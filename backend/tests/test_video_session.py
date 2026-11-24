import io
import unittest
from unittest.mock import patch

from pydantic import SecretStr
from yt_dlp.cookies import YoutubeDLCookieJar

from models.schemas import ParseResponse
from services.download_service import prepare_download
from services.video_service import open_video
from services.video_session import BilibiliSessionError, check_bilibili_login, cookies_for_video


BILIBILI = "https://www.bilibili.com/video/BV13x41117TL"
SESSION = SecretStr("fixture%2Cauth%3D")


class VideoSessionTests(unittest.IsolatedAsyncioTestCase):
    def test_cookie_jar_only_sends_session_to_https_bilibili(self):
        data = cookies_for_video("bilibili", None, SESSION)
        jar = YoutubeDLCookieJar(io.StringIO(data))
        jar.load(ignore_discard=True)
        self.assertEqual(jar.get_cookie_header(BILIBILI), "SESSDATA=fixture%2Cauth%3D")
        self.assertEqual(jar.get_cookie_header("https://api.bilibili.com/"), "SESSDATA=fixture%2Cauth%3D")
        self.assertIsNone(jar.get_cookie_header("http://www.bilibili.com/"))
        self.assertIsNone(jar.get_cookie_header("https://www.bilibili.com.example.test/"))
        self.assertIsNone(cookies_for_video("youtube", None, SESSION))

    def test_invalid_session_is_rejected_before_generating_a_cookie_jar(self):
        for value in ("", "SESSDATA=example; other=example", "example\tother"):
            with self.subTest(value=value):
                with self.assertRaises(BilibiliSessionError) as error:
                    cookies_for_video("bilibili", None, SecretStr(value))
                self.assertEqual(error.exception.code, "bilibili_session_rejected")

    def test_legacy_cookie_text_is_supported(self):
        data = "# Netscape HTTP Cookie File\n.bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tlegacy-fixture\n"
        self.assertEqual(cookies_for_video("bilibili", data, None), data)

    def test_subtitle_warning_requests_login_without_reclassifying_other_errors(self):
        warning = "Subtitles are only available when logged in."
        check_bilibili_login(warning, False)
        check_bilibili_login("HTTP Error 429", True, checking_subtitles=True)
        for has_cookies, expected in ((False, "bilibili_login_required"), (True, "bilibili_session_rejected")):
            with self.subTest(has_cookies=has_cookies):
                with self.assertRaises(BilibiliSessionError) as error:
                    check_bilibili_login(warning, has_cookies, checking_subtitles=True)
                self.assertEqual(error.exception.code, expected)

    async def test_parse_captions_and_download_receive_the_same_cookie_data(self):
        response = ParseResponse(platform="bilibili", title="Fixture", duration=0, thumbnail="",
                                 description="", webpage_url=BILIBILI)
        data = cookies_for_video("bilibili", None, SESSION)
        with patch("services.video_service.parse_video_info", return_value=response) as parse, \
             patch("services.video_service.extract_subtitle_text", return_value=None) as captions, \
             patch("services.download_service.download_video") as download:
            video = await open_video(BILIBILI, bilibili_session=SESSION)
            await video.subtitles()
            await prepare_download(BILIBILI, "best", None, bilibili_session=SESSION)
        parse.assert_awaited_once_with(BILIBILI, data)
        captions.assert_awaited_once_with(BILIBILI, data)
        download.assert_awaited_once_with(BILIBILI, "best", data)
