#!/usr/bin/env bash
#
# Backend container entrypoint.
#
# Referenced by .env.example (FORWARDED_ALLOW_IPS) and docker-compose.yml.
# Responsibilities, in order:
#   1. fail fast if the environment is not production-valid
#   2. wait for PostgreSQL (a cold compose start races the database)
#   3. apply migrations — the schema is owned by alembic, never by create_all
#   4. exec uvicorn with the worker count and proxy trust the env specifies
#
# Runs as a non-root user inside the image; nothing here needs root.

set -Eeuo pipefail

log() { printf '[start] %s\n' "$*"; }
die() { printf '[start] ERROR: %s\n' "$*" >&2; exit 1; }

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_WORKERS="${BACKEND_WORKERS:-4}"

# ── 1. Environment sanity ────────────────────────────────────────────────────
[ -n "${DATABASE_URL:-}" ] || die "DATABASE_URL is not set"
[ -n "${JWT_SECRET_KEY:-}" ] || die "JWT_SECRET_KEY is not set"

if [ "${ENVIRONMENT:-development}" = "production" ]; then
    log "production mode — settings validators will reject placeholder secrets"
else
    log "ENVIRONMENT=${ENVIRONMENT:-development} (not production)"
fi

# ── 2. Wait for PostgreSQL ───────────────────────────────────────────────────
# Alembic needs the database; compose starts it in parallel. Retry rather than
# sleep-and-hope, and give up loudly so a genuinely broken DB does not look
# like a hung container.
DB_WAIT_SECONDS="${DB_WAIT_SECONDS:-60}"
waited=0
log "waiting for the database (up to ${DB_WAIT_SECONDS}s)"
until python - <<'PY' 2>/dev/null
import asyncio, os, sys
import asyncpg

dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

async def probe() -> None:
    conn = await asyncpg.connect(dsn, timeout=3)
    await conn.close()

try:
    asyncio.run(probe())
except Exception:
    sys.exit(1)
PY
do
    waited=$((waited + 2))
    if [ "${waited}" -ge "${DB_WAIT_SECONDS}" ]; then
        die "database not reachable after ${DB_WAIT_SECONDS}s — check DATABASE_URL and the postgres service"
    fi
    sleep 2
done
log "database reachable after ${waited}s"

# ── 3. Migrations ────────────────────────────────────────────────────────────
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    log "applying migrations"
    alembic upgrade head || die "alembic upgrade head failed — refusing to serve a stale schema"

    # Two heads means a deploy applied only one branch of a forked history.
    # Serving on a half-migrated schema is worse than not starting.
    heads="$(alembic heads 2>/dev/null | wc -l)"
    if [ "${heads}" -gt 1 ]; then
        die "alembic reports ${heads} heads — merge them before deploying"
    fi
else
    log "RUN_MIGRATIONS=false — skipping (schema must already be current)"
fi

# ── 4. Serve ─────────────────────────────────────────────────────────────────
if [ "${ENVIRONMENT:-development}" = "production" ]; then
    # uvicorn trusts X-Forwarded-* only from these peers. The backend's peer is
    # the nginx container on the compose network; '*' would let any direct
    # client spoof its own address and defeat rate limiting.
    FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-172.16.0.0/12}"
    log "starting uvicorn on ${BACKEND_HOST}:${BACKEND_PORT} with ${BACKEND_WORKERS} workers"
    log "trusted proxy peers: ${FORWARDED_ALLOW_IPS}"
    exec uvicorn app.main:app \
        --host "${BACKEND_HOST}" \
        --port "${BACKEND_PORT}" \
        --workers "${BACKEND_WORKERS}" \
        --proxy-headers \
        --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}" \
        --access-log
else
    # Dev gets reload, which requires a single process.
    log "starting uvicorn (dev) on ${BACKEND_HOST}:${BACKEND_PORT}"
    exec uvicorn app.main:app \
        --host "${BACKEND_HOST}" \
        --port "${BACKEND_PORT}" \
        --reload
fi
