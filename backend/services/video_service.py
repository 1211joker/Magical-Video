"""为解析和分析流程提供统一的视频入口。"""

from dataclasses import dataclass, field
from typing import Optional

from pydantic import SecretStr

from models.schemas import ParseResponse
from services.panopto_service import PanoptoVideo, get_panopto_video
from services.subtitle_service import SubtitleData, extract_panopto_subtitle_text, extract_subtitle_text
from services.video_platform import identify_platform
from services.video_session import cookies_for_video
from services.ytdlp_service import parse_video_info


@dataclass(frozen=True)
class VideoSource:
    url: str
    info: ParseResponse
    panopto: Optional[PanoptoVideo] = None
    cookies: Optional[str] = field(default=None, repr=False)
    panopto_session: Optional[SecretStr] = field(default=None, repr=False)

    async def subtitles(self) -> Optional[SubtitleData]:
        if self.panopto is not None:
            return await extract_panopto_subtitle_text(self.panopto, self.panopto_session)
        return await extract_subtitle_text(self.url, self.cookies)


async def open_video(
    url: str,
    cookies: Optional[str] = None,
    panopto_session: Optional[SecretStr] = None,
    bilibili_session: Optional[SecretStr] = None,
) -> VideoSource:
    platform = identify_platform(url)
    if platform == "panopto":
        video = await get_panopto_video(url, panopto_session)
        return VideoSource(url, video.info(), panopto=video, panopto_session=panopto_session)
    video_cookies = cookies_for_video(platform, cookies, bilibili_session)
    return VideoSource(url, await parse_video_info(url, video_cookies), cookies=video_cookies)
