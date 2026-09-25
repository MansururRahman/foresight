FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_CACHE_DIR=/tmp/uv \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 10001 appuser \
    && rm -rf /tmp/uv && mkdir -p /keys && chown -R appuser:appuser /app /keys
USER appuser

EXPOSE 8001
# Runtime uses the venv binaries directly: no uv, no cache directory needed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
