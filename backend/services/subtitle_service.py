"""
字幕提取服务 — 从视频中提取字幕文本。

YouTube → youtube-transcript-api（专门提取字幕，不受 yt-dlp PO Token 限制）
B站     → yt-dlp 获取字幕文件 → 解析 VTT/JSON → 提取片段

返回 SubtitleData：
  - plain_text: 纯文本（给 AI 分析用）
  - segments:   [{start_time, end_time, text}, ...]（给前端展示用）
"""
import asyncio
import subprocess
import sys
import os
import tempfile
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from config import YTDLP_PROXY, YTDLP_TIMEOUT

logger = logging.getLogger(__name__)


# 字幕语言优先级
LANG_PRIORITY_YT = ["zh-Hans", "zh", "zh-TW", "en", "en-US"]
LANG_PRIORITY_BILI = [r"zh-Hans", r"zh-CN", r"zh-TW", r"zh", r"en", r"en-US", r"en-GB"]


@dataclass
class SubtitleData:
    """字幕提取结果：纯文本（AI用）+ 结构化片段（前端展示用）"""
    plain_text: str
    segments: list = field(default_factory=list)


# ========== 工具函数 ==========

def _timestamp_to_seconds(ts: str) -> float:
    """将 VTT/SRT 时间戳 "HH:MM:SS.mmm" 或 "MM:SS.mmm" 转为浮点秒数"""
    parts = ts.replace(',', '.').strip().split(':')
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return 0.0


def _segments_to_plain_text(segments: list) -> str:
    """将片段列表拼接为纯文本（空格分隔）"""
    return " ".join(s.get("text", "") if isinstance(s, dict) else s.text for s in segments)


# ========== VTT / SRT 解析（保留时间戳） ==========

def _parse_vtt_segments(raw_text: str) -> list:
    """
    将 VTT/SRT 字幕内容解析为带时间戳的片段列表。

    返回: [{"start_time": 1.0, "end_time": 4.5, "text": "大家好"}, ...]
    """
    lines = raw_text.split("\n")
    segments = []
    in_header = True
    current_start = None
    current_end = None
    current_texts = []

    # 时间戳正则（VTT 用 . 分隔毫秒，SRT 用 , 分隔）
    ts_pattern = re.compile(
        r"^(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})"
    )

    for line in lines:
        stripped = line.strip()

        # 跳过 WEBVTT 头部
        if in_header:
            if stripped in ("WEBVTT", "") or stripped.startswith(("Kind:", "Language:", "::")):
                if stripped == "":
                    in_header = False
                continue
            in_header = False

        # 空行 → 可能表示一个字幕块的结束
        if not stripped:
            if current_start is not None and current_texts:
                text = " ".join(current_texts)
                text = re.sub(r"<[^>]+>", "", text)  # 去 HTML 标签
                text = re.sub(r"</?c[^>]*>", "", text)
                if text.strip():
                    segments.append({
                        "start_time": current_start,
                        "end_time": current_end,
                        "text": text.strip()
                    })
                current_start = None
                current_end = None
                current_texts = []
            continue

        # 时间戳行
        m = ts_pattern.match(stripped)
        if m:
            # 保存上一个片段
            if current_start is not None and current_texts:
                text = " ".join(current_texts)
                text = re.sub(r"<[^>]+>", "", text)
                text = re.sub(r"</?c[^>]*>", "", text)
                if text.strip():
                    segments.append({
                        "start_time": current_start,
                        "end_time": current_end,
                        "text": text.strip()
                    })

            current_start = _timestamp_to_seconds(m.group(1))
            current_end = _timestamp_to_seconds(m.group(2))
            current_texts = []
            continue

        # 跳过纯数字序号行（SRT）
        if stripped.isdigit():
            continue

        # 跳过 cue settings
        if stripped.startswith(("align:", "position:", "size:")):
            continue

        # 文本行
        if current_start is not None:
            cleaned = re.sub(r"<[^>]+>", "", stripped)
            cleaned = re.sub(r"</?c[^>]*>", "", cleaned)
            if cleaned:
                current_texts.append(cleaned)

    # 处理最后一个片段
    if current_start is not None and current_texts:
        text = " ".join(current_texts)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"</?c[^>]*>", "", text)
        if text.strip():
            segments.append({
                "start_time": current_start,
                "end_time": current_end,
                "text": text.strip()
            })

    return segments


# ========== B站 JSON 字幕解析（保留时间戳） ==========

def _parse_bilibili_json_segments(filepath: str) -> list:
    """
    解析 B站 原生 JSON 字幕文件，返回带时间戳的片段列表。

    B站字幕格式: [{"from": 1.0, "to": 3.5, "content": "你好"}, ...]
    """
    import json as _json
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = _json.load(f)
    except Exception:
        return []

    # 支持多种 JSON 结构
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        body = data.get("body") or data.get("subtitles") or data.get("data") or []
        items = body if isinstance(body, list) else []
    else:
        return []

    segments = []
    for item in items:
        if isinstance(item, dict):
            content = (item.get("content") or item.get("text") or "").strip()
            if content:
                segments.append({
                    "start_time": float(item.get("from", 0)),
                    "end_time": float(item.get("to", 0)),
                    "text": content
                })

    return segments


# ========== yt-dlp 字幕下载（B站） ==========

def _download_bilibili_subs_sync(url: str, cookies_file: Optional[str], output_dir: str) -> Optional[str]:
    """
    同步方法：用 yt-dlp --write-subs 下载 B站 字幕文件到 output_dir。

    返回下载的字幕文件路径，无字幕时返回 None。
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-format", "vtt/srt/ass/json",
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

    logger.info(f"[B站字幕] 执行 yt-dlp 命令...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=YTDLP_TIMEOUT + 30)

    logger.info(f"[B站字幕] yt-dlp returncode={result.returncode}")
    if result.stderr:
        stderr_tail = result.stderr.strip().split('\n')[-10:]
        logger.info(f"[B站字幕] stderr (tail):\n{chr(10).join(stderr_tail)}")

    all_files = os.listdir(output_dir)
    logger.info(f"[B站字幕] 输出目录文件 ({len(all_files)} 个): {all_files}")

    SUB_EXTENSIONS = ('.vtt', '.srt', '.ass', '.json')
    sub_files = []
    for fname in all_files:
        if fname.endswith(SUB_EXTENSIONS):
            sub_files.append(os.path.join(output_dir, fname))

    if not sub_files:
        logger.warning(f"[B站字幕] 未找到任何字幕文件")
        return None

    logger.info(f"[B站字幕] 找到 {len(sub_files)} 个字幕文件")

    # 按语言优先级排序（中文优先）
    def lang_priority(fpath: str) -> int:
        name = os.path.basename(fpath).lower()
        for i, lp in enumerate(LANG_PRIORITY_BILI):
            if re.search(lp, name, re.IGNORECASE):
                return i
        return 99

    sub_files.sort(key=lang_priority)
    return sub_files[0]


# ========== 平台字幕提取 ==========

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


async def _extract_youtube_subs(url: str) -> Optional[SubtitleData]:
    """用 youtube-transcript-api 提取 YouTube 字幕（保留时间戳）"""
    video_id = _extract_video_id(url)
    if not video_id:
        return None

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # 配置代理：国内网络需代理才能访问 YouTube 字幕 API
        proxy_config = None
        if YTDLP_PROXY:
            from youtube_transcript_api.proxies import GenericProxyConfig
            proxy_config = GenericProxyConfig(http_url=YTDLP_PROXY, https_url=YTDLP_PROXY)
        api = YouTubeTranscriptApi(proxy_config=proxy_config)
        transcript = await asyncio.to_thread(
            api.fetch, video_id, LANG_PRIORITY_YT
        )
        snippets = list(transcript)
        if not snippets:
            return None

        segments = []
        for s in snippets:
            text = s.text.strip()
            if text:
                segments.append({
                    "start_time": s.start,
                    "end_time": s.start + s.duration,
                    "text": text
                })

        if not segments:
            return None

        plain = _segments_to_plain_text(segments)
        return SubtitleData(plain_text=plain, segments=segments)

    except Exception:
        return None


async def _extract_bilibili_subs(url: str, cookies: Optional[str] = None) -> Optional[SubtitleData]:
    """
    用 yt-dlp 下载 B站 字幕文件，解析为带时间戳的片段。

    返回 SubtitleData（plain_text + segments），失败时返回 None。
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
        sub_path = await asyncio.to_thread(
            _download_bilibili_subs_sync, url, cookies_file, output_dir
        )

        if not sub_path:
            return None

        logger.info(f"[B站字幕] 选中文件: {sub_path}")

        # 根据扩展名选择解析器
        if sub_path.endswith('.json'):
            segments = _parse_bilibili_json_segments(sub_path)
        else:
            with open(sub_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            segments = _parse_vtt_segments(raw_text)

        if not segments:
            logger.warning(f"[B站字幕] 解析出 0 个片段")
            return None

        plain = _segments_to_plain_text(segments)
        if len(plain) < 10:
            logger.warning(f"[B站字幕] 纯文本太短 ({len(plain)} 字)")
            return None

        logger.info(f"[B站字幕] 成功提取 {len(segments)} 片段，{len(plain)} 字")
        return SubtitleData(plain_text=plain, segments=segments)

    except Exception as e:
        logger.warning(f"[B站字幕] 提取过程异常: {type(e).__name__}: {e}")
        return None

    finally:
        if cookies_file and os.path.exists(cookies_file):
            os.unlink(cookies_file)
        import shutil
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


# ========== 公共入口 ==========

async def extract_subtitle_text(
    url: str,
    cookies: Optional[str] = None,
) -> Optional[SubtitleData]:
    """
    提取视频字幕，自动根据平台选择最佳方式。

    - YouTube → youtube-transcript-api（专用字幕库）
    - B站 → yt-dlp（下载 + 解析）

    返回 SubtitleData：
      - plain_text: 纯文本，空格分隔，给 AI 分析用
      - segments: [{start_time, end_time, text}, ...]，给前端展示用

    无字幕时返回 None。
    """
    if re.search(r"youtube\.com|youtu\.be", url, re.IGNORECASE):
        return await _extract_youtube_subs(url)

    if re.search(r"bilibili\.com|b23\.tv", url, re.IGNORECASE):
        return await _extract_bilibili_subs(url, cookies)

    return None
