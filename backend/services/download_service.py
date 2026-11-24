"""下载任务与临时文件的生命周期。"""

import asyncio
import secrets
from dataclasses import dataclass, field
from functools import partial
from typing import Optional, Union

from pydantic import SecretStr

from services.panopto_service import PanoptoError, get_panopto_video
from services.video_platform import identify_platform
from services.video_session import cookies_for_video
from services.ytdlp_service import PreparedVideo, download_video


class DownloadJobNotFound(Exception):
    """任务不存在、已领取或已过期。"""


class DownloadNotReady(Exception):
    """文件仍在准备。"""


@dataclass(frozen=True)
class DownloadRedirect:
    url: str = field(repr=False)


PreparedDownload = Union[PreparedVideo, DownloadRedirect]


async def prepare_download(
    url: str,
    format_id: str,
    cookies: Optional[str],
    panopto_session: Optional[SecretStr] = None,
    bilibili_session: Optional[SecretStr] = None,
) -> PreparedDownload:
    platform = identify_platform(url)
    if platform == "panopto":
        video = await get_panopto_video(url, panopto_session)
        if not video.download_url:
            raise PanoptoError("panopto_download_unavailable", "Panopto 当前未为这个账号提供官方录像下载。")
        return DownloadRedirect(video.download_url)
    if platform not in ("youtube", "bilibili"):
        raise RuntimeError("目前支持 YouTube、B站和理大 Panopto 的视频下载")
    video_cookies = cookies_for_video(platform, cookies, bilibili_session)
    return await download_video(url, format_id, video_cookies)


@dataclass
class DownloadJob:
    task: asyncio.Task
    expiry: Optional[asyncio.TimerHandle] = None


class DownloadJobs:
    def __init__(self, retention_seconds: float = 300):
        self._retention_seconds = retention_seconds
        self._jobs: dict[str, DownloadJob] = {}
        self._cleanup_tasks: set[asyncio.Task] = set()

    def start(
        self,
        url: str,
        format_id: str,
        cookies: Optional[str],
        panopto_session: Optional[SecretStr] = None,
        bilibili_session: Optional[SecretStr] = None,
    ) -> str:
        job_id = secrets.token_urlsafe(24)
        task = asyncio.create_task(prepare_download(url, format_id, cookies, panopto_session, bilibili_session))
        self._jobs[job_id] = DownloadJob(task)
        task.add_done_callback(partial(self._schedule_expiry, job_id))
        return job_id

    def result(self, job_id: str) -> Optional[PreparedDownload]:
        job = self._jobs.get(job_id)
        if job is None or job.task.cancelled():
            raise DownloadJobNotFound
        return job.task.result() if job.task.done() else None

    def claim(self, job_id: str) -> PreparedDownload:
        video = self.result(job_id)
        if video is None:
            raise DownloadNotReady
        # 领取和移出任务表在同一个事件循环步骤完成。
        self._remove_job(job_id)
        return video

    async def discard(self, job_id: str):
        cleanup = self._start_cleanup(job_id)
        if cleanup is not None:
            await asyncio.shield(cleanup)

    async def close(self):
        for job_id in tuple(self._jobs):
            self._start_cleanup(job_id)
        await asyncio.gather(*self._cleanup_tasks)

    async def _dispose(self, job: DownloadJob):
        if not job.task.done():
            job.task.cancel()
        result, = await asyncio.gather(job.task, return_exceptions=True)
        if isinstance(result, PreparedVideo):
            await result.remove()

    def _start_cleanup(self, job_id: str) -> Optional[asyncio.Task]:
        job = self._remove_job(job_id)
        if job is None:
            return None
        cleanup = asyncio.create_task(self._dispose(job))
        self._cleanup_tasks.add(cleanup)
        cleanup.add_done_callback(self._cleanup_tasks.discard)
        return cleanup

    def _remove_job(self, job_id: str) -> Optional[DownloadJob]:
        job = self._jobs.pop(job_id, None)
        if job is not None and job.expiry is not None:
            job.expiry.cancel()
        return job

    def _schedule_expiry(self, job_id: str, task: asyncio.Task):
        if not task.cancelled():
            task.exception()
        job = self._jobs.get(job_id)
        if job is not None:
            job.expiry = task.get_loop().call_later(self._retention_seconds, self._start_cleanup, job_id)
