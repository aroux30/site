#!/usr/bin/env bash
# Pre-flight server checks before a production deployment (TASK P12 / P2-01).
# Runs ON the server (invoked from deploy.yml) inside the project directory.
# Exits non-zero on any blocking condition — the workflow stops BEFORE
# backup/build so a broken state never reaches the health-check phase.
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

# ── 1. DOMAIN must be present (the production nginx renders it at start
#      and exits with a fatal error if missing) ──────────────────────────
if ! grep -q '^DOMAIN=' .env 2>/dev/null; then
  if [ -n "${DOMAIN_NAME:-}" ]; then
    echo "DOMAIN=${DOMAIN_NAME}" >> .env
    echo ".env: appended DOMAIN=${DOMAIN_NAME} (derived from the health URL)"
  else
    echo "FATAL: .env has no DOMAIN= line and no DOMAIN_NAME hint was provided." >&2
    echo "Add DOMAIN=shop.example.com to ${PWD}/.env and re-run the deploy." >&2
    exit 1
  fi
else
  echo ".env: DOMAIN already set"
fi

# ── 2. Money-integrity audit: the new CHECK constraints (migration
#      a7f2c91d4e08) fail the upgrade if existing rows violate them.
#      Detect that here with a clear message instead of mid-deploy. ──────
PG_USER="$(grep '^POSTGRES_USER=' .env | cut -d= -f2 | tr -d '\"' || echo ecommerce)"
PG_DB="$(grep '^POSTGRES_DB=' .env | cut -d= -f2 | tr -d '\"' || echo ecommerce)"

RESULT="$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -t -A -c \
  "SELECT CASE WHEN
      EXISTS (SELECT 1 FROM wallets WHERE balance < 0)
      OR EXISTS (SELECT 1 FROM inventory_items WHERE available < 0 OR reserved < 0 OR committed < 0)
      OR EXISTS (SELECT 1 FROM order_items WHERE quantity <= 0)
      OR EXISTS (SELECT 1 FROM cart_items WHERE quantity <= 0)
    THEN 'violations' ELSE 'clean' END;")"

if [ "$RESULT" != "clean" ]; then
  echo "FATAL: existing rows violate the new money-integrity constraints." >&2
  echo "Run the pre-flight queries from docs/ecommerce-fix-roadmap.md (TASK P2-01)," >&2
  echo "remediate the data, then re-run the deployment." >&2
  exit 1
fi
echo "Money-integrity pre-flight: clean"
