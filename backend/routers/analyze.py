"""
分析相关 API 路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import unquote
import httpx
from models.schemas import ParseRequest, ParseResponse
from services.ytdlp_service import parse_video_info

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
        # 预期的错误（如不支持平台、链接无效等），返回 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 未预期的错误，返回 500
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/thumbnail")
async def proxy_thumbnail(url: str):
    """
    封面图代理 — 解决 B站 / YouTube 图片防盗链问题。

    原理：浏览器直接加载 B站 图片会被拒绝（防盗链）。
    我们让后端帮忙去取图片，加上正确的 Referer 头，
    然后原样返回给前端。这样前端就能正常显示了。
    """
    # URL 解码（前端传来的 url 参数会被自动编码）
    image_url = unquote(url)

    # 伪装成从对应网站来的请求
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
                headers={"Cache-Control": "public, max-age=86400"}  # 缓存 1 天
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="封面图加载超时")
