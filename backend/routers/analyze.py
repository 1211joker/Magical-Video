"""
分析相关 API 路由
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import unquote
import httpx
from models.schemas import ParseRequest, ParseResponse
from services.ytdlp_service import parse_video_info
from services.subtitle_service import extract_subtitle_text
from services.deepseek_service import analyze_subtitles

router = APIRouter(prefix="/api", tags=["analyze"])


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "后端服务运行正常"}


@router.post("/parse", response_model=ParseResponse)
async def parse_video(req: ParseRequest):
    """
    解析视频链接，返回元数据（标题、封面、时长等）。

    前端调用方式：
        POST /api/parse
        Body: { "url": "https://www.youtube.com/watch?v=xxx" }

    返回内容包含：
        - platform: 哪个平台 (youtube / bilibili)
        - title: 视频标题
        - duration: 时长（秒）
        - thumbnail: 封面图地址
        - description: 视频简介
        - formats: 可选清晰度列表
    """
    try:
        result = await parse_video_info(req.url, cookies=req.cookies)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/thumbnail")
async def proxy_thumbnail(url: str):
    """
    封面图代理 — 解决 B站 / YouTube 图片防盗链问题。
    """
    image_url = unquote(url)

    headers = {
        "Referer": "https://www.bilibili.com",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
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
async def analyze_video_stream(req: ParseRequest):
    """
    AI 分析视频字幕，通过 SSE 实时推送进度。

    前端调用方式：
        POST /api/analyze-stream
        Body: { "url": "https://...", "cookies": "..." }

    SSE 事件格式：
        data: {"step": "parse", "status": "processing", "message": "..."}
        data: {"step": "subtitles", "status": "processing", "message": "..."}
        data: {"step": "subtitles", "status": "done", "message": "已提取 xxx 字"}
        data: {"step": "analyze", "status": "processing", "message": "AI 分析中..."}
        data: {"step": "analyze", "status": "done", "result": {...}}
    """

    async def event_generator():
        try:
            # 步骤 1：获取视频信息（快速）
            yield _sse("parse", "processing", "正在获取视频信息...")

            try:
                video_info = await parse_video_info(req.url, cookies=req.cookies)
            except RuntimeError as e:
                yield _sse("parse", "failed", str(e))
                return

            if video_info.platform == "unsupported":
                yield _sse("parse", "failed", video_info.description or "暂不支持此平台")
                return

            yield _sse("parse", "done", f"视频：{video_info.title}")

            # 步骤 2：提取字幕
            yield _sse("subtitles", "processing", "正在提取字幕文本...")

            subtitle_data = await extract_subtitle_text(req.url, cookies=req.cookies)

            if not subtitle_data:
                yield _sse("subtitles", "failed",
                           "该视频没有可用字幕（可能未开启自动字幕或语言不支持）\n"
                           "可以尝试提供中文字幕的视频链接")
                return

            char_count = len(subtitle_data.plain_text)
            yield _sse("subtitles", "done", f"已提取 {char_count} 字字幕文本")

            # 步骤 3：AI 分析
            yield _sse("analyze", "processing", "AI 正在分析视频内容，请稍候...")

            try:
                result = await analyze_subtitles(subtitle_data.plain_text, video_info.title)
            except RuntimeError as e:
                yield _sse("analyze", "failed", str(e))
                return

            # 成功！推送最终结果（含四维度 + 字幕片段 + 字幕全文用于 QA）
            yield _sse("analyze", "done", "分析完成", {
                "title": result.title,
                "overview": result.overview,
                "outline": [item.model_dump() for item in result.outline],
                "key_points": [item.model_dump() for item in result.key_points],
                "conclusions": [item.model_dump() for item in result.conclusions],
                "mindmap": result.mindmap,
                "subtitle_segments": subtitle_data.segments,
                "subtitle_text": subtitle_data.plain_text,
            })

        except Exception as e:
            yield _sse("error", "failed", f"分析过程出错: {str(e)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )


def _sse(step: str, status: str, message: str, result: dict = None) -> str:
    """生成一条 SSE 事件字符串"""
    data = {"step": step, "status": status, "message": message}
    if result is not None:
        data["result"] = result
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
