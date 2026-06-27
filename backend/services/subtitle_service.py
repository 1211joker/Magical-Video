"""
字幕提取服务 — 从视频中提取字幕文本。

YouTube → youtube-transcript-api（专门提取字幕，不受 yt-dlp PO Token 限制）
B站     → yt-dlp 获取字幕 URL → 下载 VTT → 解析
"""
import asyncio
import subprocess
import sys
import os
import tempfile
import re
from typing import Optional
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


def _download_bilibili_subs_sync(url: str, cookies_file: Optional[str], output_dir: str) -> Optional[str]:
    """
    同步方法：用 yt-dlp --write-subs 下载 B站 字幕文件到 output_dir。

    返回下载的字幕文件路径，无字幕时返回 None。
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--skip-download",           # 不下载视频
        "--write-subs",              # 下载手动字幕
        "--write-auto-subs",         # 下载自动生成字幕
        "--sub-format", "vtt",       # 要 VTT 格式
        "--sub-langs", "zh-Hans,zh-CN,zh-TW,zh,ai-zh,en",
        "--no-playlist",
        "--no-check-certificates",
        "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
        url
    ]
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    if YTDLP_PROXY:
        cmd.extend(["--proxy", YTDLP_PROXY])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=YTDLP_TIMEOUT + 30)

    # yt-dlp 返回非 0 也可能成功下载了字幕（视频格式不可用但字幕OK）
    # 所以不检查 returncode，直接找字幕文件

    # 在 output_dir 中找 .vtt 文件，按语言优先级排序
    vtt_files = []
    for fname in os.listdir(output_dir):
        if fname.endswith(".vtt"):
            fpath = os.path.join(output_dir, fname)
            vtt_files.append(fpath)

    if not vtt_files:
        return None

    # 按文件名中的语言优先级排序（中文优先）
    def lang_priority(fpath: str) -> int:
        name = os.path.basename(fpath).lower()
        for i, lp in enumerate(LANG_PRIORITY_BILI):
            if re.search(lp, name, re.IGNORECASE):
                return i
        return 99  # 未知语言排最后

    vtt_files.sort(key=lang_priority)
    return vtt_files[0]  # 返回优先级最高的


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
    """
    用 yt-dlp 下载 B站 字幕（--write-subs + --write-auto-subs）。

    流程：
    1. 创建临时目录
    2. yt-dlp 下载字幕 .vtt 文件到临时目录
    3. 读取并解析 VTT → 纯文本
    4. 清理临时目录和 cookies 文件
    """
    cookies_file = None
    if cookies:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(cookies)
        tmp.close()
        cookies_file = tmp.name

    output_dir = tempfile.mkdtemp(prefix="bili_subs_")

    try:
        # 同步下载字幕（在线程池中执行，不阻塞事件循环）
        vtt_path = await asyncio.to_thread(
            _download_bilibili_subs_sync, url, cookies_file, output_dir
        )

        if not vtt_path:
            return None

        # 读取 VTT 文件
        with open(vtt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        plain = _parse_vtt(raw_text)
        if not plain or len(plain) < 10:
            return None

        return plain

    except Exception:
        # yt-dlp 执行失败或字幕下载失败 → 当作无字幕处理
        return None

    finally:
        # 清理 cookies 临时文件
        if cookies_file and os.path.exists(cookies_file):
            os.unlink(cookies_file)
        # 清理字幕临时目录
        import shutil
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


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
