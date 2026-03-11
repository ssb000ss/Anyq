from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> JSONResponse:
    storage = request.app.state.storage
    job = await storage.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(job.model_dump(mode="json"))
