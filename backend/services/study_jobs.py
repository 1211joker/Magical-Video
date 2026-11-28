"""本地任务队列。浏览器只通过任务 ID 观察进度。"""

import asyncio
from dataclasses import replace
import logging
import time

from storage import study_jobs as store
from storage.study_db import StudyProblem

logger = logging.getLogger(__name__)
TEMPORARY_TTL = 3600
JOB_PRIORITY = {"question": 0, "analysis": 1, "wiki": 2}


class LocalStudyJobs:
    def __init__(self, database, run_job, notify):
        self.database = database
        self.run_job = run_job
        self.notify = notify
        self.temporary = {}
        self.credentials = {}
        self.active = None
        self.active_id = None

    def recover(self):
        with self.database.transaction(write=True) as connection:
            store.recover_jobs(connection)

    def submit(self, job, credentials=None):
        self.prune()
        with self.database.transaction(write=True) as connection:
            existing = self.temporary.get(job.id) or store.read_job(connection, job.id)
            if existing:
                # 旧任务允许缺少后来加入的模型和平台鉴权信息。
                payload = {**existing.payload}
                requested = {**job.payload}
                original_save = payload.pop("save_at_submission", existing.persistent)
                payload.pop("requires_session", None)
                requested.pop("requires_session", None)
                if "provider" in requested:
                    payload.setdefault("provider", requested["provider"])
                if (existing.kind, payload, original_save) != (job.kind, requested, job.persistent):
                    raise StudyProblem("请求编号已经用于另一个任务", 409, "request_conflict")
                return existing
            count = connection.execute(
                "SELECT count(*) FROM jobs WHERE state IN ('queued', 'running')"
            ).fetchone()[0]
            count += sum(item.state in {"queued", "running"} for item in self.temporary.values())
            if count >= 30:
                raise StudyProblem("待处理任务较多，请等当前任务完成", 429, "queue_full")
            if job.kind == "question":
                pending = connection.execute(
                    """SELECT 1 FROM jobs WHERE kind='question' AND state IN ('queued','running')
                       AND json_extract(payload, '$.conversation_id')=?""", (job.payload["conversation_id"],),
                ).fetchone()
                if pending:
                    raise StudyProblem("这个对话已有一条问题在处理", 409, "question_pending")
            if job.persistent:
                store.insert_job(connection, job)
            else:
                self.temporary[job.id] = job
        self._set_credentials(job, credentials)
        self.notify()
        return job

    def get(self, job_id):
        self.prune()
        with self.database.transaction() as connection:
            job = self.temporary.get(job_id) or store.read_job(connection, job_id)
        if not job:
            raise StudyProblem("任务不存在或临时任务已过期", 404, "job_not_found")
        return job

    def list(self, conversation_id=None, *, kind=None):
        self.prune()
        with self.database.transaction() as connection:
            jobs = store.recent_jobs(connection, conversation_id=conversation_id, kind=kind)
        if conversation_id is None:
            jobs.extend(job for job in self.temporary.values() if kind is None or job.kind == kind)
        return sorted(jobs, key=lambda job: (-job.updated_at, job.id))[:100]

    def retry(self, job, credentials=None):
        if job.state not in store.RETRYABLE:
            raise StudyProblem("当前任务状态无法重试", 409, "job_state")
        if job.kind == "question":
            competing = self.list(job.payload["conversation_id"])
            if any(item.id != job.id and item.state in {"queued", "running"} for item in competing):
                raise StudyProblem("这个对话已有一条问题在处理", 409, "question_pending")
        self._set_credentials(job, credentials)
        job.state, job.phase, job.detail, job.code = "queued", "queued", None, None
        self._save(job)
        self.notify()
        return job

    def cancel(self, job):
        if job.state not in {"queued", "running", "needs_input", "needs_retry"}:
            raise StudyProblem("当前任务已经结束", 409, "job_state")
        job.state, job.phase, job.checkpoint = "cancelled", "cancelled", None
        job.detail, job.code = None, None
        self._save(job)
        self.credentials.pop(job.id, None)
        self.interrupt(job.id)
        return job

    def delete_analysis(self, job_id):
        job = self.get(job_id)
        if job.kind != "analysis":
            raise StudyProblem("没有这条解析记录", 404, "analysis_not_found")
        if job.persistent:
            with self.database.transaction(write=True) as connection:
                store.delete_job(connection, job)
        else:
            self.temporary.pop(job_id, None)
        self.interrupt(job_id)

    def interrupt(self, job_id):
        self.credentials.pop(job_id, None)
        if self.active_id == job_id and self.active:
            self.active.cancel()

    def progress(self, job, phase, checkpoint=None, *, requeue=False):
        job.phase = phase
        if checkpoint is not None:
            job.checkpoint = checkpoint
        if requeue:
            job.state = "queued"
        self._save(job)
        if requeue:
            self.notify()

    def complete(self, job, result=None, *, commit=None):
        finished = replace(job, state="done", phase="done", checkpoint=None, detail=None, code=None,
                           updated_at=time.time())
        if job.persistent:
            with self.database.transaction(write=True) as connection:
                current = store.read_job(connection, job.id)
                if not current or current.created_at != job.created_at or current.state != "running":
                    raise asyncio.CancelledError()
                finished.result = commit(connection) if commit else result
                store.update_job(connection, finished)
        else:
            if self.temporary.get(job.id) is not job or job.state != "running":
                raise asyncio.CancelledError()
            finished.result = result
            self.temporary[job.id] = finished

    def persist_completed(self, job, commit):
        with self.database.transaction(write=True) as connection:
            payload = {**job.payload, "save_at_submission": job.persistent}
            saved = replace(job, persistent=True, payload=payload, result=commit(connection), updated_at=time.time())
            store.insert_job(connection, saved)
        # 事务失败时保留内存结果，允许用户重试。
        self.temporary.pop(job.id, None)
        self.notify()

    def _save(self, job):
        job.updated_at = time.time()
        # Temporary jobs already change in place. A removed job must stay out of the queue.
        if job.persistent:
            with self.database.transaction(write=True) as connection:
                store.update_job(connection, job)

    def _set_credentials(self, job, credentials):
        if credentials:
            self.credentials[job.id] = credentials

    def prune(self):
        cutoff = time.time() - TEMPORARY_TTL
        for job in list(self.temporary.values()):
            if job.state not in {"queued", "running"} and job.updated_at < cutoff:
                self.temporary.pop(job.id)
                self.credentials.pop(job.id, None)

    @staticmethod
    def _priority(job):
        return JOB_PRIORITY[job.kind], job.created_at, job.id

    def _take(self):
        with self.database.transaction(write=True) as connection:
            candidates = store.queued_jobs(connection)
            candidates.extend(job for job in self.temporary.values() if job.state == "queued")
            if not candidates:
                return None
            job = min(candidates, key=self._priority)
            job.state = "running"
            job.updated_at = time.time()
            if job.persistent:
                store.update_job(connection, job)
            return job

    async def run_next(self):
        self.prune()
        job = self._take()
        if job is None:
            return False
        self.active_id = job.id
        self.active = asyncio.create_task(self._execute(job, self.credentials.pop(job.id, {})))
        try:
            await self.active
        except asyncio.CancelledError:
            # 单条任务的取消只终止它自己的执行，服务退出才终止调度。
            if asyncio.current_task().cancelling():
                raise
        finally:
            self.active = None
            self.active_id = None
        return True

    async def _execute(self, job, credentials):
        try:
            await self.run_job(job, credentials)
        except StudyProblem as error:
            self._fail(job, error.detail, error.code)
        except Exception:
            logger.error("本地学习任务失败 type=%s", job.kind)
            self._fail(job, "执行失败，请重试。", "job_failed")
        finally:
            credentials.clear()

    def _fail(self, job, detail, code):
        if code == "retry_confirmation":
            job.state = "needs_retry"
        elif code.endswith(("_login_required", "_session_rejected")):
            job.state = "needs_input"
        else:
            job.state = "failed"
        job.detail, job.code = detail, code
        self._save(job)
