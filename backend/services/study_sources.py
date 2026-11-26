"""视频标识和字幕快照。供归档、索引与原文展示共用。"""

from math import isfinite
import re
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from models.schemas import SubtitleSegment
from services.video_platform import PANOPTO_HOST, identify_platform

YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
BILIBILI_ID = re.compile(r"/video/((?i:BV)[A-Za-z0-9]+|av[0-9]+)/?$")
BILIBILI_SHORT = re.compile(r"/[A-Za-z0-9]+/?$")
MAX_CHUNK_CHARS = 650


def video_link(raw_url: str) -> tuple[str, str, str]:
    """只保留指向视频所需的字段，允许 B站短链接待平台解析后归档。"""
    url = raw_url.strip()
    if "://" not in url:
        url = "https://" + url.lstrip("/")
    platform = identify_platform(url)
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or parts.username or parts.password or parts.port:
        raise ValueError("请使用平台的视频网页链接")
    query = parse_qs(parts.query)

    if platform == "youtube":
        if parts.hostname == "youtu.be" or parts.path.startswith(("/shorts/", "/embed/", "/live/")):
            video_id = parts.path.rstrip("/").rsplit("/", 1)[-1]
        else:
            video_id = query.get("v", [""])[0]
        if YOUTUBE_ID.fullmatch(video_id):
            return platform, video_id, f"https://www.youtube.com/watch?v={video_id}"
    elif platform == "bilibili":
        part = query.get("p", ["1"])[0]
        if not re.fullmatch(r"[1-9][0-9]{0,4}", part):
            raise ValueError("B站分 P 编号无效")
        match = BILIBILI_ID.fullmatch(parts.path)
        suffix = f"?p={part}" if part != "1" else ""
        if match:
            video_id = match[1]
            if video_id.lower().startswith("bv"):
                video_id = "BV" + video_id[2:]
            return platform, f"{video_id}:{part}", f"https://www.bilibili.com/video/{video_id}{suffix}"
        if parts.hostname == "b23.tv" and BILIBILI_SHORT.fullmatch(parts.path):
            return platform, "", f"https://b23.tv{parts.path.rstrip('/')}{suffix}"
    elif platform == "panopto" and parts.path.lower() == "/panopto/pages/viewer.aspx":
        try:
            video_id = str(UUID(query["id"][0]))
        except (KeyError, ValueError):
            raise ValueError("Panopto 视频编号无效") from None
        return platform, video_id, f"https://{PANOPTO_HOST}/Panopto/Pages/Viewer.aspx?{urlencode({'id': video_id})}"
    raise ValueError("暂不支持此视频链接，请使用 YouTube、B站或理大 Panopto 的单视频页面")


def archive_identity(request_url: str, webpage_url: str) -> tuple[str, str, str]:
    platform, original_id, original_url = video_link(request_url)
    try:
        resolved_platform, resolved_id, resolved_url = video_link(webpage_url)
    except ValueError:
        resolved_platform, resolved_id, resolved_url = "", "", ""
    if resolved_platform == platform and resolved_id:
        if platform == "bilibili" and "?p=" in original_url:
            part = original_url.split("?p=", 1)[1]
            resolved_id = f"{resolved_id.rsplit(':', 1)[0]}:{part}"
            resolved_url = f"{resolved_url.split('?', 1)[0]}?p={part}"
        return platform, resolved_id, resolved_url
    if original_id:
        return platform, original_id, original_url
    raise ValueError("无法取得视频的稳定标识，请使用完整的视频网页链接")


def normalized_segments(items: list) -> list[dict]:
    segments = []
    for value in items:
        item = SubtitleSegment.model_validate(value)
        text = " ".join(item.text.split())
        if text and isfinite(item.start_time) and isfinite(item.end_time) and 0 <= item.start_time <= item.end_time:
            segments.append({"start_time": item.start_time, "end_time": item.end_time, "text": text})
    return sorted(segments, key=lambda item: (item["start_time"], item["end_time"]))


def subtitle_chunks(segments: list[dict]):
    """优先沿字幕边界分段，特别长的单条字幕沿用原来的时间区间。"""
    group = []
    size = 0
    for segment in segments:
        text = segment["text"]
        for start in range(0, len(text), MAX_CHUNK_CHARS):
            excerpt = text[start:start + MAX_CHUNK_CHARS]
            if group and (size + len(excerpt) + 1 > MAX_CHUNK_CHARS
                          or segment["end_time"] - group[0]["start_time"] > 45):
                yield _chunk(group)
                # 相邻片段保留最近一条短字幕，便于召回跨边界句子。
                tail = group[-1]
                group = [tail] if len(group) > 1 and len(tail["text"]) <= 90 else []
                size = len(tail["text"]) if group else 0
                if size + len(excerpt) + 1 > MAX_CHUNK_CHARS:
                    group = []
                    size = 0
            group.append({**segment, "text": excerpt})
            size += len(excerpt) + 1
    if group:
        yield _chunk(group)


def _chunk(group: list[dict]) -> dict:
    return {
        "start_time": group[0]["start_time"],
        "end_time": max(item["end_time"] for item in group),
        "text": " ".join(item["text"] for item in group),
    }
