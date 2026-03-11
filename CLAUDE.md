# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# First-time setup
make setup          # copies .env.example → .env, prints a generated secret key
# Then fill in .env: set SEARXNG_SECRET_KEY

# Run (Docker)
make up             # docker compose up -d
make down           # docker compose down
make logs           # tail anyq-api logs
make build          # rebuild images

# Local dev (no Docker)
uv sync             # install deps
make dev            # uvicorn with --reload on :8000
```

## Architecture

Single FastAPI app (`src/anyq/main.py`) with asyncio background tasks — no Celery.

**Request flow:**
1. `POST /api/check` — upload file → create Redis job → `asyncio.create_task(run_pipeline(...))`
2. `GET /api/jobs/{id}` — poll status (progress 0–100, current_step)
3. `GET /api/jobs/{id}/results` — fetch Report when status=done

**Pipeline** (`src/anyq/pipeline.py`):
```
Parse document → TF-IDF extract → generate queries (Ollama LLM + rule-based fallback)
→ SearchOrchestrator (proxy+UA rotation per query) → save Report to Redis
```

**Key modules:**
- `parsers/` — PDF (PyMuPDF), DOCX (python-docx), TXT; `factory.py` selects by extension
- `extractors/tfidf.py` — key phrases and representative sentences via sklearn TF-IDF
- `query_gen/llm.py` — Ollama LLM generates 5 queries; `rule_based.py` is the fallback
- `search/proxy_pool.py` — Tor SOCKS5 instances + free proxies from proxyscrape.com
- `search/orchestrator.py` — round-robin proxy + random UA per query, with delay
- `jobs/storage.py` — Redis job/report state; all models (Job, Report, SearchResult) defined here

## Infrastructure

```
docker-compose.yml:
  anyq-api    FastAPI app (:8000, localhost only)
  redis       job state store
  searxng     self-hosted search (internal only)
  tor-1/2/3   Tor SOCKS5 proxies (dperson/torproxy)

Ollama — runs on host, accessed via host.docker.internal:11434
```

SearXNG config: `docker/searxng/settings.yml` + `limiter.toml` (rate limiter disabled).

## Environment

All settings via `.env` (see `.env.example`). Key vars:
- `OLLAMA_MODEL` — LLM for query generation (default: `llama3.2`)
- `TOR_HOSTS` — set automatically by docker-compose (`tor-1:9050,tor-2:9050,tor-3:9050`)
- `SEARCH_DELAY_MIN/MAX` — anti-ban delay between queries (seconds)
- `SEARXNG_SECRET_KEY` — required, generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

## Extending

- **New file format**: add parser in `src/anyq/parsers/`, register in `factory.py`
- **New search engine**: SearXNG aggregates automatically; add engine to `docker/searxng/settings.yml`
- **More queries**: adjust `MAX_QUERIES_PER_DOC` in `.env`
