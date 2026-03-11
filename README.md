# Anyq

Self-hosted service that takes a document (PDF, DOCX, TXT) and searches the internet to find where it came from — which websites host or reference it.

**How it works:** extracts the title, headings, and key phrases from the document → generates search queries via Ollama LLM (or rule-based fallback) → sends them through SearXNG (which rotates across Google / Bing / DuckDuckGo / Brave via Tor exit nodes) → deduplicates and returns matching URLs.

```
Browser → FastAPI → SearXNG → Tor-1 → Google
                              Tor-2 → Bing
                              Tor-3 → DuckDuckGo
```

## Requirements

- Docker + Docker Compose (v2)
- [Ollama](https://ollama.com) running on the host (optional, rule-based fallback is used if unavailable)

## Quick start

```bash
# 1. Clone
git clone <repo-url> anyq && cd anyq

# 2. Create .env and generate a random secret key
make setup

# 3. Pull the Ollama model you want to use (optional)
ollama pull llama3.2

# 4. Build and start all services
make up

# 5. Open the UI
open http://localhost:8000
```

That's it. Upload a PDF/DOCX/TXT and Anyq will search for its origin.

## Make targets

| Target | Description |
|--------|-------------|
| `make setup` | Copy `.env.example` → `.env`, generate random `SEARXNG_SECRET_KEY` |
| `make up` | Start all services in background (`docker compose up -d`) |
| `make down` | Stop all services |
| `make build` | Rebuild images without cache |
| `make logs` | Follow logs of the API container |
| `make dev` | Run API locally with hot-reload (requires `uv`) |

## Configuration

All settings are in `.env` (created by `make setup`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_SECRET_KEY` | *(generated)* | Required by SearXNG |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2` | Model for query generation. Any 8–12B model works well |
| `SEARCH_DELAY_MIN` | `1.5` | Min delay between search requests (seconds) |
| `SEARCH_DELAY_MAX` | `4.0` | Max delay between search requests (seconds) |
| `MAX_QUERIES_PER_DOC` | `15` | Max search queries generated per document |
| `UPLOAD_MAX_SIZE_MB` | `50` | Max upload file size |

## Architecture

```
anyq/
├── src/anyq/
│   ├── api/
│   │   └── routes/
│   │       ├── check.py      # POST /api/check — upload & start job
│   │       ├── jobs.py       # GET  /api/jobs/{id} — job status
│   │       └── results.py    # GET  /api/jobs/{id}/results
│   ├── parsers/              # PDF (PyMuPDF), DOCX, TXT parsers
│   ├── extractors/           # TF-IDF key phrase + sentence extraction
│   ├── query_gen/            # LLM (Ollama) + rule-based query generators
│   ├── search/
│   │   ├── searxng.py        # SearXNG HTTP client
│   │   └── orchestrator.py   # Fan-out queries, delay, dedup
│   ├── jobs/
│   │   └── storage.py        # Redis job + report storage (TTL 24h)
│   ├── pipeline.py           # Orchestrates the full flow per job
│   ├── config.py             # Pydantic settings
│   └── main.py               # FastAPI app, lifespan, routing
├── docker/
│   ├── tor/Dockerfile        # Custom Alpine+Tor image (amd64 + arm64)
│   └── searxng/
│       ├── settings.yml      # SearXNG config with Tor outgoing proxies
│       └── limiter.toml      # Rate limiter config
├── frontend/
│   └── index.html            # Alpine.js + Tailwind UI (no build step)
├── Dockerfile                # Multi-stage Python image
├── docker-compose.yml
└── pyproject.toml
```

### Services

| Container | Port | Role |
|-----------|------|------|
| `anyq-api` | 8000 | FastAPI application |
| `anyq-redis` | — | Job queue and results storage (internal) |
| `anyq-searxng` | 8081 | Meta-search engine — http://localhost:8081 |
| `anyq-tor-1/2/3` | — | Tor SOCKS5 proxies for IP rotation (internal) |

### API

После запуска (`make up`) интерактивная документация доступна прямо в браузере:

- **Swagger UI** — http://localhost:8000/docs
- **ReDoc** — http://localhost:8000/redoc
- **OpenAPI JSON** — http://localhost:8000/openapi.json

Там можно сразу попробовать эндпоинты без curl.

**Эндпоинты:**

```
POST /api/check
  Content-Type: multipart/form-data
  file: <file>
  → 202 { "job_id": "uuid" }

GET /api/jobs/{job_id}
  → 200 { "id", "status", "progress", "current_step", "error", "created_at" }
  status: queued | running | done | failed

GET /api/jobs/{job_id}/results
  → 200 { "job_id", "total_found", "queries_used", "results": [...], "created_at" }
  → 202 if not done yet
  → 422 if job failed

GET /health
  → 200 { "status": "ok" }
```

## Tor and proxy rotation

Search requests from SearXNG are routed through three independent Tor instances (`tor-1`, `tor-2`, `tor-3`). Each uses a different circuit (exit node), providing IP diversity across queries. This is configured in `docker/searxng/settings.yml`:

```yaml
outgoing:
  proxies:
    all://:
      - socks5h://tor-1:9050
      - socks5h://tor-2:9050
      - socks5h://tor-3:9050
```

SearXNG selects a proxy from the list per request. If one Tor node fails its healthcheck, only that node is affected.

> **Note:** Tor circuits are slow (5–15s per request). Processing a document with 15 queries takes ~2–5 minutes. This is expected.

## Local development

```bash
# Install dependencies
uv sync

# Run Redis (needed for dev)
docker compose up -d redis

# Start API with hot-reload
make dev
# → http://localhost:8000

# Run linter
uv run ruff check src/

# Run tests
uv run pytest
```

## Supported formats

| Format | Parser | Notes |
|--------|--------|-------|
| PDF | PyMuPDF | Font-size heuristics for heading detection |
| DOCX | python-docx | Heading styles (`Heading 1/2/3`) |
| TXT | built-in | Auto-detects encoding: UTF-8, CP1251, Latin-1 |

DOC (old binary format) is not supported — convert to DOCX first.

## Troubleshooting

**SearXNG doesn't start / permission error**
```bash
make down && make build && make up
```

**No results / all searches fail**
Check that Tor nodes are healthy:
```bash
docker compose ps
docker compose logs anyq-tor-1
```

**Ollama queries fail, falling back to rule-based**
Verify Ollama is running and accessible from Docker:
```bash
curl http://localhost:11434/api/tags
docker compose exec anyq-api curl http://host.docker.internal:11434/api/tags
```

**Job stuck in `running`**
```bash
make logs
```
Look for timeout or parse errors in the output.
