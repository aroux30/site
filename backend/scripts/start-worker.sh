#!/usr/bin/env bash
# Start a Celery worker process.
#
# Environment variables:
#   CELERY_CONCURRENCY – Number of concurrent worker threads/processes (default: 4)
#   CELERY_QUEUES      – Comma-separated list of queues (default: all)
#   LOG_LEVEL          – Worker log level (default: info)

set -euo pipefail

CONCURRENCY="${CELERY_CONCURRENCY:-4}"
LOG_LEVEL="${LOG_LEVEL:-info}"
QUEUES="${CELERY_QUEUES:-default,high_priority,notifications,payments,analytics}"

echo "==> Starting Celery worker (concurrency=${CONCURRENCY}, queues=${QUEUES})"

exec celery -A app.worker.celery_app worker \
    --loglevel="$LOG_LEVEL" \
    --concurrency="$CONCURRENCY" \
    --queues="$QUEUES" \
    --max-tasks-per-child=1000 \
    --without-heartbeat \
    --without-mingle \
    --without-gossip \
    -E
