import asyncio
from contextlib import ExitStack
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from models.schemas import AnalysisResult
from models.study import StudyAnswer, WikiDraft
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


async def fake_analysis(text, title, **options):
    return AnalysisResult(title=title, overview="课程介绍梯度下降及损失。")


async def fake_wiki(chunks, existing):
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


async def fake_answer(question, evidence, recent, recalled):
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
        self.open = contexts.enter_context(patch("services.study.open_video", side_effect=fake_open))
        self.analyze = contexts.enter_context(patch("services.study.analyze_subtitles", side_effect=fake_analysis))
        self.wiki = contexts.enter_context(patch("services.study_ai.generate_wiki", side_effect=fake_wiki))
        self.answer = contexts.enter_context(patch("services.study_ai.generate_answer", side_effect=fake_answer))

    def client(self):
        return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 55000))

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

    def ask(self, client, conversation, question, recall=True):
        response = client.post(f"{PREFIX}/conversations/{conversation}/questions", json={
            "question": question, "request_id": uuid4().hex, "recall": recall,
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
            saved = self.submit(client, PANO + "&token=" + SECRET, panopto_session=SECRET, private_consent=True).json()
            self.assertTrue(self.wait(client, saved["id"])["result"]["private"])
            self.assertFalse(app.state.study.jobs.credentials)
        for path in self.data.glob("library.sqlite3*"):
            self.assertNotIn(SECRET.encode(), path.read_bytes())

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
            self.assertEqual(client.delete(record_url).status_code, 204)
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

    def test_ai_interruption_requires_confirmation_and_resumes_from_subtitles(self):
        async def wait_for_shutdown(*args, **kwargs):
            await asyncio.Future()

        self.analyze.side_effect = wait_for_shutdown
        with self.client() as client:
            response = self.submit(client).json()
            job_id = response["id"]
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if client.get(f"{PREFIX}/tasks/{job_id}").json()["phase"] == "ai":
                    break
                time.sleep(0.02)
            else:
                self.fail("AI stage did not start")
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
        async def changed_video(url, **credentials):
            video = await fake_open(url, **credentials)
            content = await video.subtitles()
            content.segments[0]["text"] += " 这里补充步长的说明。"
            return video

        async def wrong_quotes(chunks, existing):
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
            self.open.side_effect = changed_video
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
        self.open.side_effect = _wait_forever
        with self.client() as client:
            first = self.submit(client, PANO, panopto_session=SECRET, private_consent=True).json()
            job_id = first["id"]
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if client.get(f"{PREFIX}/tasks/{job_id}").json()["phase"] == "fetching":
                    break
                time.sleep(0.02)
            else:
                self.fail("fetch stage did not start")
        self.open.side_effect = fake_open
        with self.client() as client:
            self.assertEqual(self.wait(client, job_id, states=("needs_input",))["code"], "panopto_login_required")
            path = f"{PREFIX}/tasks/{job_id}/retry"
            self.assertEqual(client.post(path, json={}).status_code, 401)
            self.assertEqual(client.post(path, json={"panopto_session": SECRET}).status_code, 202)
            self.wait(client, job_id)
        self.assertNotIn(SECRET.encode(), (self.data / "library.sqlite3").read_bytes())

    def test_loopback_boundary(self):
        with self.client() as client:
            blocked = client.get(PREFIX + "/library", headers={"Origin": "https://example.invalid"})
            self.assertEqual(blocked.status_code, 403)
            self.assertEqual(blocked.headers["Cache-Control"], "no-store")
            self.assertEqual(client.get(PREFIX + "/library", headers={"Sec-Fetch-Site": "same-site"}).status_code, 403)
            self.assertEqual(client.get(PREFIX + "/library", headers={"Sec-Fetch-Site": "same-origin"}).status_code, 200)


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
