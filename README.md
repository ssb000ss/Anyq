# Anyq

**Anyq** — self-hosted сервис для поиска источника документа в интернете.

Загружаете PDF, DOCX или TXT → сервис извлекает заголовок, ключевые фразы и предложения → генерирует поисковые запросы через Ollama LLM → отправляет их через SearXNG с ротацией IP через Tor → возвращает список сайтов, где документ опубликован или упоминается.

```
Документ → TF-IDF → LLM (Ollama) → SearXNG ──► Tor-1 → Google
                                              ├──► Tor-2 → Bing
                                              └──► Tor-3 → DuckDuckGo / Brave
```

---

## Быстрый старт

### Требования

- **Docker** + **Docker Compose v2**
- **Ollama** на хосте (опционально — без него работает rule-based fallback)

### Запуск

```bash
git clone https://github.com/ssb000ss/Anyq.git && cd Anyq

make setup        # создаёт .env с автоматически сгенерированным ключом
ollama pull llama3.2  # опционально, для умной генерации запросов
make build        # сборка образов (нужна один раз)
make up           # запуск всех сервисов
```

Откройте **http://localhost:8000** — загрузите документ и нажмите «Найти в интернете».

> Обработка занимает 2–5 минут — Tor медленный, это норма.

---

## Команды

| Команда | Описание |
|---------|----------|
| `make setup` | Создать `.env` с автогенерацией `SEARXNG_SECRET_KEY` |
| `make build` | Собрать / пересобрать Docker-образы |
| `make up` | Запустить все сервисы в фоне |
| `make down` | Остановить все сервисы |
| `make logs` | Следить за логами API |
| `make dev` | Запустить API локально с hot-reload (нужен `uv`) |

---

## Конфигурация

Все настройки — в файле `.env` (создаётся через `make setup`):

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `SEARXNG_SECRET_KEY` | *(автогенерация)* | Ключ SearXNG, обязателен |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | URL Ollama |
| `OLLAMA_MODEL` | `llama3.2` | Модель для генерации запросов (8–12B) |
| `SEARCH_DELAY_MIN` | `1.5` | Минимальная задержка между запросами (сек) |
| `SEARCH_DELAY_MAX` | `4.0` | Максимальная задержка между запросами (сек) |
| `MAX_QUERIES_PER_DOC` | `15` | Максимум поисковых запросов на документ |
| `UPLOAD_MAX_SIZE_MB` | `50` | Максимальный размер загружаемого файла |

---

## Сервисы

| Контейнер | Порт | Роль |
|-----------|------|------|
| `anyq-api` | 8000 | FastAPI приложение — **http://localhost:8000** |
| `anyq-searxng` | 8081 | SearXNG UI — **http://localhost:8081** |
| `anyq-redis` | — | Хранилище задач (внутренний) |
| `anyq-tor-1/2/3` | — | Tor SOCKS5 прокси (внутренние) |

---

## API

Интерактивная документация после `make up`:

- **Swagger UI** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc
- **OpenAPI JSON** → http://localhost:8000/openapi.json

Полное описание — в [USAGE.md](USAGE.md#api-reference).

---

## Поддерживаемые форматы

| Формат | Парсер | Примечание |
|--------|--------|------------|
| PDF | PyMuPDF | Определение заголовков по размеру шрифта |
| DOCX | python-docx | Стили `Heading 1/2/3` |
| TXT | встроенный | Авто-определение кодировки: UTF-8, CP1251, Latin-1 |

DOC (старый бинарный) не поддерживается — конвертируйте в DOCX.

---

## Архитектура

```
src/anyq/
├── api/routes/
│   ├── check.py        # POST /api/check — загрузка и старт задачи
│   ├── jobs.py         # GET  /api/jobs/{id} — статус задачи
│   └── results.py      # GET  /api/jobs/{id}/results
├── parsers/            # PDF, DOCX, TXT парсеры
├── extractors/         # TF-IDF: ключевые фразы и предложения
├── query_gen/          # Ollama LLM + rule-based генераторы запросов
├── search/
│   ├── searxng.py      # HTTP-клиент SearXNG
│   └── orchestrator.py # Fan-out запросов с задержками и дедупликацией
├── jobs/storage.py     # Redis: хранение Job и Report (TTL 24ч)
├── pipeline.py         # Главный pipeline: парсинг → запросы → поиск
├── config.py           # Pydantic-settings из .env
└── main.py             # FastAPI app, lifespan, роуты

docker/
├── tor/Dockerfile      # Alpine + Tor (amd64 + arm64)
└── searxng/
    ├── Dockerfile      # Кастомный образ с инжекцией secret_key
    ├── entrypoint.sh   # Инжект SEARXNG_SECRET_KEY → settings.yml
    └── settings.yml    # Конфигурация: движки, Tor-прокси, лимиты
```

---

## Устранение неполадок

**SearXNG не стартует**
```bash
make down && make build && make up
```

**Нет результатов / поиск не работает**
```bash
docker compose ps                    # проверить статус контейнеров
docker compose logs anyq-tor-1       # лог Tor
docker compose logs anyq-searxng     # лог SearXNG
```

**Ollama недоступен (используется rule-based fallback)**
```bash
curl http://localhost:11434/api/tags
docker compose exec anyq-api curl http://host.docker.internal:11434/api/tags
```

**Задача завис в `running`**
```bash
make logs    # искать ошибки таймаута или парсинга
```

Подробнее — в [USAGE.md](USAGE.md).

---

## Локальная разработка

```bash
uv sync                        # установить зависимости
docker compose up -d redis     # Redis нужен даже локально
make dev                       # API на :8000 с hot-reload
uv run ruff check src/         # линтер
uv run pytest                  # тесты
```
