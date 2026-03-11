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
	@SECRET=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
	 sed -i '' "s/change-me-to-random-secret/$$SECRET/" .env 2>/dev/null || \
	 sed -i "s/change-me-to-random-secret/$$SECRET/" .env; \
	 echo "SEARXNG_SECRET_KEY set in .env"

dev:
	uv run uvicorn anyq.main:app --reload --host 0.0.0.0 --port 8000
