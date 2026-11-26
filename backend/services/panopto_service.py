"""理大 Panopto 播放器的课程信息、字幕和官方文件下载入口。"""

import math
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from uuid import UUID

import httpx
from pydantic import SecretStr

from models.schemas import FormatInfo, ParseResponse
from services.video_platform import PANOPTO_HOST
from services.video_session import session_cookie_value


ORIGIN = f"https://{PANOPTO_HOST}"
VIEWER_PATH = "/Panopto/Pages/Viewer.aspx"
DELIVERY_URL = f"{ORIGIN}/Panopto/Pages/Viewer/DeliveryInfo.aspx"
DOWNLOAD_DOMAINS = ("panopto.com", "panopto.eu", "cloudfront.net", "amazonaws.com")
# Panopto 语言编号。其他语言保留播放器提供的顺序。
LANGUAGE_PRIORITY = (8, 9, 0, 1, 15)
DELIVERY_PARAMS = {
    "invocationId": "",
    "isLiveNotes": "false",
    "refreshAuthCookie": "false",
    "isActiveBroadcast": "false",
    "isEditing": "false",
    "isKollectiveAgentInstalled": "false",
    "isEmbed": "false",
}


class PanoptoError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PanoptoVideo:
    delivery_id: str
    title: str
    duration: float
    description: str
    caption_languages: tuple[Optional[int], ...]
    download_url: Optional[str] = field(repr=False)

    def info(self) -> ParseResponse:
        query = urlencode({"id": self.delivery_id})
        thumbnail_query = urlencode({"objectId": self.delivery_id, "mode": "Delivery"})
        formats = [FormatInfo(format_id="best", resolution="Panopto 官方版", ext="mp4")] if self.download_url else []
        return ParseResponse(
            platform="panopto",
            title=self.title,
            duration=int(self.duration),
            description=self.description,
            webpage_url=f"{ORIGIN}{VIEWER_PATH}?{query}",
            thumbnail=f"{ORIGIN}/Panopto/Services/FrameGrabber.svc/FrameRedirect?{thumbnail_query}",
            has_captions=bool(self.caption_languages),
            formats=formats,
        )


def _video_id(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        ids = parse_qs(parsed.query).get("id", [])
        if (
            parsed.scheme == "https"
            and parsed.netloc.lower() in (PANOPTO_HOST, f"{PANOPTO_HOST}:443")
            and parsed.path.lower() in (VIEWER_PATH.lower(), "/panopto/pages/embed.aspx")
            and len(ids) == 1
        ):
            video_id = str(UUID(ids[0]))
            if ids[0].lower() == video_id:
                return video_id
    except ValueError:
        pass
    raise PanoptoError("panopto_invalid_url", "请粘贴理大 Panopto 的 HTTPS 课程录像链接。")


def _download_url(value) -> Optional[str]:
    if not isinstance(value, str) or not value or re.search(r"[\s\\]", value):
        return None
    try:
        url = urljoin(f"{ORIGIN}{VIEWER_PATH}", value)
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and any(host == domain or host.endswith("." + domain) for domain in DOWNLOAD_DOMAINS)
        ):
            return url
    except ValueError:
        pass
    return None


def _login_error(session: Optional[SecretStr]) -> PanoptoError:
    if session is None:
        return PanoptoError("panopto_login_required", "这段课程录像需要先在理大 Panopto 登录。")
    return PanoptoError(
        "panopto_session_rejected",
        "Panopto 未接受当前会话。请在官方页面确认这个账号能播放录像，再连接新的会话。",
    )


async def _viewer_data(video_id: str, params: dict[str, str], session: Optional[SecretStr]):
    headers = {"Accept": "application/json"}
    if session is not None:
        cookie = session_cookie_value(session)
        if cookie is None:
            raise _login_error(session)
        headers["Cookie"] = f".ASPXAUTH={cookie}"
    # 仅向固定的理大播放器入口发送会话。登录跳转交给用户浏览器。
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(
                DELIVERY_URL,
                params={"deliveryId": video_id, "responseType": "json", **params},
                headers=headers,
            )
    except httpx.RequestError as error:
        raise PanoptoError("panopto_network_unavailable", "服务端暂时无法连接理大 Panopto，请稍后重试。") from error

    if response.is_redirect or response.status_code in (401, 403):
        raise _login_error(session)
    if response.status_code >= 500:
        raise PanoptoError("panopto_network_unavailable", "理大 Panopto 暂时无法响应，请稍后重试。")
    if response.status_code != 200:
        raise PanoptoError("panopto_unavailable", "Panopto 录像暂时不可用，请在官方页面确认链接。")
    try:
        data = response.json()
    except ValueError as error:
        raise PanoptoError("panopto_unavailable", "Panopto 返回了无法读取的数据，请稍后重试。") from error

    if isinstance(data, dict) and (data.get("ErrorCode") == 2 or data.get("LoginRedirect") is True):
        raise _login_error(session)
    if isinstance(data, dict) and data.get("ErrorCode"):
        raise PanoptoError("panopto_unavailable", "Panopto 录像暂时不可用，请在官方页面确认链接。")
    return data


def _number(value) -> Optional[float]:
    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
        return float(value)
    return None


def _caption_languages(delivery: dict) -> tuple[Optional[int], ...]:
    if not delivery.get("HasCaptions"):
        return ()
    languages = delivery.get("AvailableLanguages")
    if not isinstance(languages, list):
        return (None,)
    valid = dict.fromkeys(lang for lang in languages if type(lang) is int or lang is None)
    priority = [lang for lang in LANGUAGE_PRIORITY if lang in valid]
    priority.extend(lang for lang in valid if lang not in LANGUAGE_PRIORITY)
    return tuple(priority) or (None,)


async def get_panopto_video(url: str, session: Optional[SecretStr] = None) -> PanoptoVideo:
    video_id = _video_id(url)
    payload = await _viewer_data(video_id, DELIVERY_PARAMS, session)
    delivery = payload.get("Delivery") if isinstance(payload, dict) else None
    if not isinstance(delivery, dict) or not delivery.get("SessionName"):
        raise PanoptoError("panopto_unavailable", "Panopto 录像暂时不可用，请在官方页面确认链接。")
    return PanoptoVideo(
        delivery_id=video_id,
        title=delivery["SessionName"],
        duration=_number(delivery.get("Duration")) or 0.0,
        description=(delivery.get("SessionAbstract") or "")[:500],
        caption_languages=_caption_languages(delivery),
        # 播放流即使存在也不代表可下载。播放器单独提供 DownloadUrl。
        download_url=_download_url(payload.get("DownloadUrl")),
    )


def _caption_segments(rows: list, video_duration: float) -> list:
    cues = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = _number(row.get("Time"))
        caption = row.get("Caption")
        if start is None or not isinstance(caption, str):
            continue
        if caption.strip():
            duration = _number(row.get("CaptionDuration")) or _number(row.get("Duration"))
            cues.append((start, duration, caption))

    cues.sort(key=lambda cue: cue[0])
    segments = []
    for index, (start, duration, caption) in enumerate(cues):
        if duration:
            end = start + duration
        else:
            end = cues[index + 1][0] if index + 1 < len(cues) else video_duration
        segments.append({"start_time": start, "end_time": max(start, end), "text": caption})
    return segments


async def get_panopto_captions(video: PanoptoVideo, session: Optional[SecretStr] = None) -> list:
    for language in video.caption_languages:
        params = {"getCaptions": "true"}
        if language is not None:
            params["language"] = str(language)
        rows = await _viewer_data(video.delivery_id, params, session)
        if isinstance(rows, list):
            segments = _caption_segments(rows, video.duration)
            if segments:
                return segments
    return []
