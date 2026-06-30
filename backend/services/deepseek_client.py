"""
DeepSeek API 客户端 — 带 tenacity 重试的 HTTP 调用。

只对可恢复错误重试（429 限流 / 5xx 服务端故障 / 网络超时），
不可恢复错误（401 Key 无效 / 402 余额不足 / 4xx 请求错误）直接返回给调用方处理。
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from config import DEEPSEEK_API_URL


class RetryableError(Exception):
    """可重试的 API 错误 — tenacity 通过此异常类型判断是否重试"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _is_retryable(exception: Exception) -> bool:
    """只有 RetryableError 和网络超时才触发重试"""
    if isinstance(exception, RetryableError):
        return True
    if isinstance(exception, httpx.TimeoutException):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),  # 2s → 4s → 8s
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
async def call_deepseek_api(body: dict, headers: dict, timeout: int = 120) -> httpx.Response:
    """
    调用 DeepSeek Chat Completions API，自动重试可恢复错误。

    Args:
        body: 请求体（model / messages / temperature / max_tokens 等）
        headers: 请求头（含 Authorization）
        timeout: 超时秒数

    Returns:
        httpx.Response — 调用方自行检查 status_code 和解析 JSON

    Raises:
        RetryableError: 3 次重试均失败（429 / 5xx）
        httpx.TimeoutException: 3 次请求均超时
        httpx.HTTPStatusError: 其他 HTTP 错误（由 tenacity reraise 抛出）
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(DEEPSEEK_API_URL, json=body, headers=headers)

        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryableError(
                status_code=resp.status_code,
                message=resp.text[:300],
            )

        return resp
