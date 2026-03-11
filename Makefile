.PHONY: up down logs build setup dev

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f anyq-api

build:
	docker compose build --no-cache

setup:
	@cp -n .env.example .env 2>/dev/null && echo "Created .env" || echo ".env already exists"
	@python3 -c "import secrets; print('Generated key:', secrets.token_urlsafe(32))"

dev:
	uv run uvicorn anyq.main:app --reload --host 0.0.0.0 --port 8000
