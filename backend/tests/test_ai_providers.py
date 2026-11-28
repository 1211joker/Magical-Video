import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid5

import httpx
from auth_support import account_client, register
from models.schemas import ParseResponse
from services.ai_client import PROVIDERS


SUBTITLES = "第一点先准备材料。第二点核对字幕。"
FIRST_ANSWER = "1. 准备材料。\n2. 核对字幕。"
FOLLOWUP = "第二点能再展开讲讲吗？"
SESSION_ID = "12345678-9abc-4def-8123-456789abcdef"
NUMBERED_SUMMARY = "1. 初始化。\n2. 保存提交快照。\n3. 合并分支。"


class AIProviderRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(account_client())
        self.requests = []
        self.upstream_status = 200

        fixtures = {
            provider_id: replace(provider, api_key=f"fixture-key-{provider_id}")
            for provider_id, provider in PROVIDERS.items()
        }
        providers = patch.dict(PROVIDERS, fixtures)
        providers.start()
        self.addCleanup(providers.stop)

        async_client = httpx.AsyncClient
        transport = httpx.MockTransport(self.respond)
        mock = patch(
            "services.ai_client.httpx.AsyncClient",
            side_effect=lambda **kwargs: async_client(transport=transport, **kwargs),
        )
        mock.start()
        self.addCleanup(mock.stop)

    def respond(self, request):
        body = json.loads(request.content)
        self.requests.append((request, body))
        if self.upstream_status != 200:
            return httpx.Response(self.upstream_status, text="upstream-only detail")
        if body.get("max_output_tokens", body.get("max_tokens")) == 10000:
            text = json.dumps({"overview": "字幕分析成功"})
        else:
            text = FIRST_ANSWER
        if request.url.host == "api.openai.com":
            return httpx.Response(200, json={
                "status": "completed",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "message", "content": [{"type": "output_text", "text": text}]},
                ],
            })
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

    def ask(self, **options):
        return self.client.post("/api/ask", json={
            "question": "视频讲了哪些步骤？",
            "subtitle_text": SUBTITLES,
            **options,
        })

    def test_configured_providers_expose_only_public_metadata(self):
        PROVIDERS["openai"] = replace(PROVIDERS["openai"], api_key="")
        response = self.client.get("/api/ai/providers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["default_provider"], "deepseek")
        options = {item["id"]: item for item in response.json()["providers"]}
        self.assertEqual([options[key]["configured"] for key in PROVIDERS], [True, False, True])
        self.assertNotIn("fixture-key-", response.text)
        self.assertEqual(self.requests, [])

    def test_legacy_ask_uses_deepseek_when_no_provider_is_selected(self):
        response = self.ask()
        self.assertEqual(response.json(), {"answer": FIRST_ANSWER})
        request, body = self.requests[0]
        self.assertEqual(str(request.url), "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer fixture-key-deepseek")
        self.assertEqual(body["model"], PROVIDERS["deepseek"].model)
        self.assertEqual(body["max_tokens"], 3000)
        self.assertIn(SUBTITLES, body["messages"][1]["content"])
        self.assertIn("视频讲了哪些步骤？", body["messages"][1]["content"])

    def test_openai_can_answer_followups_when_it_is_the_default(self):
        PROVIDERS["deepseek"] = replace(PROVIDERS["deepseek"], api_key="")
        response = self.ask(
            question=FOLLOWUP,
            analysis_summary=NUMBERED_SUMMARY,
            chat_history=[{"role": "assistant", "content": FIRST_ANSWER}],
        )
        self.assertEqual(response.json(), {"answer": FIRST_ANSWER})
        request, body = self.requests[0]
        self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
        self.assertEqual(body["max_output_tokens"], 3000)
        self.assertIn(NUMBERED_SUMMARY, body["input"][1]["content"])
        self.assertEqual(body["input"][-2], {"role": "assistant", "content": FIRST_ANSWER})
        self.assertEqual(body["input"][-1], {"role": "user", "content": FOLLOWUP})

    def test_analysis_routes_all_providers_through_the_existing_stream(self):
        video = SimpleNamespace(
            info=SimpleNamespace(platform="panopto", title="字幕测试"),
            subtitles=AsyncMock(return_value=SimpleNamespace(plain_text=SUBTITLES, segments=[])),
        )
        for provider in PROVIDERS.values():
            with self.subTest(provider=provider.id), patch("routers.analyze.open_video", return_value=video):
                response = self.client.post("/api/analyze-stream", json={
                    "url": "https://example.test/video",
                    "panopto_session": "fixture-platform-session",
                    "provider": provider.id,
                })
                events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
                self.assertEqual(events[-1]["status"], "done")
                self.assertEqual(events[-1]["result"]["provider"], provider.id)
                self.assertEqual(events[-1]["result"]["overview"], "字幕分析成功")
                request, body = self.requests[-1]
                self.assertEqual(str(request.url), provider.endpoint)
                self.assertEqual(request.headers["authorization"], f"Bearer fixture-key-{provider.id}")
                self.assertEqual(body["model"], provider.model)
                messages = body["input"] if provider.id == "openai" else body["messages"]
                self.assertIn(SUBTITLES, messages[-1]["content"])
                self.assertNotIn("fixture-platform-session", request.content.decode())
                if provider.id == "openai":
                    self.assertEqual(body["max_output_tokens"], 10000)
                    self.assertIs(body["store"], False)
                    self.assertNotIn("temperature", body)

    def test_bilibili_episode_preview_allows_immediate_analysis(self):
        url = "https://www.bilibili.com/bangumi/play/ep123"
        video = SimpleNamespace(
            info=ParseResponse(platform="bilibili", title="番剧单集", duration=30,
                               thumbnail="", description="", webpage_url=url),
            cookies=None,
            subtitles=AsyncMock(return_value=SimpleNamespace(plain_text=SUBTITLES, segments=[])),
        )
        with patch("routers.analyze.open_video", return_value=video):
            preview = self.client.post("/api/parse", json={"url": url})
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertIs(preview.json()["archive_supported"], False)
            streamed = self.client.post("/api/analyze-stream", json={"url": url, "provider": "openai"})
            self.assertIn("字幕分析成功", streamed.text)

    def test_go_followup_preserves_history_and_session(self):
        first = self.ask(provider="opencode-go", session_id=SESSION_ID)
        second = self.ask(
            question=FOLLOWUP,
            provider="opencode-go",
            session_id=SESSION_ID,
            analysis_summary=NUMBERED_SUMMARY,
            chat_history=[
                {"role": "user", "content": "视频讲了哪些步骤？"},
                {"role": "assistant", "content": first.json()["answer"]},
            ],
        )
        self.assertEqual(second.status_code, 200)
        first_request, _ = self.requests[0]
        second_request, body = self.requests[1]
        self.assertEqual(str(second_request.url), "https://opencode.ai/inference/go/openai/v1/chat/completions")
        self.assertEqual(second_request.headers["user-agent"], "Magical-Video/0.1.0")
        owner = self.client.get("/api/auth/session").json()["id"]
        self.assertEqual(second_request.headers["x-opencode-session"], f"ses_{uuid5(UUID(owner), UUID(SESSION_ID).hex).hex}")
        self.assertEqual(first_request.headers["x-opencode-session"], second_request.headers["x-opencode-session"])
        self.assertIn(NUMBERED_SUMMARY, body["messages"][1]["content"])
        self.assertTrue(body["messages"][1]["content"].endswith("视频讲了哪些步骤？"))
        self.assertEqual(body["messages"][-2], {"role": "assistant", "content": FIRST_ANSWER})
        self.assertEqual(body["messages"][-1], {"role": "user", "content": FOLLOWUP})

    def test_client_session_ids_are_separate_for_each_account(self):
        self.assertEqual(self.ask(provider="opencode-go", session_id=SESSION_ID).status_code, 200)
        register(self.client, "other")
        self.assertEqual(self.ask(provider="opencode-go", session_id=SESSION_ID).status_code, 200)
        self.assertEqual(len({request.headers["x-opencode-session"] for request, _ in self.requests}), 2)

    def test_unconfigured_selection_does_not_fall_back_to_another_provider(self):
        PROVIDERS["openai"] = replace(PROVIDERS["openai"], api_key="")
        response = self.ask(provider="openai")
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])
        self.assertEqual(self.requests, [])

    def test_go_rejection_is_reported_without_exposing_upstream_body(self):
        self.upstream_status = 403
        response = self.ask(provider="opencode-go")
        self.assertEqual(response.status_code, 403)
        self.assertIn("OpenCode Go", response.json()["detail"])
        self.assertNotIn("upstream-only detail", response.text)
        self.assertEqual(len(self.requests), 1)
