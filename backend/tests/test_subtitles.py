import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from auth_support import account_client

from main import app
from services.subtitle_format import normalize_subtitle_segments
from services.subtitle_service import _extract_bilibili_subs, _extract_video_id, _parse_vtt_segments, _subtitle_data


def cue(start, end, text):
    return {"start_time": start, "end_time": end, "text": text}


class SubtitleFormatTests(unittest.TestCase):
    def test_merges_wrapped_fragments_and_splits_two_sentences(self):
        result = normalize_subtitle_segments([
            cue(0, 1.4, "First\npart of the"),
            cue(1.2, 3.7, "sentence. A second\nsentence"),
            cue(3.6, 5, "continues here."),
        ])
        self.assertEqual(
            [segment["text"] for segment in result],
            ["First part of the sentence.", "A second sentence continues here."],
        )
        self.assertEqual(result[0]["start_time"], 0)
        self.assertEqual(result[0]["end_time"], result[1]["start_time"])
        self.assertEqual(result[1]["end_time"], 5)

    def test_cjk_line_breaks_and_abbreviations_keep_their_words(self):
        result = normalize_subtitle_segments([
            cue(0, 1, "<div>先介绍<br/>第一</div>"),
            cue(1, 3, "条规则。然后"),
            cue(3, 5, "看 Dr. Li 的例子，版本是 2.1。"),
        ])
        self.assertEqual(
            [segment["text"] for segment in result],
            ["先介绍第一条规则。", "然后看 Dr. Li 的例子，版本是 2.1。"],
        )

    def test_pause_and_speaker_changes_keep_separate_cues(self):
        result = normalize_subtitle_segments([
            cue(0, 2, "Repeat"),
            cue(4, 6, "Repeat\n- Different speaker"),
        ])
        self.assertEqual([segment["text"] for segment in result], ["Repeat", "Repeat", "- Different speaker"])
        self.assertEqual(result[0]["end_time"], 2)
        self.assertEqual(result[1]["start_time"], 4)

    def test_ordinary_captions_preserve_repeated_dialogue(self):
        subtitles = _subtitle_data([
            cue(0, 1, "Yes."),
            cue(1, 3, "Yes.\nI can see it."),
        ])
        self.assertEqual(subtitles.plain_text, "Yes. Yes. I can see it.")
        self.assertEqual([segment["text"] for segment in subtitles.segments], ["Yes.", "Yes.", "I can see it."])

    def test_independent_overlapping_captions_keep_their_full_ranges(self):
        source = [cue(0, 5, "Keep reading."), cue(1, 2, "Phone rings.")]
        self.assertEqual(normalize_subtitle_segments(source), source)

    def test_korean_word_spacing_survives_cleanup(self):
        expected = [cue(0, 2, "한국어 자막을 읽습니다.")]
        for text in ("한국어 자막을 읽습니다.", "한국어 자막을\n읽습니다."):
            with self.subTest(text=text):
                self.assertEqual(normalize_subtitle_segments([cue(0, 2, text)]), expected)

    def test_vtt_rollover_and_srt_numbered_cues(self):
        vtt = (
            "\ufeffWEBVTT\n\nNOTE ignore this block\n00:00.000 --> 00:00.100\nnoise\n\n"
            "a\n00:00.000 --> 00:01.000 align:start\nfirst line\n\n"
            "00:01.000 --> 00:01.010\nfirst line\n\n"
            "00:01.010 --> 00:03.000\nfirst line\n<00:01.020><c>then &amp; more.</c>"
        )
        result = _subtitle_data(_parse_vtt_segments(vtt))
        self.assertEqual(result.plain_text, "first line then & more.")
        self.assertEqual(result.segments, [cue(0, 3, "first line then & more.")])

        srt = "1\r\n00:00:02,500 --> 00:00:04,000\r\n123\r\n"
        self.assertEqual(_subtitle_data(_parse_vtt_segments(srt)).segments, [cue(2.5, 4, "123")])
        back_to_back = "00:00.000 --> 00:01.000\nFirst.\n00:01.000 --> 00:02.000\nSecond."
        self.assertEqual(_parse_vtt_segments(back_to_back), [cue(0, 1, "First."), cue(1, 2, "Second.")])

    def test_youtube_caption_id_supports_query_order_and_shorts(self):
        for url in (
            "https://www.youtube.com/watch?list=example&v=hwP7WQkmECE",
            "https://www.youtube.com/shorts/hwP7WQkmECE",
            "https://youtu.be/hwP7WQkmECE?t=10",
        ):
            self.assertEqual(_extract_video_id(url), "hwP7WQkmECE")

    def test_youtube_caption_id_accepts_links_without_a_scheme(self):
        for url in (
            "youtu.be/hwP7WQkmECE?t=10",
            "www.youtube.com/embed/hwP7WQkmECE",
            "youtube.com/watch?v=hwP7WQkmECE",
            "//youtu.be/hwP7WQkmECE",
        ):
            with self.subTest(url=url):
                self.assertEqual(_extract_video_id(url), "hwP7WQkmECE")


class SubtitleRouteTests(unittest.TestCase):
    def test_extract_returns_organized_captions_without_loading_ai(self):
        subtitles = _subtitle_data([cue(0, 1, "一句话"), cue(1, 2, "到这里结束。")])
        video = SimpleNamespace(
            info=SimpleNamespace(platform="panopto"),
            subtitles=AsyncMock(return_value=subtitles),
        )
        with account_client() as client, \
             patch("routers.analyze.open_video", return_value=video) as open_video, \
             patch("routers.analyze.select_provider") as select_provider:
            response = client.post("/api/subtitles", json={
                "url": "https://example.test/course", "panopto_session": "fixture-session",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(open_video.call_args.kwargs["panopto_session"].get_secret_value(), "fixture-session")
        self.assertEqual(response.json(), {
            "subtitle_segments": [cue(0, 2, "一句话到这里结束。")],
            "subtitle_text": "一句话到这里结束。",
        })
        select_provider.assert_not_called()

    def test_extract_reports_no_captions(self):
        video = SimpleNamespace(info=SimpleNamespace(platform="youtube"), subtitles=AsyncMock(return_value=None))
        with account_client() as client, patch("routers.analyze.open_video", return_value=video):
            response = client.post("/api/subtitles", json={"url": "https://example.test/video"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("没有可用字幕", response.json()["detail"])


class SubtitleCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_disconnect_cancels_bilibili_extraction_and_cleans_session_file(self):
        url = "https://www.bilibili.com/video/BVFixture"
        download_started = asyncio.Event()
        incoming = asyncio.Queue()
        incoming.put_nowait({
            "type": "http.request",
            "body": json.dumps({"url": url}).encode(),
            "more_body": False,
        })
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/subtitles",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("192.0.2.3", 1234),
        }
        directory = None

        async def downloading(_url, cookies_file, output_dir):
            nonlocal directory
            directory = output_dir
            self.assertTrue(cookies_file.is_file())
            download_started.set()
            await asyncio.Future()

        async def subtitles():
            return await _extract_bilibili_subs(url, "fixture-cookie")

        video = SimpleNamespace(info=SimpleNamespace(platform="bilibili"), subtitles=subtitles)
        with account_client() as browser, patch("routers.analyze.open_video", return_value=video), \
             patch("services.subtitle_service._download_bilibili_subs", side_effect=downloading):
            session = browser.cookies.get("magical-session")
            scope["headers"].extend([(b"origin", b"http://testserver"), (b"cookie", f"magical-session={session}".encode())])
            send = AsyncMock()
            task = asyncio.create_task(app(scope, incoming.get, send))
            try:
                await asyncio.wait_for(download_started.wait(), timeout=1)
                incoming.put_nowait({"type": "http.disconnect"})
                await asyncio.wait_for(task, timeout=1)
                self.assertFalse(directory.exists())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_cancelled_bilibili_request_cleans_its_temporary_cookies(self):
        directory = None

        async def download(_url, cookies_file, output_dir):
            nonlocal directory
            directory = output_dir
            self.assertTrue(cookies_file.is_file())
            raise asyncio.CancelledError

        with patch("services.subtitle_service._download_bilibili_subs", side_effect=download):
            with self.assertRaises(asyncio.CancelledError):
                await _extract_bilibili_subs("https://www.bilibili.com/video/BVFixture", "fixture-cookie")
        self.assertFalse(directory.exists())
