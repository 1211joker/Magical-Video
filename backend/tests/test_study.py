import asyncio
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4, uuid5

import httpx
from auth_support import account_client

from main import app
from models.schemas import AnalysisResult
from models.study import StudyAnswer, WikiDraft
from services.ai_client import PROVIDERS
from services.analysis_service import analyze_subtitles
from services.panopto_service import PanoptoError
from services.study_ai import generate_answer, generate_wiki
from services.study_jobs import TEMPORARY_TTL
from services.subtitle_service import extract_subtitle_text
from storage.study_db import StudyProblem

PREFIX = "/api/study"
VIDEOS = (
    "https://www.youtube.com/watch?v=aircAruvnKk",
    "https://www.youtube.com/watch?v=IHZwWFHWa-w",
    "https://www.youtube.com/watch?v=Ilg3gGewQ5U",
)
PANO = "https://polyu.ap.panopto.com/Panopto/Pages/Viewer.aspx?id=11111111-1111-1111-1111-111111111111"
BILI = "https://www.bilibili.com/video/BV1ab"
SHORT = "https://b23.tv/FixtureLink"
SECRET = "TEST-SESSION-ONLY-IN-MEMORY"
PUBLIC_CUES = [
    "梯度下降在第一讲介绍沿负梯度调整权重的直觉。",
    "梯度下降在第二讲把平均损失用于更新多个权重。",
    "梯度下降由反向传播计算所需导数，第三讲讨论小批量。",
]


async def fake_open(url, **credentials):
    index = VIDEOS.index(url) if url in VIDEOS else 0
    platform = "panopto" if "panopto.com" in url else "bilibili" if "bilibili.com" in url else "youtube"
    title = f"梯度下降 第 {index + 1} 讲"
    info = SimpleNamespace(webpage_url=url, title=title, duration=40, platform=platform)
    caption = PUBLIC_CUES[index]
    segments = [{"start_time": 2, "end_time": 10, "text": caption}]
    return SimpleNamespace(info=info, subtitles=AsyncMock(return_value=SimpleNamespace(segments=segments)))


async def fake_changed_open(url, **credentials):
    video = await fake_open(url, **credentials)
    content = await video.subtitles()
    content.segments[0]["text"] += " 这里补充步长的说明。"
    return video


async def fake_analysis(text, title, provider, **options):
    return AnalysisResult(title=title, overview="课程介绍梯度下降及损失。")


async def fake_wiki(chunks, existing, **options):
    chunk = chunks[0]
    return WikiDraft.model_validate({"pages": [
        {
            "title": "梯度下降", "aliases": ["gradient descent"],
            "claims": [{"chunk_id": chunk["id"], "quote": chunk["text"], "explanation": "用这个例子解释梯度下降。"}],
            "related": ["损失函数"],
        },
        {
            "title": "损失函数", "aliases": ["loss"],
            "claims": [{"chunk_id": chunk["id"], "quote": chunk["text"], "explanation": "用字幕说明训练的目标。"}],
        },
    ]})


async def fake_answer(question, evidence, recent, recalled, **options):
    return StudyAnswer(
        answer="1. 计算梯度\n2. 沿负梯度更新权重",
        citations=[e["id"] for e in evidence],
        recalled_turns=[turn["id"] for turn in recalled],
    )


class StudyTests(unittest.TestCase):
    def setUp(self):
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        self.data = Path(contexts.enter_context(tempfile.TemporaryDirectory()))
        contexts.enter_context(patch.dict(os.environ, {
            "STUDY_DATA_DIR": str(self.data), "STUDY_SEMANTIC": "0", "STUDY_ENABLED": "1",
        }))
        contexts.enter_context(patch.dict(PROVIDERS, {
            provider_id: replace(provider, api_key=f"fixture-key-{provider_id}")
            for provider_id, provider in PROVIDERS.items()
        }))
        self.open = contexts.enter_context(patch("services.study.open_video", side_effect=fake_open))
        self.analyze = contexts.enter_context(patch("services.study.analyze_subtitles", side_effect=fake_analysis))
        self.wiki = contexts.enter_context(patch("services.study_ai.generate_wiki", side_effect=fake_wiki))
        self.answer = contexts.enter_context(patch("services.study_ai.generate_answer", side_effect=fake_answer))

    @contextmanager
    def client(self):
        with account_client(self.data) as client:
            self.account_id = client.get("/api/auth/session").json()["id"]
            self.library_path = self.data / "users" / self.account_id / "library.sqlite3"
            yield client

    def wait_for_phase(self, client, job_id, phase):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            response = client.get(f"{PREFIX}/tasks/{job_id}")
            self.assertEqual(response.status_code, 200, response.text)
            if response.json()["phase"] == phase:
                return
            time.sleep(0.02)
        self.fail(f"task did not reach {phase}")

    def wait(self, client, job_id, states=("done",), timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = client.get(f"{PREFIX}/tasks/{job_id}")
            self.assertEqual(response.status_code, 200, response.text)
            job = response.json()
            if job["state"] in states:
                return job
            if job["state"] in {"failed", "cancelled", "needs_input", "needs_retry", "done"}:
                self.fail(str(job))
            time.sleep(0.025)
        self.fail(f"task did not reach {states}")

    def submit(self, client, url=VIDEOS[0], **options):
        data = {"url": url, "request_id": uuid4().hex, "save": True, **options}
        return client.post(PREFIX + "/analysis", json=data)

    def save_video(self, client, url=VIDEOS[0]):
        response = self.submit(client, url)
        self.assertEqual(response.status_code, 202, response.text)
        return self.wait(client, response.json()["id"])["result"]

    def course(self, client, title="神经网络"):
        response = client.post(PREFIX + "/courses", json={"title": title})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def add(self, client, course_id, video_id):
        response = client.put(f"{PREFIX}/courses/{course_id}/videos/{video_id}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def conversation(self, client, scope, scope_id=None):
        response = client.post(PREFIX + "/conversations", json={"scope": scope, "scope_id": scope_id})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def ask(self, client, conversation, question, recall=True, **options):
        response = client.post(f"{PREFIX}/conversations/{conversation}/questions", json={
            "question": question, "request_id": uuid4().hex, "recall": recall, **options,
        })
        self.assertEqual(response.status_code, 202, response.text)
        self.wait(client, response.json()["id"])
        return client.get(f"{PREFIX}/conversations/{conversation}").json()["turns"][-1]

    def test_archive_identity_idempotence_and_course_order(self):
        with self.client() as client:
            req_id = uuid4().hex
            first = self.submit(client, request_id=req_id).json()
            again = self.submit(client, "https://youtu.be/aircAruvnKk?t=45", request_id=req_id).json()
            self.assertEqual(first["id"], again["id"])
            saved = self.wait(client, req_id)["result"]
            self.assertEqual(self.analyze.call_count, 1)
            same = self.save_video(client, "https://youtu.be/aircAruvnKk")
            self.assertEqual((saved["id"], saved["source_id"]), (same["id"], same["source_id"]))
            part_one = self.save_video(client, "https://www.bilibili.com/video/BV1ab")
            part_two = self.save_video(client, "https://www.bilibili.com/video/BV1ab?p=2")
            self.assertNotEqual(part_one["id"], part_two["id"])
            course = self.course(client)
            other = self.course(client, "另一个课程")
            for video in (part_one, part_two):
                self.wait(client, self.add(client, course, video["id"]))
            self.wait(client, self.add(client, other, part_one["id"]))
            route = f"{PREFIX}/courses/{course}"
            self.assertEqual(client.put(route + "/order", json={"video_ids": [part_two["id"], part_one["id"]]}).status_code, 204)
            self.assertEqual(client.put(route + "/order", json={"video_ids": [part_two["id"]]}).status_code, 409)
            ids = [video["id"] for video in client.get(route).json()["videos"]]
            self.assertEqual(ids, [part_two["id"], part_one["id"]])

    def test_reanalysis_keeps_task_results_while_reusing_subtitles(self):
        async def by_provider(_text, title, provider, **_options):
            return AnalysisResult(title=title, overview=f"{provider.id} 生成的摘要")

        self.analyze.side_effect = by_provider
        with self.client() as client:
            old_id = self.submit(client, provider="deepseek").json()["id"]
            original = self.wait(client, old_id)
            database = app.state.study.services[self.account_id].database
            # 旧版本只记录字幕版本的 ID。
            with database.transaction(write=True) as connection:
                connection.execute("UPDATE jobs SET result=json_remove(result, '$.analysis') WHERE id=?", (old_id,))
            self.assertEqual(client.get(f"{PREFIX}/tasks/{old_id}").json(), original)

            temporary_id = self.submit(client, save=False, provider="openai").json()["id"]
            temporary = self.wait(client, temporary_id)
            response = client.put(f"{PREFIX}/analysis/{temporary_id}/archive", json={})
            self.assertEqual(response.status_code, 200, response.text)
            archived = response.json()
            self.assertEqual(archived["result"]["analysis"], temporary["result"]["analysis"])

            newest_id = self.submit(client, provider="opencode-go").json()["id"]
            newest = self.wait(client, newest_id)
            video_id = newest["result"]["id"]
            self.assertEqual(client.get(f"{PREFIX}/videos/{video_id}").json(), newest["result"])

        with self.client() as client:
            for expected in (original, archived, newest):
                with self.subTest(provider=expected["provider"]):
                    task = client.get(f"{PREFIX}/tasks/{expected['id']}").json()
                    self.assertEqual(task["result"]["analysis"], expected["result"]["analysis"])
                    self.assertEqual(task["result"]["subtitle_segments"], expected["result"]["subtitle_segments"])
                    self.assertEqual(task["provider"], task["result"]["analysis"]["provider"])
                    self.assertEqual(task["result"]["id"], video_id)
                    self.assertEqual(task["result"]["source_id"], newest["result"]["source_id"])
        self.assertEqual(self.analyze.await_count, 3)

    def test_private_opt_in_temporary_expiry_and_redacted_validation(self):
        with self.client() as client:
            rejected = self.submit(client, PANO, panopto_session=SECRET)
            self.assertEqual(rejected.json()["code"], "private_consent")
            invalid = self.submit(client, PANO, panopto_session=SECRET, request_id="bad")
            self.assertEqual(invalid.status_code, 422)
            self.assertNotIn(SECRET, invalid.text)
            temporary = self.submit(client, PANO, save=False, panopto_session=SECRET).json()
            self.wait(client, temporary["id"])
            self.assertEqual(client.get(PREFIX + "/library").json()["videos"], [])
            with patch("services.study_jobs.time.time", return_value=time.time() + TEMPORARY_TTL + 1):
                self.assertEqual(client.get(f"{PREFIX}/tasks/{temporary['id']}").status_code, 404)
                self.assertEqual(client.put(f"{PREFIX}/analysis/{temporary['id']}/archive", json={}).status_code, 404)
            saved = self.submit(client, PANO + "&token=" + SECRET, panopto_session=SECRET, private_consent=True).json()
            self.assertTrue(self.wait(client, saved["id"])["result"]["private"])
            self.assertFalse(app.state.study.services[self.account_id].jobs.credentials)
        for path in self.library_path.parent.glob("library.sqlite3*"):
            self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_archive_completed_temporary_analysis_reuses_result_and_keeps_task(self):
        with self.client() as client:
            job_id = self.submit(client, save=False).json()["id"]
            temporary = self.wait(client, job_id)
            self.assertFalse(temporary["persistent"])
            self.assertEqual(client.get(PREFIX + "/library").json()["videos"], [])

            route = f"{PREFIX}/analysis/{job_id}/archive"
            response = client.put(route, json={})
            self.assertEqual(response.status_code, 200, response.text)
            saved = response.json()
            self.assertEqual(saved["id"], job_id)
            self.assertTrue(saved["persistent"])
            for field in ("analysis", "subtitle_segments"):
                self.assertEqual(saved["result"][field], temporary["result"][field])
            self.assertEqual(client.put(route, json={}).json(), saved)
            self.assertNotIn(job_id, app.state.study.services[self.account_id].jobs.temporary)

        with self.client() as client:
            self.assertEqual(client.get(f"{PREFIX}/tasks/{job_id}").json(), saved)
            replay = self.submit(client, request_id=job_id, save=False)
            self.assertEqual(replay.status_code, 202, replay.text)
            self.assertEqual(replay.json()["id"], job_id)
            self.assertEqual(self.submit(client, request_id=job_id).json()["code"], "request_conflict")
            videos = client.get(PREFIX + "/library").json()["videos"]
            self.assertEqual([video["id"] for video in videos], [saved["result"]["id"]])
        self.open.assert_awaited_once()
        self.analyze.assert_awaited_once()

    def test_archive_private_temporary_analysis_requires_consent(self):
        with self.client() as client:
            job_id = self.submit(client, PANO, save=False, panopto_session=SECRET).json()["id"]
            self.wait(client, job_id)
            route = f"{PREFIX}/analysis/{job_id}/archive"
            rejected = client.put(route, json={})
            self.assertEqual(rejected.status_code, 400)
            self.assertEqual(rejected.json()["code"], "private_consent")
            self.assertFalse(client.get(f"{PREFIX}/tasks/{job_id}").json()["persistent"])
            self.assertEqual(client.get(PREFIX + "/library").json()["videos"], [])

            response = client.put(route, json={"private_consent": True})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["result"]["private"])
        for path in self.library_path.parent.glob("library.sqlite3*"):
            self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_public_panopto_can_be_analyzed_without_a_session(self):
        with self.client() as client:
            job = self.submit(client, PANO, save=False).json()
            result = self.wait(client, job["id"])["result"]
            self.assertEqual(result["platform"], "panopto")
            self.open.assert_awaited_once_with(PANO)
            self.assertFalse(client.get(PREFIX + "/library").json()["videos"])

    def test_study_tasks_use_selected_providers_and_wait_after_unknown_outcome(self):
        requests = []

        def upstream(request):
            body = json.loads(request.content)
            messages = body["input"] if "input" in body else body["messages"]
            limit = body.get("max_output_tokens", body.get("max_tokens"))
            requests.append((request, limit))
            if len(requests) == 1:
                raise httpx.ReadTimeout("mock timeout", request=request)
            if limit == 10000:
                result = {"overview": "课程介绍梯度下降及损失。"}
            else:
                data = json.loads(messages[-1]["content"])
                chunk = data["subtitles"][0]
                if limit == 4000:
                    result = {"pages": [{
                        "title": "梯度下降",
                        "claims": [{"chunk_id": chunk["id"], "quote": chunk["text"], "explanation": "解释梯度下降。"}],
                    }]}
                else:
                    result = {"answer": "1. 计算梯度\n2. 沿负梯度更新权重", "citations": [chunk["id"]]}
            content = "```json\n" + json.dumps(result) + "\n```"
            if request.url.host == "api.openai.com":
                return httpx.Response(200, json={"status": "completed", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": content}]},
                ]})
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        self.analyze.side_effect = analyze_subtitles
        self.wiki.side_effect = generate_wiki
        self.answer.side_effect = generate_answer
        make_client = httpx.AsyncClient
        transport = httpx.MockTransport(upstream)
        with patch("services.ai_client.httpx.AsyncClient",
                   side_effect=lambda **kwargs: make_client(transport=transport, **kwargs)):
            with self.client() as client:
                submitted = self.submit(client, provider="openai").json()
                job = self.wait(client, submitted["id"], states=("needs_retry",))
                self.assertEqual(job["provider"], "openai")
                self.assertEqual(job["code"], "retry_confirmation")
                self.assertEqual(len(requests), 1)
            with self.client() as client:
                self.assertEqual(len(requests), 1)
                self.assertEqual(client.post(f"{PREFIX}/tasks/{job['id']}/retry", json={}).status_code, 202)
                video = self.wait(client, job["id"])["result"]
                self.assertEqual(video["analysis"]["provider"], "openai")
                course = self.course(client)
                wiki = self.wait(client, self.add(client, course, video["id"]))
                self.assertEqual(wiki["provider"], "openai")
                conversation = self.conversation(client, "course", course)
                turn = self.ask(client, conversation, "梯度下降怎么更新权重？", provider="opencode-go")
                followup = self.ask(client, conversation, "第二点能再展开讲讲吗", provider="opencode-go")
                self.assertTrue(turn["citations"] and followup["citations"])
                self.assertEqual(self.save_video(client, VIDEOS[1])["analysis"]["provider"], "deepseek")
        self.assertEqual([(request.url.host, limit) for request, limit in requests], [
            ("api.openai.com", 10000), ("api.openai.com", 10000), ("api.openai.com", 4000),
            ("opencode.ai", 2800), ("opencode.ai", 2800), ("api.deepseek.com", 10000),
        ])
        self.assertEqual({request.headers["x-opencode-session"] for request, limit in requests if limit == 2800},
                         {f"ses_{uuid5(UUID(self.account_id), conversation).hex}"})

    def test_video_group_and_title_survive_reanalysis_and_restart(self):
        groups_url = PREFIX + "/groups"
        with self.client() as client:
            video = self.save_video(client)
            self.assertIsNone(video["group_id"])
            video_url = f"{PREFIX}/videos/{video['id']}"
            course_id = self.course(client)
            course_url = f"{PREFIX}/courses/{course_id}"
            self.wait(client, self.add(client, course_id, video["id"]))
            created = client.post(groups_url, json={"title": "复习 A"})
            self.assertEqual(created.status_code, 201)
            group_id = created.json()["id"]
            group_url = f"{groups_url}/{group_id}"
            self.assertEqual(client.post(groups_url, json={"title": " 复习 ａ "}).status_code, 409)
            bad_group = client.patch(video_url, json={"title": "误改", "group_id": uuid4().hex})
            self.assertEqual(bad_group.status_code, 404)
            self.assertEqual(client.get(video_url).json()["title"], video["title"])
            new_title = "我的梯度下降笔记"
            self.assertEqual(client.patch(video_url, json={"title": new_title, "group_id": group_id}).status_code, 204)
            self.assertEqual(client.patch(group_url, json={"title": "已复习"}).status_code, 204)
            reanalyzed = self.save_video(client)
            self.assertEqual((reanalyzed["id"], reanalyzed["title"], reanalyzed["group_id"]),
                             (video["id"], new_title, group_id))
            member, = client.get(course_url).json()["videos"]
            self.assertEqual(member["title"], new_title)
        with self.client() as client:
            snapshot = client.get(PREFIX + "/library").json()
            self.assertEqual(snapshot["groups"], [{"id": group_id, "title": "已复习", "video_count": 1}])
            self.assertEqual(client.delete(group_url).status_code, 204)
            saved = client.get(video_url).json()
            self.assertIsNone(saved["group_id"])
            self.assertEqual(saved["title"], new_title)
            self.assertEqual(saved["subtitle_segments"], video["subtitle_segments"])
            course = client.get(course_url).json()
            self.assertEqual([member["id"] for member in course["videos"]], [video["id"]])
            self.assertTrue(course["wiki_pages"])

    def test_delete_analysis_record_preserves_archive_wiki_and_conversation(self):
        with self.client() as client:
            task_id = self.submit(client).json()["id"]
            video = self.wait(client, task_id)["result"]
            course = self.course(client)
            wiki_task = self.add(client, course, video["id"])
            self.wait(client, wiki_task)
            conversation = self.conversation(client, "video", video["id"])
            turn = self.ask(client, conversation, "梯度下降怎么调整权重")
            self.assertEqual(client.delete(f"{PREFIX}/analysis/{wiki_task}").status_code, 404)
            record_url = f"{PREFIX}/analysis/{task_id}"
            self.assertEqual(client.delete(record_url).status_code, 204)
            self.assertEqual(client.delete(record_url).status_code, 404)
            self.assertEqual(client.get(f"{PREFIX}/tasks/{task_id}").status_code, 404)
            self.assertEqual(client.get(PREFIX + "/tasks?kind=analysis").json(), [])
            self.assertEqual(client.get(f"{PREFIX}/videos/{video['id']}").json(), video)
            self.assertTrue(client.get(f"{PREFIX}/courses/{course}").json()["wiki_pages"])
            self.assertEqual(client.get(f"{PREFIX}/conversations/{conversation}").json()["turns"], [turn])
            temporary = self.submit(client, save=False).json()["id"]
            self.wait(client, temporary)
            self.assertEqual(client.delete(f"{PREFIX}/analysis/{temporary}").status_code, 204)
            self.assertEqual(client.get(f"{PREFIX}/tasks/{temporary}").status_code, 404)

    def test_delete_running_analysis_keeps_removed_record_out_of_queue(self):
        async def report_after_cancel(*args, **kwargs):
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                raise RuntimeError("上游请求已取消") from None

        with self.client() as client:
            for save in (False, True):
                with self.subTest(save=save):
                    self.analyze.side_effect = report_after_cancel
                    task_id = self.submit(client, save=save).json()["id"]
                    self.assertEqual(self.wait(client, task_id, states=("running",))["phase"], "ai")
                    self.assertEqual(client.delete(f"{PREFIX}/analysis/{task_id}").status_code, 204)
                    self.assertEqual(client.get(f"{PREFIX}/tasks/{task_id}").status_code, 404)
                    self.assertEqual(client.get(PREFIX + "/tasks?kind=analysis").json(), [])
                    self.assertEqual(client.get(PREFIX + "/library").json()["videos"], [])

    def test_wiki_increment_and_confirmed_cross_course_link(self):
        with self.client() as client:
            videos = [self.save_video(client, url) for url in VIDEOS]
            first = self.course(client)
            other = self.course(client, "另一个梯度下降课程")
            for video in videos:
                self.wait(client, self.add(client, first, video["id"]))
            self.wait(client, self.add(client, other, videos[0]["id"]))
            pages = client.get(f"{PREFIX}/courses/{first}").json()["wiki_pages"]
            self.assertEqual({item["title"] for item in pages}, {"梯度下降", "损失函数"})
            page_id = next(item["id"] for item in pages if item["title"] == "梯度下降")
            url = f"{PREFIX}/wiki/{page_id}"
            page = client.get(url).json()
            self.assertEqual({item["source"]["video_id"] for item in page["claims"]}, {v["id"] for v in videos})
            peer = page["suggestions"][0]
            self.assertEqual(peer["course_id"], other)
            self.assertEqual(client.put(f"{url}/links/{peer['id']}", json={"accepted": True}).status_code, 204)
            self.assertIn(peer["id"], {item["id"] for item in client.get(url).json()["related"]})
            loss = next(item["id"] for item in pages if item["title"] == "损失函数")
            self.assertEqual(client.post(f"{PREFIX}/wiki/{loss}/merge/{page_id}").status_code, 204)
            self.assertIn("损失函数", client.get(url).json()["aliases"])

    def test_scope_recall_followup_and_deletion(self):
        with self.client() as client:
            videos = [self.save_video(client, url) for url in VIDEOS]
            course = self.course(client)
            for video in videos[:2]:
                self.wait(client, self.add(client, course, video["id"]))
            initial = self.conversation(client, "course", course)
            old = self.ask(client, initial, "两讲如何解释梯度下降")
            self.assertEqual({e["video_id"] for e in old["citations"]}, {v["id"] for v in videos[:2]})
            followup = self.ask(client, initial, "第二点能再展开讲讲吗")
            self.assertTrue(followup["citations"])
            self.assertEqual(self.answer.call_args.args[2][-1]["id"], old["id"])
            fresh = self.conversation(client, "course", course)
            recalled = self.ask(client, fresh, "上次提到的梯度下降")
            self.assertIn(old["id"], {turn["id"] for turn in recalled["recalled"]})
            self.assertFalse(self.ask(client, fresh, "梯度下降怎么更新", recall=False)["recalled"])
            ambiguous = self.ask(client, self.conversation(client, "course", course), "第二点能再展开讲讲吗")
            self.assertIn("哪条", ambiguous["answer"])
            target = videos[0]["id"]
            self.assertGreater(client.get(f"{PREFIX}/videos/{target}/impact").json()["turn_count"], 0)
            client.delete(f"{PREFIX}/videos/{target}")
            stored = client.get(f"{PREFIX}/conversations/{initial}").json()["turns"]
            self.assertTrue(all(turn["invalidated"] and not turn["citations"] for turn in stored))
            self.assertFalse(self.ask(client, self.conversation(client, "course", course), "梯度下降")["recalled"])
            client.delete(f"{PREFIX}/videos/{videos[1]['id']}?clear_turns=true")
            self.assertFalse(client.get(f"{PREFIX}/conversations/{initial}").json()["turns"])

    def test_deleting_the_middle_video_updates_course_question_numbers(self):
        with self.client() as client:
            videos = [self.save_video(client, url) for url in VIDEOS]
            course = self.course(client)
            for video in videos:
                self.wait(client, self.add(client, course, video["id"]))
            self.assertEqual(client.delete(f"{PREFIX}/videos/{videos[1]['id']}").status_code, 200)
            conversation = self.conversation(client, "course", course)
            turn = self.ask(client, conversation, "第 2 讲如何讨论梯度下降？")
            self.assertEqual({item["video_id"] for item in turn["citations"]}, {videos[2]["id"]})

    def test_deleting_a_video_cancels_its_resolved_short_link_analysis(self):
        async def resolve_short(url, **credentials):
            return await fake_open(BILI if url == SHORT else url, **credentials)

        with self.client() as client:
            video = self.save_video(client, BILI)
            self.open.side_effect = resolve_short
            self.analyze.side_effect = _wait_forever
            job_id = self.submit(client, SHORT).json()["id"]
            self.wait_for_phase(client, job_id, "ai")
            self.assertEqual(client.delete(f"{PREFIX}/videos/{video['id']}").status_code, 200)
            self.assertEqual(client.get(f"{PREFIX}/tasks/{job_id}").status_code, 404)
            self.assertFalse(client.get(PREFIX + "/library").json()["videos"])

    def test_deletion_during_short_link_resolution_blocks_stale_archive(self):
        release = Event()

        async def resolve_later(url, **credentials):
            if url == SHORT:
                await asyncio.to_thread(release.wait, 4)
            return await fake_open(BILI, **credentials)

        with self.client() as client:
            video = self.save_video(client, BILI)
            self.open.side_effect = resolve_later
            job_id = self.submit(client, SHORT).json()["id"]
            try:
                self.wait_for_phase(client, job_id, "fetching")
                self.assertEqual(client.delete(f"{PREFIX}/videos/{video['id']}").status_code, 200)
            finally:
                release.set()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if client.get(f"{PREFIX}/tasks/{job_id}").status_code == 404:
                    break
                time.sleep(0.02)
            else:
                self.fail("stale short-link analysis survived video deletion")
            self.assertEqual(self.analyze.await_count, 1)
            self.assertFalse(client.get(PREFIX + "/library").json()["videos"])
            self.assertNotEqual(self.save_video(client, SHORT)["id"], video["id"])

    def test_ai_interruption_requires_confirmation_and_resumes_from_subtitles(self):
        async def wait_for_shutdown(*args, **kwargs):
            await asyncio.Future()

        self.analyze.side_effect = wait_for_shutdown
        with self.client() as client:
            response = self.submit(client).json()
            job_id = response["id"]
            self.wait_for_phase(client, job_id, "ai")
        self.analyze.side_effect = fake_analysis
        with self.client() as client:
            job = self.wait(client, job_id, states=("needs_retry",))
            self.assertEqual(job["code"], "retry_confirmation")
            self.assertEqual(client.post(f"{PREFIX}/tasks/{job_id}/retry", json={}).status_code, 202)
            self.wait(client, job_id)
        self.assertEqual(self.open.await_count, 1)
        self.assertEqual(self.analyze.await_count, 2)

    def test_failed_retry_and_cancel_do_not_publish_partial_results(self):
        with self.client() as client:
            video = self.save_video(client)
            course = self.course(client)
            self.wiki.side_effect = StudyProblem("请求结果不明", code="retry_confirmation")
            first = self.add(client, course, video["id"])
            self.wait(client, first, states=("needs_retry",))
            self.assertFalse(client.get(f"{PREFIX}/courses/{course}").json()["wiki_pages"])
            self.wiki.side_effect = fake_wiki
            self.assertEqual(client.post(f"{PREFIX}/tasks/{first}/retry", json={}).status_code, 202)
            self.wait(client, first)
            self.analyze.side_effect = lambda *args, **kwargs: None
            unexpected = self.submit(client, VIDEOS[1]).json()["id"]
            self.wait(client, unexpected, states=("failed",))
            self.assertEqual(client.get(PREFIX + "/library").json()["videos"][0]["id"], video["id"])
            self.analyze.side_effect = _wait_forever
            queued = self.submit(client, VIDEOS[1]).json()["id"]
            self.assertEqual(client.delete(f"{PREFIX}/tasks/{queued}").json()["state"], "cancelled")
            self.assertEqual(len(client.get(PREFIX + "/library").json()["videos"]), 1)

    def test_updated_subtitles_keep_previous_wiki_when_quotes_fail(self):
        async def wrong_quotes(chunks, existing, **options):
            draft = await fake_wiki(chunks, existing)
            for page in draft.pages:
                page.claims[0].quote = "这句话从未出现在原始字幕中。"
            return draft

        with self.client() as client:
            initial = self.submit(client).json()["id"]
            video = self.wait(client, initial)["result"]
            course = self.course(client)
            self.wait(client, self.add(client, course, video["id"]))
            self.wiki.side_effect = wrong_quotes
            self.open.side_effect = fake_changed_open
            updated = self.save_video(client)
            self.assertEqual(updated["id"], video["id"])
            self.assertNotEqual(updated["source_id"], video["source_id"])
            previous = self.wait(client, initial)["result"]
            self.assertEqual(previous["source_id"], video["source_id"])
            course_url = f"{PREFIX}/courses/{course}"
            current = client.get(course_url).json()
            wiki_task = current["videos"][0]["wiki_task"]["id"]
            self.assertEqual(self.wait(client, wiki_task, states=("failed",))["code"], "wiki_no_evidence")
            self.assertEqual(client.get(course_url).json()["videos"][0]["published_source"], video["source_id"])
            self.wiki.side_effect = fake_wiki
            self.assertEqual(client.post(f"{PREFIX}/tasks/{wiki_task}/retry", json={}).status_code, 202)
            self.wait(client, wiki_task)
            self.assertEqual(client.get(course_url).json()["videos"][0]["published_source"], updated["source_id"])

    def test_wiki_republishes_when_subtitles_return_to_an_older_version(self):
        with self.client() as client:
            first = self.save_video(client)
            course = self.course(client)
            first_wiki = self.add(client, course, first["id"])
            self.wait(client, first_wiki)
            url = f"{PREFIX}/courses/{course}"
            self.open.side_effect = fake_changed_open
            second = self.save_video(client)
            next_task = client.get(url).json()["videos"][0]["wiki_task"]["id"]
            self.wait(client, next_task)
            self.assertEqual(client.get(url).json()["videos"][0]["published_source"], second["source_id"])
            self.open.side_effect = fake_open
            restored = self.save_video(client)
            self.assertEqual(restored["source_id"], first["source_id"])
            self.wait(client, first_wiki)
            self.assertEqual(client.get(url).json()["videos"][0]["published_source"], first["source_id"])

    def test_evidence_absence_and_fabricated_citation(self):
        with self.client() as client:
            video = self.save_video(client)
            conversation = self.conversation(client, "video", video["id"])
            unrelated = self.ask(client, conversation, "鲸鱼的寿命是多少？")
            self.assertIn("没有找到足够的字幕", unrelated["answer"])
            self.assertFalse(unrelated["citations"])
            self.answer.side_effect = None
            self.answer.return_value = StudyAnswer(answer="无法验证的结论", citations=["a" * 32])
            pretend = self.ask(client, conversation, "梯度下降是什么")
            self.assertNotIn("无法验证的结论", pretend["answer"])
            self.assertFalse(pretend["citations"])

    def test_restart_before_private_subtitles_requires_fresh_credentials(self):
        async def protected_panopto(url, **credentials):
            if not credentials.get("panopto_session"):
                raise PanoptoError("panopto_login_required", "需要登录此录像")
            return await fake_open(url, **credentials)

        self.open.side_effect = _wait_forever
        with self.client() as client:
            first = self.submit(client, PANO, panopto_session=SECRET, private_consent=True).json()
            job_id = first["id"]
            self.wait_for_phase(client, job_id, "fetching")
        self.open.side_effect = protected_panopto
        with self.client() as client:
            self.assertEqual(self.wait(client, job_id, states=("needs_input",))["code"], "panopto_login_required")
            path = f"{PREFIX}/tasks/{job_id}/retry"
            self.assertEqual(client.post(path, json={}).status_code, 401)
            self.assertEqual(client.post(path, json={"panopto_session": SECRET}).status_code, 202)
            self.wait(client, job_id)
        self.assertNotIn(SECRET.encode(), self.library_path.read_bytes())


async def _wait_forever(*args, **kwargs):
    await asyncio.Future()


class SubtitleCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_bilibili_cancellation_reaps_before_removing_temporary_session(self):
        started = asyncio.Event()
        cookies = None
        cleaned = False

        async def running(command, url, timeout):
            nonlocal cookies, cleaned
            cookies = Path(command[command.index("--cookies") + 1])
            self.assertTrue(cookies.is_file())
            started.set()
            try:
                await asyncio.Future()
            finally:
                cleaned = cookies.is_file()

        with patch("services.subtitle_service.run_ytdlp", side_effect=running):
            task = asyncio.create_task(extract_subtitle_text("https://www.bilibili.com/video/BV1ab", SECRET))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(cleaned)
        self.assertFalse(cookies.exists())
