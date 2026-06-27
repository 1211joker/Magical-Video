"""
yt-dlp 封装服务 — 通过 subprocess 调用 CLI，不修改 yt-dlp 源码
"""
import json
import asyncio
import subprocess
import re
import sys
import os
import tempfile
from typing import Optional
from config import YTDLP_PROXY, YTDLP_TIMEOUT
from models.schemas import ParseResponse, FormatInfo


# 平台识别规则（用最简单的 URL 关键词匹配）
PLATFORM_RULES = [
    ("youtube", [r"youtube\.com", r"youtu\.be"]),
    ("bilibili", [r"bilibili\.com", r"b23\.tv"]),
]

# 已知不支持的平台
UNSUPPORTED_PLATFORMS = [
    (r"tiktok\.com", "TikTok"),
    (r"douyin\.com", "抖音"),
]


def identify_platform(url: str) -> str:
    """
    通过 URL 判断是哪个平台。
    返回 "youtube" / "bilibili" / "unsupported"
    """
    for platform, patterns in PLATFORM_RULES:
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return "unsupported"


def check_unsupported(url: str) -> Optional[str]:
    """如果是明确不支持的平台，返回平台中文名"""
    for pattern, name in UNSUPPORTED_PLATFORMS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return None


async def parse_video_info(url: str, cookies: Optional[str] = None) -> ParseResponse:
    """
    用 yt-dlp 提取视频元数据（不下载视频本身）。

    大白话原理：
    1. 运行 `yt-dlp --dump-json <url>` 命令
    2. yt-dlp 去视频网站爬取信息，返回一个 JSON
    3. 我们从 JSON 中挑出需要的字段：标题、时长、封面等

    这一步不下载视频，只获取"名片信息"，通常 2-5 秒完成。

    cookies 参数：B站需要登录才能获取完整信息。用户把浏览器的 cookies
    粘贴进来，我们临时写成文件传给 yt-dlp，用完即删，不留存。
    """
    # 先检查是否是不支持的平台
    unsupported_name = check_unsupported(url)
    if unsupported_name:
        return ParseResponse(
            platform="unsupported",
            title="",
            duration=0,
            thumbnail="",
            description=f"暂不支持{unsupported_name}",
            webpage_url=url,
            formats=[]
        )

    platform = identify_platform(url)
    if platform == "unsupported":
        return ParseResponse(
            platform="unsupported",
            title="",
            duration=0,
            thumbnail="",
            description="暂不支持此平台，目前只支持 YouTube 和 B站",
            webpage_url=url,
            formats=[]
        )

    # 把 cookies 文本写入临时文件（用后即删）
    cookies_file = None
    if cookies:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(cookies)
        tmp.close()
        cookies_file = tmp.name

    try:
        # 构建 yt-dlp 命令
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--dump-json",
            "--no-playlist",
            "--flat-playlist",
            "--no-check-certificates",
            url
        ]

        # 有 cookies 文件时传入
        if cookies_file:
            cmd.extend(["--cookies", cookies_file])

        if YTDLP_PROXY:
            cmd.extend(["--proxy", YTDLP_PROXY])

        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=YTDLP_TIMEOUT
        )

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            # 识别 B站 需要登录的情况
            if platform == "bilibili" and ("412" in error_msg or "403" in error_msg):
                if not cookies:
                    raise RuntimeError(
                        "B站需要登录才能获取视频信息。\n"
                        "请在下方展开「B站 Cookies」面板，按指引粘贴 cookies 后重试。\n"
                        "YouTube 视频无需此步骤。"
                    )
                else:
                    raise RuntimeError("cookies 已过期或无效，请重新获取并粘贴")
            if "Private video" in error_msg or "Video unavailable" in error_msg:
                raise RuntimeError("视频不可用（可能已删除或设为私密）")
            if "HTTP Error 429" in error_msg:
                raise RuntimeError("请求过于频繁，请稍等片刻再试")
            # 如果带了 cookies 还失败，可能是 cookies 过期
            if cookies_file and platform == "bilibili":
                raise RuntimeError("cookies 可能已过期，请重新获取并粘贴")
            raise RuntimeError("解析失败，请检查链接是否有效")

        data = json.loads(stdout.decode("utf-8"))

        title = data.get("title", "未知标题")
        duration = int(data.get("duration", 0) or 0)
        thumbnail = data.get("thumbnail", "")
        description = data.get("description", "") or ""
        webpage_url = data.get("webpage_url", url)

        raw_formats = data.get("formats", [])
        formats = _extract_formats(raw_formats)

        return ParseResponse(
            platform=platform,
            title=title,
            duration=duration,
            thumbnail=thumbnail,
            description=description[:500],
            webpage_url=webpage_url,
            formats=formats
        )

    except asyncio.TimeoutError:
        raise RuntimeError(f"解析超时（超过 {YTDLP_TIMEOUT} 秒），请稍后重试")
    except json.JSONDecodeError:
        raise RuntimeError("yt-dlp 返回格式异常，请重试")

    finally:
        # 无论成功失败，用完即删 cookies 临时文件
        if cookies_file and os.path.exists(cookies_file):
            os.unlink(cookies_file)


def _extract_formats(raw_formats: list) -> list[FormatInfo]:
    """
    从 yt-dlp 的原始格式列表中提取用户可选的清晰度。

    规则：
    - 只要视频+音频合并的格式（有 video_ext 且有 audio_ext）
    - 同一个分辨率只留一个（取文件体积最小的）
    - 最多展示 6 个选项
    """
    merged = []

    for f in raw_formats:
        # 过滤：有视频、有音频、有分辨率信息
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        height = f.get("height")

        if vcodec == "none" or acodec == "none" or not height:
            continue

        resolution = f"{height}p"
        filesize = f.get("filesize") or f.get("filesize_approx")

        merged.append(FormatInfo(
            format_id=f["format_id"],
            resolution=resolution,
            filesize=filesize,
            ext=f.get("ext", "mp4")
        ))

    # 去重：同一个分辨率只留一个
    seen_resolution = set()
    unique = []
    for f in merged:
        if f.resolution not in seen_resolution:
            seen_resolution.add(f.resolution)
            unique.append(f)

    # 按分辨率从高到低排序
    unique.sort(key=lambda x: int(x.resolution.replace("p", "")), reverse=True)

    return unique[:6]
