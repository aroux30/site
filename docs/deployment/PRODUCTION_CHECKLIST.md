# Production Deployment Checklist — Iranian E-Commerce Platform

The definitive go-live gate. Follow top to bottom; **every step is executable and
verifiable** — nothing here relies on judgment calls.

---

## 1. Environment configuration (`.env` on the production host)

Required values — the application **refuses to boot** without them:

| Variable | Requirement |
| --- | --- |
| `ENVIRONMENT` | `production` (enables the fail-fast validator) |
| `DEBUG` | `false` |
| `JWT_SECRET_KEY` | ≥ 24 chars, generated: `openssl rand -hex 32` |
| `DATABASE_URL` | Real credentials, **not** `postgres:postgres@` / `postgres:password@` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Not `minioadmin` |
| `DIGITAL_CARDS_ENCRYPTION_KEY` | Real base64 32-byte key (card PINs) |
| `ADMIN_PHONE` / `ADMIN_PASSWORD` | Real Iranian mobile; password ≥ 12 chars, unique |
| `PAYMENT_PROVIDER` | A real gateway (`zarinpal` / `idpay` / `crypto` / `card_transfer`) — `mock` fails boot |
| `PAYMENT_SANDBOX` | `false` |
| `SMS_PROVIDER` | `kavenegar` / `ghasedak` with real `SMS_API_KEY` — `mock` fails boot |
| `CORS_ORIGINS` | Only the real HTTPS origins — localhost origins fail boot |

> The validator enforces all of the above at boot AND in preflight; see
> `backend/tests/unit/test_config_production.py` for the exact contract.

Secrets live only in the deployment environment (or a secret manager). Never in
git, never in images.

## 2. Preflight (blocking gate)

Run inside the production container before opening traffic:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
    python scripts/preflight_production.py
```

- Exit `0` = safe to serve traffic. Exit `1` = read the printed `[FAIL]` line(s).
- The preflight re-runs the boot validator, checks DB/Redis reachability (blocking),
  Elasticsearch/MinIO (warnings — degradable), migration head, and admin bootstrap.
- **Found a false positive?** Phase 3 did: the old DATABASE_URL rule rejected strong
  passwords containing the word "password". Preflight exists precisely to surface
  these before go-live — fix the validator, add a test, re-run.

## 3. Migrations and bootstrap

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python scripts/ensure_admin.py
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python scripts/reindex_search.py
```

## 4. Edge / proxy

- TLS via certbot (see README); HSTS enabled in `nginx/nginx.prod.conf`.
- `/metrics` and `/deep-health` are **denied at the edge** — Prometheus scrapes
  `backend:8000` inside the Docker network.
- nginx rate-limit zones (`auth_limit`, `login_limit`, general) active.

## 5. Post-deploy smoke (5 minutes)

1. Storefront loads, product listing renders, search returns results.
2. Register a test account → OTP arrives via the real SMS provider.
3. Add to cart → cart badge/drawer update → checkout quote shows totals.
4. Create order → gateway sandbox→real switch verified → payment callback verifies.
5. Admin login → orders list renders → status transition works → audit log entry visible.
6. `curl -f https://<domain>/healthz` and `/readyz` return 200; `/metrics` returns 404
   from outside the network.

## 6. Known production limitations (documented trade-offs)

| Area | Limitation | Recovery / monitoring |
| --- | --- | --- |
| Search sync | Near-real-time via transactional outbox → `sync_single_product` (autoretry); when ES is unreachable the full reindex **every 6 h** is the compensation pass — max staleness ≈ 6 h | `scripts/reindex_search.py`; warn-level preflight check; `full_reindex_task_completed/failed` logs |
| Payment reconciliation | Auto-cancel skips orders with live payment attempts; gateway-status polling not automated | `docs/runbooks/payment-reconciliation.md` — per-case detection + recovery |
| Celery money tasks | `process_pending_cashback`, `cancel_stale_pending_orders`, `reconcile_wallet_balances` are NOT auto-retried (duplicate money-movement risk); all log explicit failure events | Beat reschedules; inspect worker logs; manual retry safe per-task (each run filters by pending status) |
| Invoice accounting | VAT snapshot is authoritative; no Samaneh Moadian (سامانه مودیان) integration — the invoice prints the internal invoice ID, **not** a real Shaparak tracking code | External regulatory integration — product/accounting decision required |
| Access-token revocation | Deactivated users blocked instantly via Redis denylist; Redis outage degrades the check to fail-open | Redis is a blocking preflight dependency |
