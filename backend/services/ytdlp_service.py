"""
yt-dlp 封装服务 — 通过 subprocess 调用 CLI，不修改 yt-dlp 源码
"""
import json
import asyncio
import subprocess
import re
import sys
import os
import shutil
import tempfile
from typing import Optional
from config import YTDLP_PROXY, YTDLP_TIMEOUT, DOWNLOAD_TIMEOUT, YTDLP_NO_CHECK_CERTIFICATES
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
            url
        ]
        if YTDLP_NO_CHECK_CERTIFICATES:
            cmd.insert(4, "--no-check-certificates")

        # YouTube: 用 Android 客户端绕过 SABR 流式拦截
        if platform == "youtube":
            cmd.extend(["--extractor-args", "youtube:player_client=android"])

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


def _sanitize_filename(name: str) -> str:
    """把文件名中的非法字符替换为下划线"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip() or "video"


async def _get_download_filename(
    url: str, format_id: str, cookies_file: Optional[str] = None, platform: str = "unsupported"
) -> str:
    """
    查询 yt-dlp 会输出什么文件名。
    跑一次 --print filename（只查询元数据，不下载），拿到文件名后返回。
    失败时返回 "video.mp4" 兜底。
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--print", "filename",
        "-f", format_id,
        "--no-playlist",
        url
    ]
    if YTDLP_NO_CHECK_CERTIFICATES:
        cmd.insert(4, "--no-check-certificates")
    if platform == "youtube":
        cmd.extend(["--extractor-args", "youtube:player_client=android"])
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    if YTDLP_PROXY:
        cmd.extend(["--proxy", YTDLP_PROXY])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=YTDLP_TIMEOUT)
        if process.returncode == 0 and stdout:
            name = stdout.decode("utf-8", errors="replace").strip()
            if name:
                return _sanitize_filename(name)
    except Exception:
        pass

    return "video.mp4"


async def download_video(
    url: str,
    format_id: str = "best",
    cookies: Optional[str] = None,
    has_audio: bool = True,
):
    """
    下载视频到临时文件。

    流程：
    1. 构建格式选择器 + 文件名查询
    2. yt-dlp 下载到临时目录 → 成功后才返回
    3. 返回 (filepath, filename, temp_dir) 供路由层用 FileResponse 发送

    简单可靠：yt-dlp 自己处理 cookies / ffmpeg / 风控，后端不插手。
    """
    platform = identify_platform(url)

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
    if cookies:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(cookies)
        tmp.close()
        cookies_file = tmp.name

    temp_dir = None
    try:
        # -- 3. 查询 yt-dlp 会输出的文件名 --
        filename = await _get_download_filename(url, format_selector, cookies_file, platform)

        # -- 4. 创建临时目录，下载到那里 --
        temp_dir = tempfile.mkdtemp(prefix="ytdlp_dl_")
        output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", format_selector,
            "-o", output_template,
            "--format-sort", "vcodec:avc",  # 优先 H.264（兼容性好），没有时自动降级
            "--no-playlist",
            url,
        ]
        if YTDLP_NO_CHECK_CERTIFICATES:
            cmd.insert(5, "--no-check-certificates")
        # YouTube: 用 Android 客户端绕过 SABR 流式拦截
        # ref: https://github.com/yt-dlp/yt-dlp/issues/12482
        if platform == "youtube":
            cmd.extend(["--extractor-args", "youtube:player_client=android"])
        if cookies_file:
            cmd.extend(["--cookies", cookies_file])
        if YTDLP_PROXY:
            cmd.extend(["--proxy", YTDLP_PROXY])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 等 yt-dlp 完整下载完成（大文件需要时间）
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=DOWNLOAD_TIMEOUT
        )

        if process.returncode != 0:
            error_text = _extract_download_error(stderr)
            raise RuntimeError(f"下载失败：{error_text}")

        # -- 5. 找到下载好的文件 --
        files = os.listdir(temp_dir)
        if not files:
            raise RuntimeError("下载完成但未找到输出文件")

        filepath = os.path.join(temp_dir, files[0])
        filename = os.path.basename(filepath)  # 用实际输出的文件名

        return filepath, filename, temp_dir

    except RuntimeError:
        # 下载失败 → 清理临时目录
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except asyncio.TimeoutError:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"下载超时（超过 {DOWNLOAD_TIMEOUT} 秒），文件可能过大或网络较慢")
    except Exception as e:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"下载异常：{str(e)}")
    finally:
        # cookies 用完即删
        if cookies_file and os.path.exists(cookies_file):
            os.unlink(cookies_file)
