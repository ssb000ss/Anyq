from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from anyq.api.routes.check import router as check_router
from anyq.api.routes.jobs import router as jobs_router
from anyq.api.routes.results import router as results_router
from anyq.config import get_settings
from anyq.jobs.storage import RedisJobStorage
from anyq.query_gen.llm import OllamaQueryGenerator
from anyq.query_gen.rule_based import RuleBasedQueryGenerator
from anyq.search.orchestrator import SearchOrchestrator
from anyq.search.proxy_pool import ProxyPool
from anyq.search.searxng import SearXNGClient

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Redis
    from redis.asyncio import from_url as redis_from_url

    redis = redis_from_url(settings.redis_url, decode_responses=False)
    storage = RedisJobStorage(redis)

    # Proxy pool
    tor_hosts_raw = getattr(settings, "tor_hosts", "")
    if tor_hosts_raw:
        tor_hosts = [h.strip() for h in tor_hosts_raw.split(",") if h.strip()]
    else:
        tor_hosts = [f"tor-{i}:9050" for i in range(1, 4)]

    proxy_pool = ProxyPool(tor_hosts)

    # Start background proxy refresh
    refresh_task = asyncio.create_task(
        proxy_pool.start_refresh_loop(settings.proxy_refresh_interval)
    )

    # Search
    searxng = SearXNGClient(settings.searxng_url)
    orchestrator = SearchOrchestrator(
        proxy_pool=proxy_pool,
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
    app.state.proxy_pool = proxy_pool
    app.state.orchestrator = orchestrator
    app.state.ollama_gen = ollama_gen
    app.state.rule_gen = rule_gen

    log.info("anyq.started", searxng=settings.searxng_url, ollama=settings.ollama_base_url)

    yield

    refresh_task.cancel()
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

    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.searxng_url}/healthz")
            checks["searxng"] = r.status_code == 200
    except Exception:
        checks["searxng"] = False

    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            checks["ollama"] = r.status_code == 200
    except Exception:
        checks["ollama"] = False

    try:
        redis = app.state.storage._redis
        await redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    return {"status": "ok", **checks}


@app.get("/")
async def index():
    return FileResponse("/app/frontend/index.html")


# Mount static files for frontend assets if needed
try:
    app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")
except Exception:
    pass
