#!/usr/bin/env bash
# Start the FastAPI application with uvicorn.
#
# Environment variables:
#   HOST        – Bind address (default: 0.0.0.0)
#   PORT        – Bind port    (default: 8000)
#   WORKERS     – Number of worker processes (default: 4)
#   LOG_LEVEL   – Uvicorn log level (default: info)
#   ENVIRONMENT – When "development", enables auto-reload

set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-4}"
LOG_LEVEL="${LOG_LEVEL:-info}"
ENVIRONMENT="${ENVIRONMENT:-production}"

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting uvicorn on ${HOST}:${PORT} (workers=${WORKERS})"

if [ "$ENVIRONMENT" = "development" ]; then
    exec uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level "$LOG_LEVEL"
else
    exec uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --proxy-headers \
        --forwarded-allow-ips='*' \
        --access-log \
        --no-server-header
fi
