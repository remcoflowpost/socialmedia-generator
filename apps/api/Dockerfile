# Build-context: de root van de repo (config/, templates/ en seed/ zijn nodig).
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /repo/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api ./
COPY config /repo/config
COPY templates /repo/templates
COPY seed /repo/seed
COPY packages/schema/schema.json /repo/packages/schema/schema.json

ENV PATH="/repo/apps/api/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
