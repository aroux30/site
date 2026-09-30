# Backend image — FastAPI + Celery, multi-stage so build tooling never ships.
#
# Python 3.12 to match `requires-python = ">=3.12"` in pyproject.toml. The
# development host runs a newer interpreter; pinning here keeps what is tested
# and what is deployed on the same minor line.

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential is needed by asyncpg/argon2-cffi wheels only when a wheel is
# unavailable for the platform; keeping it in the builder stage means the
# runtime image stays free of a compiler.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app

# A venv (not --user) so the runtime stage can copy exactly one directory.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_HOME=/app

# curl: container healthcheck. libpq5: psycopg-style client libs some wheels
# link against at runtime. No compilers, no package managers beyond apt.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR ${APP_HOME}
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini manage.py ./
COPY --chown=appuser:appuser scripts ./scripts

# Uploads and logs are written at runtime; owning them here avoids a root-owned
# volume the app user cannot write to (the classic upload-500-after-deploy).
RUN mkdir -p /app/media /app/logs /app/uploads \
    && chown -R appuser:appuser /app/media /app/logs /app/uploads

USER appuser

EXPOSE 8000

# Liveness only — /readyz checks downstream dependencies and belongs in the
# orchestrator's readiness probe, not here (a slow database would otherwise
# make Docker restart a perfectly healthy process).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["bash", "scripts/start.sh"]
