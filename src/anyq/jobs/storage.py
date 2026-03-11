from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel
from redis.asyncio import Redis

log = structlog.get_logger()

# TTL constants
_JOB_TTL = 60 * 60 * 24       # 24 hours
_REPORT_TTL = 60 * 60 * 24    # 24 hours
_UPLOAD_TTL = 60 * 60 * 2     # 2 hours

# Redis key prefixes
_KEY_JOB = "anyq:job:{}"
_KEY_REPORT = "anyq:report:{}"
_KEY_UPLOAD = "anyq:upload:{}"


class JobStatus(StrEnum):
    pending = "pending"
    parsing = "parsing"
    generating = "generating"
    searching = "searching"
    done = "done"
    failed = "failed"


class Job(BaseModel):
    id: str
    status: JobStatus
    progress: int = 0           # 0–100
    current_step: str | None = None
    filename: str
    created_at: datetime
    error: str | None = None


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    query: str
    engine: str


class Report(BaseModel):
    job_id: str
    results: list[SearchResult]
    queries_used: list[str]
    total_found: int


class RedisJobStorage:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create_job(self, filename: str) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            status=JobStatus.pending,
            progress=0,
            current_step=None,
            filename=filename,
            created_at=datetime.now(tz=timezone.utc),
            error=None,
        )
        key = _KEY_JOB.format(job.id)
        await self._redis.set(key, job.model_dump_json(), ex=_JOB_TTL)
        log.info("job.created", job_id=job.id, filename=filename)
        return job

    async def get_job(self, job_id: str) -> Job | None:
        key = _KEY_JOB.format(job_id)
        data = await self._redis.get(key)
        if data is None:
            return None
        return Job.model_validate_json(data)

    async def update_job(self, job_id: str, **kwargs: Any) -> None:
        job = await self.get_job(job_id)
        if job is None:
            log.warning("job.update.not_found", job_id=job_id)
            return

        # Apply updates to model fields
        updated = job.model_copy(update=kwargs)
        key = _KEY_JOB.format(job_id)
        # Preserve remaining TTL — use KEEPTTL (Redis >= 6.0)
        await self._redis.set(key, updated.model_dump_json(), keepttl=True)
        log.debug(
            "job.updated",
            job_id=job_id,
            status=updated.status,
            progress=updated.progress,
        )

    async def save_report(self, job_id: str, report: Report) -> None:
        key = _KEY_REPORT.format(job_id)
        await self._redis.set(key, report.model_dump_json(), ex=_REPORT_TTL)
        log.info("report.saved", job_id=job_id, total_found=report.total_found)

    async def get_report(self, job_id: str) -> Report | None:
        key = _KEY_REPORT.format(job_id)
        data = await self._redis.get(key)
        if data is None:
            return None
        return Report.model_validate_json(data)

    async def save_upload(self, job_id: str, content: bytes) -> None:
        key = _KEY_UPLOAD.format(job_id)
        await self._redis.set(key, content, ex=_UPLOAD_TTL)

    async def get_upload(self, job_id: str) -> bytes | None:
        key = _KEY_UPLOAD.format(job_id)
        return await self._redis.get(key)

    async def delete_upload(self, job_id: str) -> None:
        key = _KEY_UPLOAD.format(job_id)
        await self._redis.delete(key)
