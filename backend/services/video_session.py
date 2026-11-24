"""视频平台会话值校验及 yt-dlp 的 B站会话适配。"""

import re
from typing import Optional

from pydantic import SecretStr


COOKIE_VALUE = re.compile(r"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]{1,8192}")
BILIBILI_LOGIN_FAILURE = re.compile(
    r"\bHTTP Error (?:401|403|412)\b|this video is only available for registered users"
    r"|you need to log ?in|login required",
    re.IGNORECASE,
)
BILIBILI_SUBTITLE_LOGIN_WARNING = "subtitles are only available when logged in"


class BilibiliSessionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def session_cookie_value(session: SecretStr) -> Optional[str]:
    value = session.get_secret_value().strip()
    return value if COOKIE_VALUE.fullmatch(value) else None


def cookies_for_video(
    platform: str,
    cookies: Optional[str],
    bilibili_session: Optional[SecretStr],
) -> Optional[str]:
    """旧 API 仍可传 Netscape 文本。新版只提交对应站点的会话值。"""
    if platform != "bilibili" or bilibili_session is None:
        return cookies
    value = session_cookie_value(bilibili_session)
    if value is None:
        raise BilibiliSessionError(
            "bilibili_session_rejected",
            "请复制 B站 Cookie 面板中 SESSDATA 这一行的值。",
        )
    # 只允许向 B站域名的 HTTPS 请求发送此会话。
    return f"# Netscape HTTP Cookie File\n#HttpOnly_.bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\t{value}\n"


def check_bilibili_login(stderr: str, has_cookies: bool, *, checking_subtitles: bool = False) -> None:
    subtitle_warning = checking_subtitles and BILIBILI_SUBTITLE_LOGIN_WARNING in stderr.lower()
    if not subtitle_warning and not BILIBILI_LOGIN_FAILURE.search(stderr):
        return
    if has_cookies:
        raise BilibiliSessionError(
            "bilibili_session_rejected",
            "B站拒绝了这次请求。请确认官方页面可以播放，并复制当前会话值重试。",
        )
    raise BilibiliSessionError(
        "bilibili_login_required",
        "B站需要浏览器会话才能继续这次请求，请登录后连接会话。",
    )
