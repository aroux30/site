#!/usr/bin/env bash
#
# Celery worker entrypoint. The beat scheduler uses the same script with
# MODE=beat (compose sets it), so worker and beat share one startup contract
# and the queue list cannot drift between them.

set -Eeuo pipefail

log() { printf '[worker] %s\n' "$*"; }
die() { printf '[worker] ERROR: %s\n' "$*" >&2; exit 1; }

[ -n "${CELERY_BROKER_URL:-}" ] || die "CELERY_BROKER_URL is not set"
[ -n "${DATABASE_URL:-}" ] || die "DATABASE_URL is not set"

MODE="${MODE:-worker}"
LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"

if [ "${MODE}" = "beat" ]; then
    log "starting beat scheduler"
    # Beat must run as a SINGLE instance: two schedulers double-fire every
    # periodic task, which for the backup/outbox jobs means duplicate work.
    exec celery -A app.worker.celery_app:celery_app beat \
        --loglevel="${LOG_LEVEL}" \
        --schedule=/tmp/celerybeat-schedule
fi

log "starting worker (concurrency=${CELERY_CONCURRENCY:-8})"
exec celery -A app.worker.celery_app:celery_app worker \
    --loglevel="${LOG_LEVEL}" \
    --concurrency="${CELERY_CONCURRENCY:-8}" \
    --max-tasks-per-child="${CELERY_MAX_TASKS_PER_CHILD:-1000}" \
    --without-gossip \
    --without-mingle
