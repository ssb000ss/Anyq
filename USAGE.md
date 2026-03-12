# Anyq — Руководство по использованию

## Содержание

1. [Первый запуск](#первый-запуск)
2. [Использование UI](#использование-ui)
3. [API Reference](#api-reference)
4. [Использование curl](#использование-curl)
5. [SearXNG UI](#searxng-ui)
6. [Настройка Ollama](#настройка-ollama)
7. [Как работает поиск](#как-работает-поиск)
8. [Диагностика](#диагностика)

---

## Первый запуск

### 1. Установка зависимостей

Убедитесь, что установлены:

```bash
docker --version          # Docker 24+
docker compose version    # Docker Compose v2.x
```

### 2. Настройка окружения

```bash
make setup
```

Команда создаёт `.env` из `.env.example` и автоматически генерирует `SEARXNG_SECRET_KEY`.

Пример `.env` после `make setup`:

```env
SEARXNG_SECRET_KEY=xK9mP2vQnR7tL4wA8jY1sU6hD3fB5eC0

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2

SEARCH_DELAY_MIN=1.5
SEARCH_DELAY_MAX=4.0
MAX_QUERIES_PER_DOC=15

UPLOAD_MAX_SIZE_MB=50
```

> Редактировать `.env` вручную можно в любой момент. После изменений — `make build && make up`.

### 3. Сборка образов

```bash
make build
```

Собирает кастомные Docker-образы: API, SearXNG с инжекцией ключа, Tor на Alpine.

### 4. Запуск

```bash
make up
```

Запускает 6 контейнеров:

```
anyq-api       → http://localhost:8000
anyq-searxng   → http://localhost:8081
anyq-redis     (внутренний)
anyq-tor-1/2/3 (внутренние)
```

Проверка статуса:

```bash
docker compose ps
```

Все контейнеры должны быть в статусе `running` или `healthy`. Tor поднимается ~60 секунд при первом старте.

---

## Использование UI

Откройте **http://localhost:8000**

### Шаг 1 — Загрузка документа

- Перетащите файл в зону загрузки или нажмите на неё
- Поддерживаемые форматы: **PDF**, **DOCX**, **TXT**
- Максимальный размер: **50 МБ** (настраивается через `UPLOAD_MAX_SIZE_MB`)
- Нажмите **«Найти в интернете»**

### Шаг 2 — Обработка

Отображается круговой прогресс с текущим шагом:

| Шаг | Что происходит |
|-----|----------------|
| Парсинг документа | Извлечение текста, заголовков, структуры |
| Извлечение ключевых фраз | TF-IDF анализ: топ-фразы и репрезентативные предложения |
| Генерация запросов | Ollama LLM создаёт 5–15 поисковых запросов |
| Поиск | Запросы отправляются через SearXNG + Tor |
| Готово | Результаты сохранены в Redis |

> Обработка занимает **2–5 минут** из-за медленных Tor-цепочек. Таймер показывает сколько прошло.

### Шаг 3 — Результаты

- Список источников с заголовком, URL, сниппетом
- Показывает поисковый движок и запрос, который нашёл каждый результат
- Кнопка копирования URL у каждого результата
- «Показать запросы» — все запросы, которые использовались

---

## API Reference

### POST /api/check

Загрузить документ и запустить поиск.

**Запрос:**
```
POST /api/check
Content-Type: multipart/form-data

file: <binary>   # PDF, DOCX или TXT файл
```

**Ответ `202 Accepted`:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Ошибки:**
```
400 — неверный формат файла
413 — файл превышает UPLOAD_MAX_SIZE_MB
429 — слишком много одновременных задач (лимит 3)
```

---

### GET /api/jobs/{job_id}

Получить статус задачи.

**Ответ `200 OK`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 45,
  "current_step": "Отправляем запрос 3/10...",
  "error": null,
  "created_at": "2026-03-11T10:00:00Z"
}
```

**Поле `status`:**

| Значение | Описание |
|----------|----------|
| `queued` | Задача создана, ожидает очереди |
| `running` | Идёт обработка |
| `done` | Завершено успешно |
| `failed` | Ошибка (причина в поле `error`) |

**Поле `progress`:** число от 0 до 100.

---

### GET /api/jobs/{job_id}/results

Получить результаты поиска.

**Ответ `200 OK`** (когда `status = done`):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_found": 7,
  "queries_used": [
    "\"Название документа\" filetype:pdf",
    "Ключевая фраза из документа site:gov.ru",
    "\"точная цитата из текста\""
  ],
  "results": [
    {
      "title": "Название страницы",
      "url": "https://example.com/document.pdf",
      "snippet": "Фрагмент текста с совпадением...",
      "engine": "google",
      "query": "\"Название документа\" filetype:pdf"
    }
  ],
  "created_at": "2026-03-11T10:03:42Z"
}
```

**Другие коды:**
```
202 — задача ещё выполняется
404 — job_id не найден или истёк (TTL 24 часа)
422 — задача завершилась с ошибкой
```

---

### GET /health

Проверка состояния сервиса.

```json
{ "status": "ok" }
```

---

## Использование curl

### Загрузить документ и получить job_id

```bash
JOB_ID=$(curl -s -X POST http://localhost:8000/api/check \
  -F "file=@/path/to/document.pdf" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

echo "Job ID: $JOB_ID"
```

### Опрос статуса

```bash
curl -s http://localhost:8000/api/jobs/$JOB_ID | python3 -m json.tool
```

### Дождаться завершения и получить результаты

```bash
while true; do
  STATUS=$(curl -s http://localhost:8000/api/jobs/$JOB_ID | python3 -c \
    "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "done" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done

curl -s http://localhost:8000/api/jobs/$JOB_ID/results | python3 -m json.tool
```

### Полный сценарий одной командой

```bash
# Загружаем и ждём результатов
FILE="document.pdf"
JOB_ID=$(curl -s -X POST http://localhost:8000/api/check \
  -F "file=@$FILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

echo "Started: $JOB_ID"

while true; do
  RESP=$(curl -s http://localhost:8000/api/jobs/$JOB_ID)
  STATUS=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  PROG=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['progress'])")
  echo "[$PROG%] $STATUS"
  [ "$STATUS" = "done" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done

curl -s http://localhost:8000/api/jobs/$JOB_ID/results | python3 -m json.tool
```

---

## SearXNG UI

SearXNG доступен по адресу **http://localhost:8081** и может использоваться как самостоятельный поисковик.

Особенности конфигурации в Anyq:

- Включены движки: **Google**, **Bing**, **DuckDuckGo**, **Brave**, **Google Scholar**
- Все запросы идут через Tor (3 узла, разные IP)
- Rate limiter отключён (все запросы от Anyq доверенные)
- Язык по умолчанию: `ru-RU`
- Safe search: отключён

Изменить набор движков можно в `docker/searxng/settings.yml`. После изменений нужен `make build && make up`.

---

## Настройка Ollama

Ollama используется для умной генерации поисковых запросов. Без него работает rule-based генератор.

### Установка Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### Запуск и выбор модели

```bash
ollama serve          # запустить если не запущен

ollama pull llama3.2  # рекомендуется (3B, быстрый)
ollama pull llama3.1  # лучше качество (8B)
ollama pull gemma3    # альтернатива
```

### Изменить модель в .env

```env
OLLAMA_MODEL=llama3.1
```

После изменения перезапуск API: `make down && make up`

### Проверка доступности из контейнера

```bash
docker compose exec anyq-api curl -s http://host.docker.internal:11434/api/tags \
  | python3 -m json.tool
```

Если команда возвращает список моделей — Ollama работает корректно.

---

## Как работает поиск

### Pipeline

```
1. Парсинг
   └── PDF → PyMuPDF (заголовки по размеру шрифта)
   └── DOCX → python-docx (стили Heading 1/2/3)
   └── TXT → авто-определение кодировки

2. Извлечение признаков (TF-IDF)
   └── Топ ключевых фраз (1–3 слова)
   └── Репрезентативные предложения

3. Генерация запросов
   └── Ollama LLM: 5–15 запросов с операторами (filetype:, site:, кавычки)
   └── Fallback: rule-based из заголовка + фраз

4. Поиск (SearchOrchestrator)
   └── Запросы отправляются через SearXNG последовательно
   └── Задержка SEARCH_DELAY_MIN–MAX секунд между запросами
   └── SearXNG ротирует Tor exit nodes автоматически

5. Дедупликация и сохранение
   └── Результаты по всем запросам объединяются
   └── Дубликаты по URL удаляются
   └── Report сохраняется в Redis (TTL 24ч)
```

### Типы генерируемых запросов

LLM создаёт запросы разных типов для лучшего покрытия:

```
"Точный заголовок документа"
"Точный заголовок" filetype:pdf
ключевые слова из документа
"точная цитата из текста"
ключевые слова site:конкретный_домен
```

---

## Диагностика

### Все сервисы запущены?

```bash
docker compose ps
```

Ожидаемый статус:
```
anyq-api       running   (healthy)
anyq-redis     running   (healthy)
anyq-searxng   running   (healthy)
anyq-tor-1     running   (healthy)
anyq-tor-2     running   (healthy)
anyq-tor-3     running   (healthy)
```

Tor может показывать `starting` первые 60 секунд — это норма.

### Логи

```bash
make logs                              # API
docker compose logs anyq-searxng       # SearXNG
docker compose logs anyq-tor-1         # Tor узел 1
docker compose logs --follow           # все сервисы
```

### Частые проблемы

**SearXNG в restart loop**
```bash
make down
make build   # пересборка образа с инжекцией ключа
make up
```

**Tor не поднимается**
```bash
docker compose logs anyq-tor-1
# Если ошибки сети — Tor блокируется провайдером.
# Попробуйте добавить bridges в docker/tor/torrc
```

**Нет результатов из Google**
Google активно блокирует Tor exit nodes. Это нормально. Bing и DuckDuckGo обычно работают.

**Задача зависла**
```bash
make logs   # смотреть таймауты
# Если задача не обновляется 10+ минут — перезапустить API:
docker compose restart anyq-api
```

**Результаты устарели / Redis переполнен**
```bash
docker compose exec anyq-redis redis-cli FLUSHDB
```

### Проверка SearXNG напрямую

```bash
curl -s "http://localhost:8081/search?q=test&format=json" | python3 -m json.tool
```

Должен вернуть JSON с результатами поиска.

### Проверка API

```bash
curl http://localhost:8000/health
# → {"status": "ok"}

curl http://localhost:8000/docs
# → Swagger UI HTML
```
