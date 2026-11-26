"""持久任务记录。平台会话凭证由运行器临时持有。"""

from dataclasses import dataclass, field
import json
import time
from typing import Optional

from storage.study_db import pack

RETRYABLE = {"failed", "needs_input", "needs_retry", "cancelled"}


@dataclass
class StudyJob:
    id: str
    kind: str
    label: str
    payload: dict
    persistent: bool = True
    state: str = "queued"
    phase: str = "queued"
    checkpoint: Optional[dict] = None
    result: Optional[dict] = None
    detail: Optional[str] = None
    code: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def from_row(cls, row):
        data = dict(row)
        for key in ("payload", "checkpoint", "result"):
            data[key] = json.loads(data[key]) if data[key] is not None else None
        return cls(**data)

    def brief(self):
        return {
            "id": self.id, "kind": self.kind, "label": self.label, "state": self.state,
            "phase": self.phase, "detail": self.detail, "code": self.code, "persistent": self.persistent,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "provider": self.payload.get("provider"),
        }


def read_job(connection, job_id):
    row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return StudyJob.from_row(row) if row else None


def insert_job(connection, job):
    connection.execute(
        """INSERT INTO jobs(id, kind, state, phase, label, payload, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (job.id, job.kind, job.state, job.phase, job.label, pack(job.payload), job.created_at, job.updated_at),
    )


def update_job(connection, job):
    connection.execute(
        """UPDATE jobs SET state=?, phase=?, label=?, payload=?, checkpoint=?, result=?, detail=?, code=?, updated_at=?
           WHERE id=? AND created_at=?""",
        (job.state, job.phase, job.label, pack(job.payload),
         pack(job.checkpoint) if job.checkpoint is not None else None,
         pack(job.result) if job.result is not None else None,
         job.detail, job.code, job.updated_at, job.id, job.created_at),
    )


def delete_job(connection, job):
    connection.execute("DELETE FROM jobs WHERE id=? AND created_at=?", (job.id, job.created_at))


def delete_video_analyses(connection, video):
    rows = connection.execute(
        """DELETE FROM jobs WHERE kind='analysis' AND (
               json_extract(payload, '$.url')=? OR json_extract(result, '$.video_id')=?
               OR (json_extract(checkpoint, '$.video.platform')=?
                   AND json_extract(checkpoint, '$.video.external_id')=?)
           ) RETURNING id""",
        (video["url"], video["id"], video["platform"], video["external_id"]),
    )
    return [row["id"] for row in rows]


def recover_jobs(connection):
    connection.execute(
        """UPDATE jobs SET state='needs_retry', detail='AI 请求可能已发出，请确认是否重试。',
           code='retry_confirmation', updated_at=? WHERE state='running' AND phase='ai'""",
        (time.time(),),
    )
    connection.execute(
        """UPDATE jobs SET state='queued', updated_at=?
           WHERE state='running'""", (time.time(),),
    )


def queued_jobs(connection):
    return [StudyJob.from_row(row) for row in connection.execute(
        """SELECT * FROM jobs WHERE state='queued'
           ORDER BY CASE kind WHEN 'question' THEN 0 WHEN 'analysis' THEN 1 ELSE 2 END, created_at LIMIT 1"""
    )]


def recent_jobs(connection, *, conversation_id=None, kind=None):
    where = ""
    params = ()
    if conversation_id is not None:
        where, params = "WHERE kind='question' AND json_extract(payload, '$.conversation_id')=?", (conversation_id,)
    elif kind is not None:
        where, params = "WHERE kind=?", (kind,)
    return [StudyJob.from_row(row) for row in connection.execute(
        f"SELECT * FROM jobs {where} ORDER BY updated_at DESC, id LIMIT 100", params,
    )]
