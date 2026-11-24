"""下载相关的 HTTP 接口。"""

import asyncio
import logging
from contextlib import contextmanager
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from limiter import limiter
from models.schemas import DownloadJobStarted, DownloadJobStatus, DownloadRequest
from services.download_service import DownloadJobNotFound, DownloadJobs, DownloadNotReady
from services.youtube_network import YouTubeNetworkUnavailable
from services.ytdlp_service import PreparedVideo, download_video

router = APIRouter(prefix="/api", tags=["download"])
download_limit = limiter.shared_limit("3/minute", scope="video-download")
logger = logging.getLogger(__name__)


def get_download_jobs(request: Request) -> DownloadJobs:
    return request.app.state.download_jobs


@contextmanager
def download_errors():
    try:
        yield
    except DownloadJobNotFound as error:
        raise HTTPException(404, "下载任务不存在或已过期，请重新发起下载") from error
    except DownloadNotReady as error:
        raise HTTPException(409, "视频文件还在准备中") from error
    except YouTubeNetworkUnavailable:
        raise
    except RuntimeError as error:
        logger.warning("[下载] 视频准备失败")
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        logger.error("[下载] 未预期错误类型 %s", type(error).__name__)
        raise HTTPException(500, "服务器内部错误，请稍后重试") from error


class DownloadFileResponse(FileResponse):
    def __init__(self, video: PreparedVideo):
        filename = video.path.name
        super().__init__(
            video.path,
            media_type="application/octet-stream",
            filename=filename,
            headers={"X-Filename": quote(filename, safe=""), "Cache-Control": "no-store"},
        )
        self.video = video

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            await asyncio.shield(self.video.remove())


@router.post("/download")
@download_limit
async def download_video_endpoint(body: DownloadRequest, request: Request):
    """保留直接接收文件的 API。"""
    with download_errors():
        video = await download_video(body.url, body.format_id, body.cookies)
    return DownloadFileResponse(video)


@router.post("/download/jobs", status_code=202, response_model=DownloadJobStarted)
@download_limit
async def start_download_job(body: DownloadRequest, request: Request, jobs: DownloadJobs = Depends(get_download_jobs)):
    return DownloadJobStarted(job_id=jobs.start(body.url, body.format_id, body.cookies))


@router.get("/download/jobs/{job_id}", response_model=DownloadJobStatus, response_model_exclude_none=True)
async def get_download_status(job_id: str, request: Request, jobs: DownloadJobs = Depends(get_download_jobs)):
    with download_errors():
        video = jobs.result(job_id)
    if video is None:
        return DownloadJobStatus(status="preparing")
    return DownloadJobStatus(status="ready", download_url=request.url_for("get_download_file", job_id=job_id).path)


@router.delete("/download/jobs/{job_id}", status_code=204)
async def cancel_download_job(job_id: str, jobs: DownloadJobs = Depends(get_download_jobs)):
    await jobs.discard(job_id)
    return Response(status_code=204)


@router.get("/download/jobs/{job_id}/file")
async def get_download_file(job_id: str, jobs: DownloadJobs = Depends(get_download_jobs)):
    with download_errors():
        video = jobs.claim(job_id)
    return DownloadFileResponse(video)
