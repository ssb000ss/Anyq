from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import JSONResponse

router = APIRouter()

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
JobId = Annotated[str, Path(pattern=_UUID_PATTERN)]


@router.get("/jobs/{job_id}")
async def get_job(job_id: JobId, request: Request) -> JSONResponse:
    storage = request.app.state.storage
    job = await storage.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(job.model_dump(mode="json"))
