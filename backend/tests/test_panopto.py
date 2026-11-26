import unittest
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from services import panopto_service
from services.download_service import DownloadRedirect, prepare_download
from services.panopto_service import PanoptoError
from services.video_service import open_video


COURSE = "https://polyu.ap.panopto.com/Panopto/Pages/Viewer.aspx?id=11111111-1111-1111-1111-111111111111"
PODCAST = "https://polyu.ap.panopto.com/Panopto/Podcast/recording.mp4"
DELIVERY = {
    "SessionName": "示例课程",
    "Duration": 65.0,
    "HasCaptions": True,
    "AvailableLanguages": [0, 8],
    "PodcastStreams": [{"StreamUrl": "https://polyu.ap.panopto.com/playback.m3u8"}],
}


class PanoptoTests(unittest.IsolatedAsyncioTestCase):
    def mock_viewer(self, respond):
        requests = []
        async_client = httpx.AsyncClient

        def handler(request):
            requests.append(request)
            return respond(request)

        def client(**kwargs):
            return async_client(transport=httpx.MockTransport(handler), **kwargs)

        scope = patch.object(panopto_service.httpx, "AsyncClient", side_effect=client)
        scope.start()
        self.addCleanup(scope.stop)
        return requests

    async def test_playback_permission_does_not_offer_download(self):
        self.mock_viewer(lambda _: httpx.Response(200, json={"Delivery": DELIVERY, "DownloadUrl": None}))
        video = await open_video(COURSE)
        self.assertEqual(video.info.formats, [])
        with self.assertRaises(PanoptoError) as error:
            await prepare_download(COURSE, "best", None)
        self.assertEqual(error.exception.code, "panopto_download_unavailable")

    async def test_official_download_is_a_browser_redirect(self):
        payload = {"Delivery": DELIVERY, "DownloadUrl": PODCAST}
        requests = self.mock_viewer(lambda _: httpx.Response(200, json=payload))
        download = await prepare_download(COURSE, "best", None)
        self.assertEqual(download, DownloadRedirect(PODCAST))
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/Panopto/Pages/Viewer/DeliveryInfo.aspx")

    async def test_subtitles_reuse_delivery_and_caption_duration(self):
        def respond(request):
            if request.url.params.get("getCaptions"):
                self.assertEqual(request.url.params["language"], "8")
                return httpx.Response(200, json=[
                    {"Time": 1.0, "Caption": "<b>第一点</b>", "CaptionDuration": 2.0, "Duration": 0},
                    {"Time": 8.0, "Caption": "第二点"},
                ])
            return httpx.Response(200, json={"Delivery": DELIVERY})

        requests = self.mock_viewer(respond)
        session = SecretStr("fixture-session")
        video = await open_video(COURSE, panopto_session=session)
        subtitles = await video.subtitles()
        self.assertEqual(subtitles.plain_text, "第一点 第二点")
        self.assertEqual([segment["end_time"] for segment in subtitles.segments], [3.0, 65.0])
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(request.headers.get("Cookie") == ".ASPXAUTH=fixture-session" for request in requests))

    async def test_subtitles_fall_back_when_preferred_track_only_contains_markup(self):
        def respond(request):
            language = request.url.params.get("language")
            if language == "8":
                return httpx.Response(200, json=[{"Time": 1.0, "Caption": "<b></b><br>&nbsp;"}])
            if language == "0":
                return httpx.Response(200, json=[{"Time": 1.0, "Caption": "Backup captions."}])
            return httpx.Response(200, json={"Delivery": DELIVERY})

        requests = self.mock_viewer(respond)
        video = await open_video(COURSE)
        subtitles = await video.subtitles()
        self.assertIsNotNone(subtitles)
        self.assertEqual(subtitles.plain_text, "Backup captions.")
        self.assertEqual([request.url.params.get("language") for request in requests], [None, "8", "0"])

    async def test_sign_in_and_rejected_session_are_distinct(self):
        self.mock_viewer(lambda _: httpx.Response(200, json={"ErrorCode": 2, "LoginRedirect": True}))
        for session, expected in ((None, "panopto_login_required"), (SecretStr("expired"), "panopto_session_rejected")):
            with self.subTest(expected=expected):
                with self.assertRaises(PanoptoError) as error:
                    await open_video(COURSE, panopto_session=session)
                self.assertEqual(error.exception.code, expected)

    async def test_does_not_follow_credentialed_login_redirect(self):
        response = httpx.Response(302, headers={"Location": "https://login.example.test/"})
        requests = self.mock_viewer(lambda _: response)
        with self.assertRaises(PanoptoError):
            await open_video(COURSE, panopto_session=SecretStr("fixture-session"))
        self.assertEqual([request.url.host for request in requests], ["polyu.ap.panopto.com"])

    async def test_invalid_course_url_does_not_contact_the_viewer(self):
        requests = self.mock_viewer(lambda _: httpx.Response(500))
        with self.assertRaises(PanoptoError) as error:
            await open_video(COURSE.replace("https://", "http://", 1))
        self.assertEqual(error.exception.code, "panopto_invalid_url")
        self.assertEqual(requests, [])
