"""
分析相关 API 路由
"""
import asyncio
import json
from typing import AsyncGenerator

from anyio import CancelScope
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from urllib.parse import unquote, urlsplit
import httpx
from models.schemas import AnalyzeVideoRequest, ParseRequest, ParseResponse, SubtitleResponse
from services.ai_client import select_provider
from services.analysis_service import analyze_subtitles
from services.panopto_service import PanoptoError
from services.video_service import open_video
from services.video_session import BilibiliSessionError
from services.youtube_network import YouTubeNetworkUnavailable, get_youtube_connection
from limiter import limiter

router = APIRouter(prefix="/api", tags=["analyze"])
SSE_HEARTBEAT_SECONDS = 15


async def _open_requested_video(req: ParseRequest):
    return await open_video(
        req.url,
        cookies=req.cookies,
        panopto_session=req.panopto_session,
        bilibili_session=req.bilibili_session,
    )


def _no_subtitles_message(platform: str) -> str:
    if platform == "panopto":
        return "该 Panopto 录像没有可用字幕。可以在官方播放器的字幕面板确认。"
    return "该视频没有可用字幕（可能未开启自动字幕或语言不支持）。"


class AnalysisStreamResponse(StreamingResponse):
    async def stream_response(self, send):
        try:
            await super().stream_response(send)
        finally:
            # 客户端在发送事件时断开，也要关闭迭代器并取消待完成的工作。
            with CancelScope(shield=True):
                await self.body_iterator.aclose()


async def _with_heartbeat(events: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    pending = asyncio.create_task(events.__anext__())
    try:
        while True:
            done, _ = await asyncio.wait((pending,), timeout=SSE_HEARTBEAT_SECONDS)
            if not done:
                yield ": keep-alive\n\n"
                continue
            yield pending.result()
            pending = asyncio.create_task(events.__anext__())
    except StopAsyncIteration:
        return
    finally:
        pending.cancel()
        with CancelScope(shield=True):
            await asyncio.gather(pending, return_exceptions=True)
            await events.aclose()


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "后端服务运行正常"}


@router.post("/parse", response_model=ParseResponse)
@limiter.limit("20/minute")
async def parse_video(req: ParseRequest, request: Request, response: Response):
    """
    解析视频链接，返回元数据（标题、封面、时长等）。

    前端调用方式：
        POST /api/parse
        Body: { "url": "https://www.youtube.com/watch?v=xxx" }

    返回内容包含：
        - platform: 哪个平台 (youtube / bilibili / panopto)
        - title: 视频标题
        - duration: 时长（秒）
        - thumbnail: 封面图地址
        - description: 视频简介
        - formats: 可选清晰度列表
    """
    try:
        video = await _open_requested_video(req)
        if video.info.platform == "panopto" or video.cookies:
            response.headers["Cache-Control"] = "no-store"
        return video.info
    except (YouTubeNetworkUnavailable, PanoptoError, BilibiliSessionError):
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/subtitles", response_model=SubtitleResponse)
@limiter.limit("10/minute")
async def extract_subtitles(req: ParseRequest, request: Request, response: Response):
    """提取和整理字幕，不启动 AI 分析。"""
    try:
        video = await _open_requested_video(req)
        if video.info.platform == "unsupported":
            raise HTTPException(status_code=400, detail=video.info.description or "暂不支持此平台")
        subtitles = await video.subtitles()
    except (YouTubeNetworkUnavailable, PanoptoError, BilibiliSessionError):
        raise
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if not subtitles:
        raise HTTPException(status_code=404, detail=_no_subtitles_message(video.info.platform))

    response.headers["Cache-Control"] = "no-store"
    return SubtitleResponse(subtitle_segments=subtitles.segments, subtitle_text=subtitles.plain_text)


@router.get("/thumbnail")
@limiter.limit("30/minute")
async def proxy_thumbnail(url: str, request: Request):
    """
    封面图代理 — 解决 B站 / YouTube 图片防盗链问题。
    """
    image_url = unquote(url)

    # 根据图片域名选择 Referer 和代理策略
    hostname = urlsplit(image_url).hostname or ""
    is_youtube = any(hostname == domain or hostname.endswith("." + domain) for domain in ("ytimg.com", "youtube.com"))
    headers = {
        "Referer": "https://www.youtube.com/" if is_youtube else "https://www.bilibili.com",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    connection = await get_youtube_connection() if is_youtube else None
    proxy = connection.proxy if connection else None

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=proxy, trust_env=not is_youtube) as client:
            resp = await client.get(image_url, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail="封面图获取失败")

            content_type = resp.headers.get("content-type", "image/jpeg")
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"}
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="封面图加载超时")


@router.post("/analyze-stream")
@limiter.limit("5/minute")
async def analyze_video_stream(req: AnalyzeVideoRequest, request: Request):
    """
    AI 分析视频字幕，通过 SSE 实时推送进度。

    前端调用方式：
        POST /api/analyze-stream
        Body: { "url": "https://...", "provider": "openai" }

    SSE 事件格式：
        data: {"step": "parse", "status": "processing", "message": "..."}
        data: {"step": "subtitles", "status": "processing", "message": "..."}
        data: {"step": "subtitles", "status": "done", "message": "已提取 xxx 字"}
        data: {"step": "analyze", "status": "processing", "message": "AI 分析中..."}
        data: {"step": "analyze", "status": "done", "result": {...}}
    """

    async def event_generator():
        step = "parse"
        try:
            # 步骤 1：获取视频信息（快速）
            yield _sse("parse", "processing", "正在获取视频信息...")

            try:
                video = await _open_requested_video(req)
            except RuntimeError as e:
                yield _sse("parse", "failed", str(e))
                return

            video_info = video.info
            if video_info.platform == "unsupported":
                yield _sse("parse", "failed", video_info.description or "暂不支持此平台")
                return

            yield _sse("parse", "done", f"视频：{video_info.title}")

            # 步骤 2：提取字幕
            step = "subtitles"
            yield _sse("subtitles", "processing", "正在提取字幕文本...")

            subtitle_data = await video.subtitles()

            if not subtitle_data:
                yield _sse("subtitles", "failed", _no_subtitles_message(video_info.platform))
                return

            char_count = len(subtitle_data.plain_text)
            yield _sse("subtitles", "done", f"已提取 {char_count} 字字幕文本")

            # 步骤 3：AI 分析
            step = "analyze"
            yield _sse("analyze", "processing", "AI 正在分析视频内容，请稍候...")

            try:
                provider = select_provider(req.provider)
                result = await analyze_subtitles(subtitle_data.plain_text, video_info.title, provider)
            except RuntimeError as e:
                yield _sse("analyze", "failed", str(e))
                return

            # 成功！推送最终结果（含四维度 + 字幕片段 + 字幕全文用于 QA）
            yield _sse("analyze", "done", "分析完成", {
                "title": result.title,
                "provider": provider.id,
                "overview": result.overview,
                "outline": [item.model_dump() for item in result.outline],
                "key_points": [item.model_dump() for item in result.key_points],
                "conclusions": [item.model_dump() for item in result.conclusions],
                "mindmap": result.mindmap,
                "subtitle_segments": subtitle_data.segments,
                "subtitle_text": subtitle_data.plain_text,
            })

        except (YouTubeNetworkUnavailable, PanoptoError, BilibiliSessionError) as error:
            yield _sse(step, "failed", str(error), code=error.code)
        except Exception as e:
            yield _sse("error", "failed", f"分析过程出错: {str(e)}")

    return AnalysisStreamResponse(
        _with_heartbeat(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )


def _sse(step: str, status: str, message: str, result: dict = None, *, code: str = None) -> str:
    """生成一条 SSE 事件字符串"""
    data = {"step": step, "status": status, "message": message}
    if result is not None:
        data["result"] = result
    if code:
        data["code"] = code
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
