# Stage 1: builder — install dependencies with uv
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests only (cache layer)
COPY pyproject.toml ./

# Create a minimal uv.lock-compatible install
# uv sync requires uv.lock; if absent, uv will resolve and install from pyproject.toml
COPY uv.lock* ./

# Install prod dependencies into /app/.venv (no dev extras)
RUN uv sync --frozen --no-dev --no-editable 2>/dev/null || \
    uv sync --no-dev --no-editable

# Stage 2: runtime — lean image, non-root user
FROM python:3.12-slim AS runtime

# Install curl for healthcheck — single layer, no apt cache kept
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd --system anyq && useradd --system --gid anyq --no-create-home anyq

WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY src/ ./src/

# Copy frontend (static files — optional, may be empty)
# Mounted at runtime via volume, but bake the directory so it exists
RUN mkdir -p /app/frontend

# Ensure anyq user owns the working directory
RUN chown -R anyq:anyq /app

# Activate venv by putting it first on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER anyq

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "anyq.main:app", "--host", "0.0.0.0", "--port", "8000"]
