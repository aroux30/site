#!/usr/bin/env bash
# Start the Celery Beat scheduler.
#
# Beat is responsible for dispatching periodic tasks defined in
# ``app.worker.celery_app.conf.beat_schedule``.
#
# Environment variables:
#   LOG_LEVEL – Scheduler log level (default: info)

set -euo pipefail

LOG_LEVEL="${LOG_LEVEL:-info}"

echo "==> Starting Celery Beat scheduler"

exec celery -A app.worker.celery_app beat \
    --loglevel="$LOG_LEVEL" \
    --schedule=/tmp/celerybeat-schedule \
    --pidfile=/tmp/celerybeat.pid
