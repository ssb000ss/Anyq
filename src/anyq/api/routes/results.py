from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/jobs/{job_id}/results")
async def get_results(job_id: str, request: Request) -> JSONResponse:
    storage = request.app.state.storage

    job = await storage.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "failed":
        raise HTTPException(status_code=422, detail=job.error or "Job failed")

    if job.status != "done":
        raise HTTPException(
            status_code=202,
            detail=f"Job is not finished yet (status: {job.status})",
        )

    report = await storage.get_report(job_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return JSONResponse(report.model_dump(mode="json"))
