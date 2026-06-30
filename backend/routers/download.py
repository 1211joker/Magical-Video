"""
下载相关 API 路由 — 后端缓存后文件传输
"""
import logging
import shutil
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse

from models.schemas import DownloadRequest
from services.ytdlp_service import download_video
from limiter import limiter

router = APIRouter(prefix="/api", tags=["download"])

logger = logging.getLogger(__name__)


@router.post("/download")
@limiter.limit("3/minute")
async def download_video_endpoint(body: DownloadRequest, background_tasks: BackgroundTasks, request: Request):
    """
    下载视频：后端用 yt-dlp 完整下载到临时文件 → FileResponse 发给浏览器。

    浏览器收到后会弹出"另存为"对话框。
    """
    logger.info(
        f"[下载] 开始: url={body.url[:80]}, format={body.format_id}"
    )

    try:
        filepath, filename, temp_dir = await download_video(
            url=body.url,
            format_id=body.format_id,
            cookies=body.cookies,
            has_audio=body.has_audio,
        )
    except RuntimeError as e:
        logger.warning(f"[下载] 失败: {e}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(e)}
        )
    except Exception as e:
        logger.exception(f"[下载] 未预期错误: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"服务器内部错误: {str(e)}"}
        )

    # 响应发送完毕后自动删除临时目录
    background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

    encoded_filename = quote(filename, safe="")
    logger.info(f"[下载] 完成，传输文件: {filename}")

    # FileResponse 的 filename 参数自动处理 Content-Disposition 的 UTF-8 编码
    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=filename,
        headers={
            "X-Filename": encoded_filename,
        },
    )
