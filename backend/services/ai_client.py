"""AI 服务的配置选择、请求和响应转换。"""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import partial
import json
from typing import Optional
from uuid import UUID, uuid4, uuid5

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

import config
from models.schemas import AIProviderId, AIProviderInfo, AIProvidersResponse


@dataclass(frozen=True)
class AIProvider:
    id: AIProviderId
    label: str
    model: str
    endpoint: str
    key_name: str
    api_key: str = field(repr=False)

    @property
    def configured(self) -> bool:
        key = self.api_key.strip()
        return bool(key and key != "sk-your-key-here")


PROVIDERS = {
    provider.id: provider
    for provider in (
        AIProvider(
            id="deepseek",
            label="DeepSeek 官方",
            model=config.DEEPSEEK_MODEL,
            endpoint="https://api.deepseek.com/v1/chat/completions",
            key_name="DEEPSEEK_API_KEY",
            api_key=config.DEEPSEEK_API_KEY,
        ),
        AIProvider(
            id="openai",
            label="OpenAI",
            model=config.OPENAI_MODEL,
            endpoint="https://api.openai.com/v1/responses",
            key_name="OPENAI_API_KEY",
            api_key=config.OPENAI_API_KEY,
        ),
        AIProvider(
            id="opencode-go",
            label="OpenCode Go",
            model=config.OPENCODE_GO_MODEL,
            endpoint="https://opencode.ai/inference/go/openai/v1/chat/completions",
            key_name="OPENCODE_GO_API_KEY",
            api_key=config.OPENCODE_GO_API_KEY,
        ),
    )
}


class AIServiceError(RuntimeError):
    def __init__(self, status_code: int, message: str, *, outcome_unknown: bool = False, code: str = "ai_failed"):
        super().__init__(message)
        self.status_code = status_code
        self.outcome_unknown = outcome_unknown
        self.code = code


_account_ai = ContextVar("account_ai", default=(None, nullcontext))


@contextmanager
def using_account_ai(account_id, reserve):
    token = _account_ai.set((account_id, partial(reserve, account_id)))
    try:
        yield
    finally:
        _account_ai.reset(token)


def default_provider() -> Optional[AIProvider]:
    return next((provider for provider in PROVIDERS.values() if provider.configured), None)


def provider_options() -> AIProvidersResponse:
    default = default_provider()
    return AIProvidersResponse(
        default_provider=default.id if default else None,
        providers=[
            AIProviderInfo(id=p.id, label=p.label, model=p.model, configured=p.configured)
            for p in PROVIDERS.values()
        ],
    )


def select_provider(provider_id: Optional[AIProviderId]) -> AIProvider:
    if provider_id is None:
        provider = default_provider()
        if provider is None:
            raise AIServiceError(503, "请先在 backend/.env 中配置至少一个 AI 服务的 API Key")
        return provider

    provider = PROVIDERS[provider_id]
    if not provider.configured:
        raise AIServiceError(503, f"{provider.label} 未配置，请检查 backend/.env 中的 {provider.key_name}")
    return provider


def _is_retryable(error: BaseException) -> bool:
    return isinstance(error, httpx.TimeoutException) or (
        isinstance(error, httpx.HTTPStatusError)
        and error.response.status_code in (429, 500, 502, 503, 504)
    )


async def _post_once(endpoint: str, body: dict, headers: dict, timeout: int) -> httpx.Response:
    _, reserve = _account_ai.get()
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with reserve():
            response = await client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()
            return response


_post = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)(_post_once)


def _upstream_error(provider: AIProvider, status_code: int) -> AIServiceError:
    label = provider.label
    if status_code == 401:
        return AIServiceError(503, f"{label} API Key 无效，请检查 {provider.key_name}")
    if status_code == 402:
        return AIServiceError(402, f"{label} 账户余额或额度不足")
    if status_code == 403:
        hint = "，请检查 Go 订阅、模型区域和客户端使用要求" if provider.id == "opencode-go" else ""
        return AIServiceError(403, f"{label} 拒绝了模型请求{hint}")
    if status_code == 404:
        return AIServiceError(502, f"{label} 无法访问模型 {provider.model}，请检查模型 ID 和账户权限")
    if status_code == 429:
        return AIServiceError(429, f"{label} 达到请求频率或用量限制，请稍后重试")
    return AIServiceError(502, f"{label} 请求失败（{status_code}）", outcome_unknown=status_code >= 500)


def _output_text(provider: AIProvider, data: dict) -> str:
    if provider.id == "openai":
        if data.get("status") != "completed":
            raise AIServiceError(502, "OpenAI 未生成完整回复，请重试")
        return "\n".join(
            part["text"]
            for item in data["output"] if item["type"] == "message"
            for part in item["content"] if part["type"] == "output_text"
        )
    return data["choices"][0]["message"]["content"]


async def complete(
    provider: AIProvider,
    messages: list[dict],
    *,
    max_tokens: int,
    timeout: int,
    session_id: Optional[UUID] = None,
    retry_requests: bool = True,
    json_object: bool = False,
) -> str:
    headers = {
        "Authorization": f"Bearer {provider.api_key.strip()}",
        "User-Agent": "Magical-Video/0.1.0",
    }
    if provider.id == "openai":
        body = {
            "model": provider.model,
            "input": messages,
            "max_output_tokens": max_tokens,
            "store": False,
        }
    else:
        body = {
            "model": provider.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": False,
        }
        if provider.id == "opencode-go":
            outbound_id = session_id or uuid4()
            account_id, _ = _account_ai.get()
            if account_id:
                outbound_id = uuid5(UUID(account_id), outbound_id.hex)
            headers["x-opencode-session"] = f"ses_{outbound_id.hex}"
        if json_object and provider.id == "deepseek":
            body["response_format"] = {"type": "json_object"}
            body["thinking"] = {"type": "disabled"}

    post = _post if retry_requests else _post_once
    try:
        response = await post(provider.endpoint, body, headers, timeout)
    except httpx.HTTPStatusError as error:
        raise _upstream_error(provider, error.response.status_code) from error
    except httpx.TimeoutException as error:
        raise AIServiceError(504, f"{provider.label} 响应超时，请重试", outcome_unknown=True) from error
    except httpx.RequestError as error:
        raise AIServiceError(502, f"无法连接 {provider.label}，请检查后端网络", outcome_unknown=True) from error

    try:
        content = _output_text(provider, response.json())
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        raise AIServiceError(502, f"{provider.label} 返回格式异常，请重试") from error
    if not isinstance(content, str) or not content.strip():
        raise AIServiceError(502, f"{provider.label} 未返回文本内容，请重试")
    return content.strip()


def decode_json_object(content: str) -> dict:
    """允许模型把 JSON 对象包在代码围栏或简短说明中。"""
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(content[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("AI 返回内容不是 JSON 对象")
    return value
