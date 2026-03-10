# Anyq — Plan

Сервис поиска документа в интернете. Принимает PDF/DOC/DOCX/TXT, ищет через поисковики с ротацией прокси и User-Agent, возвращает найденные источники.

---

## Что делает

```
Документ (PDF/DOC/DOCX/TXT)
    ↓
Извлечь:
  - Заголовок документа
  - Подзаголовки (H1-H4)
  - Тема документа (Ollama LLM)
  - Ключевые фразы (TF-IDF)
  - 3-5 характерных кусков текста
    ↓
Сгенерировать поисковые запросы (Ollama)
  - "заголовок filetype:pdf"
  - "заголовок"
  - по каждому подзаголовку
  - по ключевым фразам
  - по кускам текста в кавычках
    ↓
SearXNG поиск
  - каждый запрос через другой прокси (Tor / free proxy list)
  - каждый запрос с другим User-Agent
    ↓
Результат: [{url, title, snippet, query}]
```

---

## Стек

```
Docker Compose:
  anyq-api        FastAPI + uvicorn (порт 8000)
  searxng         self-hosted поиск
  redis           статус задачи (in-memory job state)
  tor-1           Tor SOCKS5 :9050
  tor-2           Tor SOCKS5 :9051
  tor-3           Tor SOCKS5 :9052

На хосте:
  Ollama          генерация поисковых запросов (LLM 8-12B)
```

---

## Структура проекта

```
anyq/
├── src/anyq/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # pydantic-settings
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── check.py         # POST /check — загрузить документ
│   │       ├── jobs.py          # GET /jobs/{id} — статус
│   │       └── results.py       # GET /jobs/{id}/results — ссылки
│   │
│   ├── parsers/
│   │   ├── base.py              # Protocol
│   │   ├── pdf.py               # PyMuPDF
│   │   ├── docx.py              # python-docx
│   │   ├── doc.py               # LibreOffice CLI
│   │   ├── txt.py               # plain text
│   │   └── factory.py           # выбор парсера по расширению
│   │
│   ├── extractors/
│   │   ├── structure.py         # заголовок, подзаголовки
│   │   ├── tfidf.py             # ключевые фразы
│   │   └── sampler.py           # характерные куски текста
│   │
│   ├── query_gen/
│   │   ├── llm.py               # Ollama → умные запросы
│   │   └── rule_based.py        # fallback без LLM
│   │
│   ├── search/
│   │   ├── searxng.py           # клиент SearXNG
│   │   ├── proxy_pool.py        # пул прокси (Tor + free list)
│   │   ├── ua_pool.py           # пул User-Agent строк
│   │   └── orchestrator.py      # ротация прокси+UA на каждый запрос
│   │
│   ├── jobs/
│   │   └── storage.py           # Redis: create/get/update job
│   │
│   └── pipeline.py              # главный pipeline (asyncio background task)
│
├── frontend/
│   └── index.html               # Alpine.js + Tailwind CDN
│
├── docker/
│   ├── tor/
│   │   └── torrc                # конфиг Tor
│   └── searxng/
│       ├── settings.yml
│       └── limiter.toml
│
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── pyproject.toml
└── .env.example
```

---

## Модели данных

```python
class JobStatus(StrEnum):
    PENDING    = "pending"
    PARSING    = "parsing"
    GENERATING = "generating_queries"
    SEARCHING  = "searching"
    DONE       = "done"
    FAILED     = "failed"

class Job(BaseModel):
    id: str                      # UUID
    status: JobStatus
    progress: int                # 0-100
    current_step: str | None
    filename: str
    created_at: datetime
    error: str | None = None

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    query: str                   # какой запрос нашёл этот результат
    engine: str                  # google / bing / duckduckgo

class Report(BaseModel):
    job_id: str
    results: list[SearchResult]
    queries_used: list[str]
    total_found: int
```

---

## Pipeline (asyncio background task)

```
[1/4] Парсинг документа          progress: 0→25
[2/4] Генерация запросов          progress: 25→40
[3/4] Поиск (N запросов)          progress: 40→90
[4/4] Сборка отчёта               progress: 90→100
```

---

## Прокси стратегия

- **Tor**: 3 инстанса в Docker, SOCKS5 на портах 9050/9051/9052
- **Free proxy scraper**: каждые 30 мин подтягивать с proxyscrape.com/geonode.com, тестировать живость
- **Ротация**: round-robin по пулу (Tor + живые free proxies)
- **Fallback**: если прокси мёртвый — брать следующий из пула
- **User-Agent**: пул из 50+ реальных браузерных строк, случайный на каждый запрос

---

## Поисковые запросы (на один документ)

1. `"заголовок документа" filetype:pdf`
2. `"заголовок документа"`
3. По каждому подзаголовку: `"подзаголовок"`
4. По TF-IDF фразам: `"уникальная фраза из документа"`
5. По кускам текста: `"характерное предложение в кавычках"`
6. Ollama генерирует дополнительные 3-5 запросов по теме

Итого: ~10-15 запросов на документ, каждый через другой прокси/UA.

---

## Фазы разработки

### Фаза 1 — Основа
- [ ] pyproject.toml, структура папок
- [ ] Парсеры (PDF, DOCX, TXT)
- [ ] Извлечение структуры (заголовки, TF-IDF)
- [ ] FastAPI endpoints (check, jobs, results)
- [ ] Redis job storage
- [ ] Pipeline skeleton

### Фаза 2 — Поиск
- [ ] SearXNG клиент
- [ ] Tor в Docker
- [ ] Free proxy scraper
- [ ] UA pool + ротация
- [ ] Orchestrator: запрос → прокси → UA → SearXNG

### Фаза 3 — Ollama
- [ ] Клиент Ollama
- [ ] Генерация запросов через LLM
- [ ] Fallback на rule-based если Ollama недоступна

### Фаза 4 — Инфраструктура
- [ ] docker-compose.yml
- [ ] Dockerfile (с LibreOffice для DOC)
- [ ] SearXNG конфиг
- [ ] .env.example

### Фаза 5 — Frontend
- [ ] index.html (Alpine.js + Tailwind)
- [ ] Upload → progress → results
- [ ] Список источников с сниппетами

---

## Переменные окружения (.env)

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2
SEARXNG_URL=http://searxng:8080
REDIS_URL=redis://redis:6379/0
UPLOAD_MAX_SIZE_MB=50
PROXY_REFRESH_INTERVAL=1800    # секунд между обновлением free proxy list
TOR_PORTS=9050,9051,9052
SEARCH_DELAY_MIN=1.5
SEARCH_DELAY_MAX=4.0
```
