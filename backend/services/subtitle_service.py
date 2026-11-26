"""提取 YouTube、B站和 Panopto 的字幕，统一整理为带时间戳的片段。"""
import asyncio
import json
import logging
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs

from pydantic import SecretStr

from config import YTDLP_PROXY, YTDLP_TIMEOUT
from services.panopto_service import PanoptoVideo, iter_panopto_caption_tracks
from services.subtitle_format import normalize_subtitle_segments
from services.video_platform import identify_platform, split_video_url
from services.video_session import BilibiliSessionError, check_bilibili_login
from services.youtube_network import get_youtube_connection
from services.ytdlp_service import run_ytdlp

logger = logging.getLogger(__name__)

LANG_PRIORITY_YT = ["zh-Hans", "zh", "zh-TW", "en", "en-US"]
LANG_PRIORITY_BILI = ("zh-Hans", "zh-CN", "zh-TW", "zh", "ai-zh", "en", "en-US", "en-GB")

_TIMESTAMP = r"(?:\d{2,}:)?[0-5]\d:[0-5]\d[.,]\d{3}"
_CUE_TIMING = re.compile(rf"^({_TIMESTAMP})\s*-->\s*({_TIMESTAMP})(?=\s|$)")
_VTT_METADATA = re.compile(r"^(?:NOTE|STYLE|REGION)(?:[ \t]|$)")


@dataclass
class SubtitleData:
    plain_text: str
    segments: list[dict]


def _subtitle_data(segments: list[dict]) -> Optional[SubtitleData]:
    segments = normalize_subtitle_segments(segments)
    if not segments:
        return None
    return SubtitleData(" ".join(segment["text"] for segment in segments), segments)


def _timestamp_to_seconds(timestamp: str) -> float:
    seconds = 0.0
    for part in timestamp.replace(",", ".").split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


def _parse_vtt_segments(raw_text: str) -> list[dict]:
    """读取 VTT 或 SRT 的时间和文本，保留换行给后续整理。"""
    segments = []
    timing = None
    text = []
    metadata = False
    for raw_line in raw_text.lstrip("\ufeff").splitlines() + [""]:
        line = raw_line.strip()
        if not line:
            metadata = False
        elif not timing and _VTT_METADATA.match(line):
            metadata = True
        if metadata:
            continue
        next_timing = _CUE_TIMING.match(line)
        if timing and (not line or next_timing):
            if text:
                segments.append({
                    "start_time": _timestamp_to_seconds(timing[1]),
                    "end_time": _timestamp_to_seconds(timing[2]),
                    "text": "\n".join(text),
                })
            timing, text = None, []
        if next_timing:
            timing = next_timing
        elif timing:
            text.append(line)
    return segments


def _parse_bilibili_json_segments(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("body") or data.get("subtitles") or data.get("data")
    if not isinstance(data, list):
        return []
    return [
        {"start_time": row.get("from"), "end_time": row.get("to"), "text": row.get("content") or row.get("text")}
        for row in data
        if isinstance(row, dict)
    ]


async def _download_bilibili_subs(url: str, cookies_file: Optional[Path], output_dir: Path) -> list[Path]:
    command = [
        sys.executable, "-m", "yt_dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-format", "vtt/srt/json",
        "--sub-langs", ",".join(LANG_PRIORITY_BILI),
        "--no-playlist",
        "--no-check-certificates",
        "-o", str(output_dir / "subtitle.%(ext)s"),
    ]
    if cookies_file:
        command.extend(["--cookies", str(cookies_file)])
    if YTDLP_PROXY:
        command.extend(["--proxy", YTDLP_PROXY])

    _, _, stderr = await run_ytdlp(command, url, YTDLP_TIMEOUT + 30)
    files = [path for path in output_dir.iterdir() if path.suffix in {".vtt", ".srt", ".json"}]
    if not files:
        check_bilibili_login(stderr.decode("utf-8", errors="replace"), bool(cookies_file), checking_subtitles=True)

    priority = {language.lower(): index for index, language in enumerate(LANG_PRIORITY_BILI)}
    return sorted(files, key=lambda path: (priority.get(path.stem.rsplit(".", 1)[-1].lower(), len(priority)), path.name))


def _extract_video_id(url: str) -> Optional[str]:
    parsed = split_video_url(url)
    path = parsed.path.strip("/").split("/")
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        video_id = path[0]
    elif path[0] in ("embed", "shorts", "live") and len(path) > 1:
        video_id = path[1]
    else:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    return video_id if re.fullmatch(r"[a-zA-Z0-9_-]{11}", video_id) else None


async def _extract_youtube_subs(url: str) -> Optional[SubtitleData]:
    video_id = _extract_video_id(url)
    if not video_id:
        return None

    connection = await get_youtube_connection()
    try:
        from requests import Session
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig

        def fetch_transcript():
            with Session() as session:
                session.trust_env = False
                proxy = connection.proxy
                proxy_config = GenericProxyConfig(http_url=proxy, https_url=proxy) if proxy else None
                api = YouTubeTranscriptApi(proxy_config=proxy_config, http_client=session)
                return list(api.fetch(video_id, LANG_PRIORITY_YT))

        snippets = await asyncio.to_thread(fetch_transcript)
        return _subtitle_data([
            {"start_time": item.start, "end_time": item.start + item.duration, "text": item.text}
            for item in snippets
        ])
    except Exception as error:
        logger.info("YouTube 字幕提取未完成: %s", type(error).__name__)
        return None


async def _extract_bilibili_subs(url: str, cookies: Optional[str] = None) -> Optional[SubtitleData]:
    with tempfile.TemporaryDirectory(prefix="bili_subs_") as directory:
        output_dir = Path(directory)
        cookies_file = None
        if cookies:
            cookies_file = output_dir / "session.txt"
            cookies_file.write_text(cookies, encoding="utf-8")

        try:
            for path in await _download_bilibili_subs(url, cookies_file, output_dir):
                try:
                    if path.suffix == ".json":
                        segments = _parse_bilibili_json_segments(path)
                    else:
                        segments = _parse_vtt_segments(path.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError):
                    continue
                subtitles = _subtitle_data(segments)
                if subtitles:
                    return subtitles
        except BilibiliSessionError:
            raise
        except Exception as error:
            logger.warning("B站字幕提取未完成: %s", type(error).__name__)
    return None


async def extract_panopto_subtitle_text(
    video: PanoptoVideo,
    session: Optional[SecretStr],
) -> Optional[SubtitleData]:
    async for segments in iter_panopto_caption_tracks(video, session):
        subtitles = _subtitle_data(segments)
        if subtitles:
            return subtitles
    return None


async def extract_subtitle_text(url: str, cookies: Optional[str] = None) -> Optional[SubtitleData]:
    platform = identify_platform(url)
    if platform == "youtube":
        return await _extract_youtube_subs(url)
    if platform == "bilibili":
        return await _extract_bilibili_subs(url, cookies)
    return None
