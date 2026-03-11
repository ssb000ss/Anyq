from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from anyq.api.routes.check import router as check_router
from anyq.api.routes.jobs import router as jobs_router
from anyq.api.routes.results import router as results_router
from anyq.config import get_settings
from anyq.jobs.storage import RedisJobStorage
from anyq.query_gen.llm import OllamaQueryGenerator
from anyq.query_gen.rule_based import RuleBasedQueryGenerator
from anyq.search.orchestrator import SearchOrchestrator
from anyq.search.searxng import SearXNGClient

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Track background tasks to prevent GC and handle graceful shutdown
    app.state.background_tasks: set[asyncio.Task] = set()

    # Redis
    from redis.asyncio import from_url as redis_from_url

    redis = redis_from_url(settings.redis_url, decode_responses=False)
    storage = RedisJobStorage(redis)

    # Search
    searxng = SearXNGClient(settings.searxng_url)
    orchestrator = SearchOrchestrator(
        searxng=searxng,
        delay_min=settings.search_delay_min,
        delay_max=settings.search_delay_max,
    )

    # Query generators
    ollama_gen = OllamaQueryGenerator(settings.ollama_base_url, settings.ollama_model)
    rule_gen = RuleBasedQueryGenerator()

    # Inject into app state
    app.state.settings = settings
    app.state.storage = storage
    app.state.orchestrator = orchestrator
    app.state.ollama_gen = ollama_gen
    app.state.rule_gen = rule_gen

    log.info("anyq.started", searxng=settings.searxng_url, ollama=settings.ollama_base_url)

    yield

    # Graceful shutdown: cancel all running pipeline tasks
    tasks = list(app.state.background_tasks)
    if tasks:
        log.info("anyq.shutdown.cancelling_tasks", count=len(tasks))
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    await redis.aclose()
    log.info("anyq.stopped")


app = FastAPI(title="Anyq", version="0.1.0", lifespan=lifespan)

app.include_router(check_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(results_router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    checks: dict[str, bool] = {}

    import httpx

    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            r = await client.get(f"{settings.searxng_url}/healthz")
            checks["searxng"] = r.status_code == 200
        except Exception:
            checks["searxng"] = False

        try:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            checks["ollama"] = r.status_code == 200
        except Exception:
            checks["ollama"] = False

    try:
        await app.state.storage._redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    return {"status": "ok", **checks}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("/app/frontend/index.html")


try:
    app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")
except Exception:
    pass
