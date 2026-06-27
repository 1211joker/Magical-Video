"""
字幕提取服务 — 从视频中提取字幕文本。

YouTube → youtube-transcript-api（专门提取字幕，不受 yt-dlp PO Token 限制）
B站     → yt-dlp 获取字幕 URL → 下载 VTT → 解析
"""
import json
import asyncio
import subprocess
import sys
import os
import tempfile
import re
from typing import Optional
import httpx
from config import YTDLP_PROXY, YTDLP_TIMEOUT


# 字幕语言优先级
LANG_PRIORITY_YT = ["zh-Hans", "zh", "zh-TW", "en", "en-US"]
LANG_PRIORITY_BILI = [r"zh-Hans", r"zh-CN", r"zh-TW", r"zh", r"en", r"en-US", r"en-GB"]


def _extract_video_id(url: str) -> Optional[str]:
    """从 YouTube URL 提取 video ID"""
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def _extract_youtube_subs(url: str) -> Optional[str]:
    """用 youtube-transcript-api 提取 YouTube 字幕"""
    video_id = _extract_video_id(url)
    if not video_id:
        return None

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript = await asyncio.to_thread(
            api.fetch, video_id, LANG_PRIORITY_YT
        )
        # transcript 是一个可迭代对象（FetchedTranscript）
        snippets = list(transcript)
        if not snippets:
            return None
        texts = [s.text for s in snippets if s.text.strip()]
        return " ".join(texts)
    except Exception:
        # youtube-transcript-api 可能因为各种原因失败（无字幕、被封等）
        return None


def _get_bilibili_sub_urls(url: str, cookies_file: Optional[str] = None) -> dict:
    """
    同步方法：用 yt-dlp --dump-json 获取 B站 字幕信息。
    B站 不受 YouTube PO Token 限制，yt-dlp 可以正常获取。
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-playlist",
        "--flat-playlist",
        "--no-check-certificates",
        url
    ]
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    if YTDLP_PROXY:
        cmd.extend(["--proxy", YTDLP_PROXY])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=YTDLP_TIMEOUT)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 执行失败: {result.stderr[:200]}")

    data = json.loads(result.stdout)
    return {
        "subtitles": data.get("subtitles", {}) or {},
        "automatic_captions": data.get("automatic_captions", {}) or {},
    }


def _pick_best_subtitle(sub_data: dict) -> Optional[dict]:
    """从字幕数据中按优先级选中最佳字幕"""
    manual = sub_data.get("subtitles", {})
    auto = sub_data.get("automatic_captions", {})

    # 先找手动字幕
    for lang_pattern in LANG_PRIORITY_BILI:
        for lang_key in manual:
            if re.search(lang_pattern, lang_key, re.IGNORECASE):
                return {
                    "url": manual[lang_key][0]["url"],
                    "ext": manual[lang_key][0].get("ext", "vtt"),
                    "lang": lang_key,
                }

    # 再找自动生成字幕
    for lang_pattern in LANG_PRIORITY_BILI:
        for lang_key in auto:
            if re.search(lang_pattern, lang_key, re.IGNORECASE):
                return {
                    "url": auto[lang_key][0]["url"],
                    "ext": auto[lang_key][0].get("ext", "vtt"),
                    "lang": f"{lang_key}（自动生成）",
                }

    return None


def _parse_vtt(text: str) -> str:
    """
    将 VTT/SRT 字幕内容解析为纯文本。
    去掉：WEBVTT 头部、时间戳、HTML 标签、序号、空行。
    """
    lines = text.split("\n")
    result = []
    in_header = True
    seen = set()

    for line in lines:
        stripped = line.strip()

        # 跳过 WEBVTT 头部
        if in_header:
            if stripped == "WEBVTT" or stripped.startswith("Kind:") or stripped.startswith("Language:"):
                continue
            if stripped == "":
                in_header = False
                continue
            if stripped.startswith("::"):
                continue

        # 跳过空行
        if not stripped:
            continue

        # 跳过时间戳行
        if re.match(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}", stripped):
            continue

        # 跳过纯数字序号行
        if stripped.isdigit():
            continue

        # 去掉 HTML 标签和 VTT 标签
        cleaned = re.sub(r"<[^>]+>", "", stripped)
        cleaned = re.sub(r"</?c[^>]*>", "", cleaned)

        # 跳过 cue settings 行
        if cleaned.startswith("align:") or cleaned.startswith("position:") or cleaned.startswith("size:"):
            continue

        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)

    return " ".join(result)


async def _extract_bilibili_subs(url: str, cookies: Optional[str] = None) -> Optional[str]:
    """用 yt-dlp 提取 B站 字幕"""
    cookies_file = None
    if cookies:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(cookies)
        tmp.close()
        cookies_file = tmp.name

    try:
        sub_data = await asyncio.to_thread(_get_bilibili_sub_urls, url, cookies_file)
        best = _pick_best_subtitle(sub_data)
        if not best:
            return None

        # 下载字幕文件
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(best["url"], headers=headers)
            if resp.status_code != 200:
                return None
            raw_text = resp.text

        plain = _parse_vtt(raw_text)
        if not plain or len(plain) < 10:
            return None

        return plain

    finally:
        if cookies_file and os.path.exists(cookies_file):
            os.unlink(cookies_file)


async def extract_subtitle_text(
    url: str,
    cookies: Optional[str] = None,
) -> Optional[str]:
    """
    提取视频字幕的纯文本，自动根据平台选择最佳方式。

    - YouTube → youtube-transcript-api（专用字幕库）
    - B站 → yt-dlp（下载 + 解析 VTT）

    返回字幕文本，无字幕时返回 None。
    """
    # 判断平台
    if re.search(r"youtube\.com|youtu\.be", url, re.IGNORECASE):
        return await _extract_youtube_subs(url)

    if re.search(r"bilibili\.com|b23\.tv", url, re.IGNORECASE):
        return await _extract_bilibili_subs(url, cookies)

    # 其他平台暂不支持字幕
    return None
