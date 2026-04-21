# syntax=docker/dockerfile:1.7
#
# Recruitment Assistant — CrewAI backend image.
#
# PRD §3 infra: single container, sized for 1-5 concurrent sessions.
# SAD §5 MVP deployment: the crew service runs behind a FastAPI wrapper
# (/crew/run, /crew/coach, /crew/tailor) that the Next.js API routes call.
# That wrapper is not yet in the repo - this image currently serves the
# `run_crew` one-shot CLI (main:run). When the FastAPI sidecar lands,
# replace the CMD with the uvicorn invocation noted at the bottom; the
# builder stage already has everything needed.
#
# Image contract:
#   - Python 3.12 runtime (pyproject.toml: >=3.10,<3.14)
#   - Dependencies resolved via `uv sync --frozen` from uv.lock
#   - Runs as non-root user `app` (UID 1000)
#   - Expects ANTHROPIC_API_KEY and MODEL env vars at run time
#   - Logs to stdout (SAD §5 audit trail)

# ---------------------------------------------------------------------
# Builder: resolve and install dependencies with uv into /app/.venv
# ---------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install third-party deps first so the layer is cached when only src/ changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Install the project itself (editable target resolved from src/).
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------
# Runtime: slim python base + pre-built venv, non-root execution
# ---------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --create-home --shell /bin/bash app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

# SAD §4 reserves 8000 for the FastAPI sidecar. Exposed here so the
# Compose stack (web + crew) needs no Dockerfile edit once the wrapper
# is added.
EXPOSE 8000

# One-shot CLI today. When the FastAPI sidecar lands, swap to:
#   CMD ["uvicorn", "recruitment_assistant.api:app", \
#        "--host", "0.0.0.0", "--port", "8000"]
CMD ["run_crew"]
