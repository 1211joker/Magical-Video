"""
yt-dlp 封装服务 — 通过 subprocess 调用 CLI，不修改 yt-dlp 源码
"""
import json
import asyncio
import re
import sys
import os
import shutil
import signal
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from anyio import CancelScope

from config import YTDLP_PROXY, YTDLP_TIMEOUT, DOWNLOAD_TIMEOUT, YTDLP_NO_CHECK_CERTIFICATES
from models.schemas import ParseResponse, FormatInfo
from services.video_platform import identify_platform
from services.video_session import BilibiliSessionError, check_bilibili_login
from services.youtube_network import YouTubeConnection, get_youtube_connection


# 已知不支持的平台
UNSUPPORTED_PLATFORMS = [
    (r"tiktok\.com", "TikTok"),
    (r"douyin\.com", "抖音"),
]


def check_unsupported(url: str) -> Optional[str]:
    """如果是明确不支持的平台，返回平台中文名"""
    for pattern, name in UNSUPPORTED_PLATFORMS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return None


def _proxy_args(connection: Optional[YouTubeConnection]) -> list[str]:
    if connection is not None:
        return ["--proxy", connection.proxy or ""]
    return ["--proxy", YTDLP_PROXY] if YTDLP_PROXY else []


async def run_ytdlp(command: list[str], url: str, timeout: float) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *command, "--", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return process.returncode, stdout, stderr
    except BaseException:
        # SSE 断开时 AnyIO 的取消作用域可能继续取消后续等待。
        with CancelScope(shield=True):
            with suppress(ProcessLookupError):
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            await process.communicate()
        raise


async def parse_video_info(url: str, cookies: Optional[str] = None) -> ParseResponse:
    """
    用 yt-dlp 提取视频元数据（不下载视频本身）。

    大白话原理：
    1. 运行 `yt-dlp --dump-json <url>` 命令
    2. yt-dlp 去视频网站爬取信息，返回一个 JSON
    3. 我们从 JSON 中挑出需要的字段：标题、时长、封面等

    这一步不下载视频，只获取"名片信息"，通常 2-5 秒完成。

    cookies 是供 yt-dlp 使用的 Netscape 文本。临时文件会在请求结束后删除。
    """
    platform = identify_platform(url)
    if platform == "unsupported":
        unsupported_name = check_unsupported(url)
        return ParseResponse(
            platform="unsupported",
            title="",
            duration=0,
            thumbnail="",
            description=f"暂不支持{unsupported_name}" if unsupported_name else "目前支持 YouTube、B站和理大 Panopto 的视频链接",
            webpage_url=url,
            formats=[]
        )

    connection = await get_youtube_connection() if platform == "youtube" else None

    cookies_file = None
    try:
        if cookies:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as cookie_file:
                cookies_file = cookie_file.name
                cookie_file.write(cookies)

        # 构建 yt-dlp 命令
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--dump-json",
            "--no-playlist",
            "--flat-playlist",
        ]
        if YTDLP_NO_CHECK_CERTIFICATES:
            cmd.insert(4, "--no-check-certificates")

        # YouTube: 用 Android 客户端绕过 SABR 流式拦截
        if platform == "youtube":
            cmd.extend(["--extractor-args", "youtube:player_client=android"])

        # 有 cookies 文件时传入
        if cookies_file:
            cmd.extend(["--cookies", cookies_file])

        cmd.extend(_proxy_args(connection))

        returncode, stdout, stderr = await run_ytdlp(cmd, url, YTDLP_TIMEOUT)

        if returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            if platform == "bilibili":
                check_bilibili_login(error_msg, bool(cookies_file))
            if "Private video" in error_msg or "Video unavailable" in error_msg:
                raise RuntimeError("视频不可用（可能已删除或设为私密）")
            if "HTTP Error 429" in error_msg:
                raise RuntimeError("请求过于频繁，请稍等片刻再试")
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
            formats=formats,
            youtube_connection=connection.mode if connection else None,
        )

    except asyncio.TimeoutError:
        raise RuntimeError(f"解析超时（超过 {YTDLP_TIMEOUT} 秒），请稍后重试")
    except json.JSONDecodeError:
        raise RuntimeError("yt-dlp 返回格式异常，请重试")

    finally:
        # 无论成功失败，用完即删 cookies 临时文件
        if cookies_file:
            with suppress(FileNotFoundError):
                os.unlink(cookies_file)


def _extract_formats(raw_formats: list) -> list[FormatInfo]:
    """
    从 yt-dlp 原始格式中提取可选分辨率。

    不做复杂的格式筛选 — 只收集所有视频分辨率，
    下载时 yt-dlp 自己用 bestvideo[height<=X]+bestaudio 选最优流。
    """
    # 按分辨率分组，收集每个分辨率下的最佳格式信息
    best_per_height = {}
    for f in raw_formats:
        h = f.get("height")
        vcodec = f.get("vcodec", "none")
        if not h or vcodec == "none":
            continue

        size = f.get("filesize") or f.get("filesize_approx")
        # 优先 H.264（与下载时的 --format-sort vcodec:avc 一致）
        is_avc = (f.get("vcodec") or "").startswith("avc")

        if h not in best_per_height:
            best_per_height[h] = (is_avc, size, f.get("ext", "mp4"))
        else:
            prev_avc, prev_size, prev_ext = best_per_height[h]
            # H.264 优先，同等编码选体积小的（更可能是真实文件大小）
            if is_avc and not prev_avc:
                best_per_height[h] = (is_avc, size, f.get("ext", "mp4"))
            elif is_avc == prev_avc:
                if prev_size is None or (size is not None and size < prev_size):
                    best_per_height[h] = (is_avc, size, f.get("ext", "mp4"))

    if not best_per_height:
        return []

    # 从高到低排序，最多 8 档
    sorted_heights = sorted(best_per_height.keys(), reverse=True)[:8]

    return [
        FormatInfo(
            format_id=f"{h}p",
            resolution=f"{h}p",
            filesize=best_per_height[h][1],  # 预估值
            ext=best_per_height[h][2],
            has_audio=True,
        )
        for h in sorted_heights
    ]


def _extract_download_error(stderr_bytes: bytes) -> str:
    """
    从 yt-dlp 的 stderr 输出中提取真正的错误信息。
    过滤掉 Python 版本警告、urllib3 警告等噪音，取最后 500 字（错误在末尾）。
    """
    lines = stderr_bytes.decode("utf-8", errors="replace").split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "NotOpenSSLWarning" in stripped:
            continue
        if "Deprecated Feature:" in stripped:
            continue
        if "warnings.warn(" in stripped:
            continue
        if stripped.startswith("[download]") and "%" in stripped:
            continue
        clean_lines.append(stripped)

    result = "\n".join(clean_lines)
    # 错误信息在末尾，取最后 500 字
    if len(result) > 500:
        result = "..." + result[-500:]
    return result if result else "未知错误"


@dataclass(frozen=True)
class PreparedVideo:
    path: Path

    async def remove(self):
        await asyncio.to_thread(shutil.rmtree, self.path.parent, ignore_errors=True)


async def download_video(
    url: str,
    format_id: str = "best",
    cookies: Optional[str] = None,
) -> PreparedVideo:
    """准备完整的视频并把临时文件的所有权移交给调用方。"""
    platform = identify_platform(url)
    connection = await get_youtube_connection() if platform == "youtube" else None

    # -- 1. 格式选择器（yt-dlp 原生语法）--
    # format_id 现在是分辨率字符串如 "1080p"，不是原始 format_id
    height_str = format_id.lower().replace("p", "").strip()
    if height_str == "best" or not height_str:
        format_selector = "bestvideo+bestaudio/best"
    else:
        try:
            height = int(height_str)
            format_selector = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        except ValueError:
            format_selector = "bestvideo+bestaudio/best"

    # -- 2. cookies 临时文件（整次下载共用一份）--
    cookies_file = None
    temp_dir = None
    completed = False
    try:
        if cookies:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as cookie_file:
                cookies_file = cookie_file.name
                cookie_file.write(cookies)

        # -- 3. 创建临时目录，下载到那里 --
        temp_dir = tempfile.mkdtemp(prefix="ytdlp_dl_")
        output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", format_selector,
            "-o", output_template,
            "--print", "after_move:%(filepath)j",
            "--format-sort", "vcodec:avc",  # 优先 H.264（兼容性好），没有时自动降级
            "--no-playlist",
        ]
        if YTDLP_NO_CHECK_CERTIFICATES:
            cmd.insert(5, "--no-check-certificates")
        # YouTube: 用 Android 客户端绕过 SABR 流式拦截
        # ref: https://github.com/yt-dlp/yt-dlp/issues/12482
        if platform == "youtube":
            cmd.extend(["--extractor-args", "youtube:player_client=android"])
        if cookies_file:
            cmd.extend(["--cookies", cookies_file])
        cmd.extend(_proxy_args(connection))

        returncode, stdout, stderr = await run_ytdlp(cmd, url, DOWNLOAD_TIMEOUT)

        if returncode != 0:
            if platform == "bilibili":
                check_bilibili_login(stderr.decode("utf-8", errors="replace"), bool(cookies_file))
            error_text = _extract_download_error(stderr)
            raise RuntimeError(f"下载失败：{error_text}")

        # -- 4. 找到下载好的文件 --
        output_path, _, _ = stdout.decode("utf-8").strip().partition("\n")
        if not output_path:
            raise RuntimeError("下载完成但未找到输出文件")
        filepath = Path(json.loads(output_path)).resolve()
        if filepath.parent != Path(temp_dir).resolve() or not filepath.is_file():
            raise RuntimeError("下载完成但未找到有效的视频文件")
        completed = True
        return PreparedVideo(filepath)

    except (RuntimeError, BilibiliSessionError):
        raise
    except asyncio.TimeoutError as error:
        raise RuntimeError(f"下载超时（超过 {DOWNLOAD_TIMEOUT} 秒），文件可能过大或网络较慢") from error
    except Exception as error:
        raise RuntimeError(f"下载异常：{error}") from error
    finally:
        # cookies 用完即删
        if cookies_file:
            with suppress(FileNotFoundError):
                os.unlink(cookies_file)
        if temp_dir and not completed:
            with CancelScope(shield=True):
                await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)
