from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from anyq.parsers.factory import SUPPORTED_EXTENSIONS

log = structlog.get_logger()
router = APIRouter()

_MAX_FILENAME_LEN = 255


@router.post("/check")
async def check_document(request: Request, file: UploadFile) -> JSONResponse:
    settings = request.app.state.settings
    storage = request.app.state.storage
    orchestrator = request.app.state.orchestrator
    ollama_gen = request.app.state.ollama_gen
    rule_gen = request.app.state.rule_gen

    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format {ext!r}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Read file
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(content) > settings.upload_max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.upload_max_size_mb} MB",
        )

    filename = (file.filename or "document")[:_MAX_FILENAME_LEN]

    # Create job
    job = await storage.create_job(filename)
    await storage.save_upload(job.id, content)

    # Run pipeline in background
    from anyq.pipeline import run_pipeline

    asyncio.create_task(
        run_pipeline(
            job_id=job.id,
            file_content=content,
            filename=filename,
            storage=storage,
            orchestrator=orchestrator,
            ollama_gen=ollama_gen,
            rule_gen=rule_gen,
            max_queries=settings.max_queries_per_doc,
        )
    )

    log.info("check.started", job_id=job.id, filename=filename)
    return JSONResponse({"job_id": job.id})
