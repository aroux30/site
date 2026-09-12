# Implementation Log — ARoux30 / SITE

> Task-by-task record of roadmap execution. Companion to
> `docs/ecommerce-fix-roadmap.md`. Every entry lists what was changed, how it
> was verified, and anything that could NOT be verified from this machine.

---

## 2026-09-11 — Session: audit follow-up implementation

### TASK P0-01 — CI Lint / Format Gates — **DONE**

**Files changed**
- `.github/workflows/ci.yml` — added `ruff check app tests`, `ruff format --check app tests` (backend job) and `npx eslint .` (frontend job) as failing steps.
- `backend/pyproject.toml` — documented global ignores (UP042 str-Enum semantics; TC001/2/3 — see "Key decisions" below) and scoped per-file-ignores (`**/api/routes.py`, `**/domain/*.py` for runtime-evaluated annotations; `invoice_service.py` E501 for the Persian HTML template; tests E402).
- `backend/app/**`, `backend/tests/**` — full ruff burn-down: ~1700 mechanical fixes (PEP 604 unions, unused imports, import sorting, `datetime.UTC`, import-block reformatting) + ~80 manual fixes (B904 raise-from, SIM102 merges, F841, DTZ011 → Tehran-calendar `datetime.now(TZ_TEHRAN)`, E712 → `.is_(True/False)`, S110/S311/A002 documented noqas, UP046 PEP 695 generics, N806/N818/B007/RUF012).

**Real bugs found and fixed by the lint gate**
- `F821 undefined name` — missing `Any` imports in `backend/app/modules/shipping/api/routes.py` and `shipping_service.py` (latent `NameError` under `get_type_hints`).
- `F601` — duplicate `"filter"` key in `PERSIAN_ANALYSIS_SETTINGS` (`elasticsearch_client.py`); the second dict silently overrode the first. Merged into one (superset) dict.
- `S311` (security) — **OTP codes were generated with Mersenne Twister** (`random.choices`) in `auth_service._generate_otp`; replaced with `secrets.choice`.

**Commands executed (local, exact CI equivalents)**
| Command | Result |
|---|---|
| `ruff check app tests` (backend) | ✅ All checks passed! (was 1673 errors) |
| `ruff format --check app tests` | ✅ 418 files already formatted |
| `npx eslint .` (frontend) | ✅ 0 errors (68 pre-existing `no-unused-vars` warnings; eslint exits 0) |
| `python -m pytest tests/unit -q` | ✅ 178/178 passed (176 prior + 2 new) |
| `python -c "from app.main import create_app; create_app()"` | ✅ boots, 271 routes (validates all FastAPI runtime annotation resolution) |

**RED test (GitHub Actions, real)**
- Draft PR #1 (`ci/red-gate-test`, closed+deleted): seeded `backend/app/ci_red_test_violation.py` (F401 + E501 + format violation) and a `requirements.txt` with `django==2.1`, `requests==2.19.0`.
- Result: `Backend Lint, Migrations & Tests` **FAILED** at the new "Lint (ruff check)" step (3 errors); `Trivy Vulnerability Scan` **FAILED** (`exit-code: 1`, `Total: 14 (HIGH: 10, CRITICAL: 4)`). Gitleaks passed (no secret seeded — see P0-02 notes). Evidence: run 34638473074 / job 103392075179; run 34638472967 / job 103392074190.

### TASK P0-02 — Security Scan Gates — **DONE (one item NOT VERIFIED, see below)**

**Files changed**
- `.github/workflows/security.yml` — Trivy step now sets `exit-code: "1"` (fails on HIGH/CRITICAL; `ignore-unfixed: true` and severity filter retained).
- `.zap/rules.tsv` — **created** (the reference in `zap.yml` was dangling). Minimal valid TSV: rule 10015 downgraded to WARN with the reason documented in the file header.
- `.gitleaks.toml` — **blanket `^tests/.*` path exclusion removed**. Replaced with two narrowly-scoped, documented allowlists: (1) a commit+path-pinned historical test fixture (`POSTGRES_PASSWORD=` value in an old revision of `test_payments.py` — never a real credential, removed from tree); (2) `scripts/ssh_deploy.py` pre-rotation history, pinned by path+rule with a mandatory removal note after credential rotation (TASK P1-07).
- `backend/alembic/versions/a7f2c91d4e08_add_money_integrity_constraints.py` (new) — P2-01, see below.
- CodeQL alert fixes: `scripts/ssh_deploy.py`, `scripts/fast_sync_and_test.py`, `backend/tests/conftest.py`, `backend/app/modules/catalog/schemas/__init__.py`, `backend/app/main.py`, `frontend/app/(store)/blog/[slug]/page.tsx`, `frontend/lib/api/blog.ts` (details under CodeQL below).

**Commands executed**
| Command | Result |
|---|---|
| `gitleaks git --no-banner .` (local, v8.30.1, new config) | ✅ no leaks found, exit 0 (was 6 findings) |
| `gitleaks` on a temp repo seeded with a secret | ✅ detection proven (exit non-zero) — the seeded file could not be created inside this repo because the Mimosa pre-commit hook correctly blocks secret-like literals |
| `trivy fs --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 backend` | ✅ exit 0 |
| `trivy fs ... frontend` | ✅ exit 0 **after** fixing 2 real findings (see below) |
| `trivy fs ... "$TEMP/trivy_red"` (seeded `django==2.1`) | ✅ exit 1 — gate blocks |

**Real dependency vulnerabilities fixed (frontend)**
- `postcss 8.4.31` (pinned transitively by next) — CVE-2026-45623 (HIGH), CVE-2026-73646 → npm `overrides` forces `^8.5.18`; installed 8.5.28. Verified: trivy exit 0, vitest 30/30, tsc clean, production build compiles.
- Added explicit `@testing-library/dom` devDependency (peer of `@testing-library/react`; was resolving by hoisting luck — broke after reinstall).

**CodeQL alerts (15 new on PR #2) — fixed**
- **HIGH `py/paramiko-missing-host-key-validation`** (`ssh_deploy.py`, `fast_sync_and_test.py`): removed the `DEPLOY_ALLOW_UNKNOWN_HOST` AutoAddPolicy escape hatch entirely; `DEPLOY_SSH_HOST_KEY` pinning is now mandatory.
- **HIGH `py/clear-text-logging-sensitive-data`** (`ssh_deploy.py`): the remote `.env` (with secrets) was written via a shell heredoc whose command text was echoed to deploy logs. Now written via SFTP with no secret ever in a command string; `ssh_exec(..., log_command=False)` guard added for secret-bearing commands.
- 13 × `py/unused-import` in `tests/conftest.py`: removed redundant side-effect model imports (models register transitively via `create_app`).
- `js/unused-local-variable` in `frontend/app/admin/settings/page.tsx`: NOT touched (pre-existing on default branch, not part of the 15 new alerts — left for the P9-03 admin pass).
- Semgrep blocking findings (3) resolved: `main.py` dynamic router import (documented inline `nosemgrep` — module paths are compile-time constants, indirection gives fail-fast boot), blog JSON-LD now escapes `<` so the payload cannot terminate the script tag (XSS hardening), `blog.ts` log message no longer interpolates a non-literal.

**NOT VERIFIED**
- OWASP ZAP scan execution (weekly schedule; requires the live production target — not reachable from this machine). The missing-rules-file defect is resolved and the file format follows the zaproxy/action-baseline TSV contract.

### TASK P1-08 — CI-gated deployment + prod overrides — **DONE**

**Files changed**
- `scripts/deploy.sh` — override selection rewritten as an explicit case statement: `production → docker-compose.yml -f docker-compose.prod.yml` (previously looked for the nonexistent `docker-compose.production.yml`, so prod hardening was silently never applied), `staging → docker-compose.yml`; missing prod file is now a hard error.
- `.github/workflows/deploy.yml` — new first step "Require green CI on the commit being deployed": queries `actions/workflows/ci.yml/runs?head_sha=<sha>&status=success` and blocks the deploy if none exists. Emergency escape: explicit `ignore_ci=true` dispatch input (logged as a warning; the GitHub Environment protection still applies).

**NOT VERIFIED**: an actual deploy rehearsal (requires the staging server + SSH secrets). The gate logic is unit-inspectable and the API call is exercised by GitHub.

### TASK P1-09 — Crypto underpayment guard — **DONE**

**Files changed**
- `backend/app/modules/payments/infrastructure/providers/crypto.py` — in the real-API verify path, a `finished/confirmed/sending` payment is now only settled when `actually_paid` (fallback `outcome_amount`) ≥ expected USD − 1% fee tolerance (`_convert_irr_to_usd(amount)`); shortfalls return `CRYPTO_UNDERPAID` and the payment stays unsettled for manual review.
- `backend/tests/unit/test_payment_hardening.py` — `test_crypto_verify_rejects_underpayment` (50% paid → not settled) and `test_crypto_verify_allows_full_payment_and_fee_tolerance` (100% → settles; 99.4% → settles; 98% → not settled).

**Tests**: backend unit suite 178/178.

### TASK P2-01 — Money-integrity constraint migration — **DONE (runtime NOT VERIFIED locally)**

**Files changed**
- `backend/alembic/versions/a7f2c91d4e08_add_money_integrity_constraints.py` (new, head `41444c67e586` → `a7f2c91d4e08`): UNIQUE `(coupon_id, order_id)` on `coupon_redemptions`; CHECKs `wallets.balance >= 0`, `inventory_items.available/reserved/committed >= 0`, `order_items.quantity > 0`, `cart_items.quantity > 0`. Downgrade drops in reverse. Pre-flight data-audit queries documented in the migration docstring.
- Models mirrored: `discounts/domain/models.py` (UniqueConstraint), `wallet/domain/models.py`, `inventory/domain/models.py`, `orders/domain/models.py`, `cart/domain/models.py` (CheckConstraints).

**NOT VERIFIED locally**: `alembic upgrade head` against a real PostgreSQL (no Docker/Postgres on this machine). CI's migration gate (`alembic upgrade head` + `alembic check` on the PR's Postgres service) covers the fresh-DB path; the populated-DB path requires the pre-flight audit + a staging rehearsal (ops).

### TASK P2-02 — Wallet ledger authority + reconciliation — **DONE**

**Files changed**
- `backend/app/modules/wallet/application/wallet_service.py` — `get_balance` now returns the **ledger SUM** (was returning the cached `balance` column despite its docstring) and re-syncs the cache on drift.
- `backend/app/modules/wallet/application/tasks.py` (new) — nightly `reconcile_wallet_balances` task: recomputes every wallet's ledger sum, fixes cached-balance drift, logs `wallet_reconcile_drift_fixed`.
- `backend/app/worker/celery_app.py` — beat entry `reconcile-wallet-balances` at 02:30 Tehran time.

### Concurrency note

A second session committed `6921841` ("ship UI/UX waves 1-2 + security hardening") mid-audit, which captured the audit's P0 fixes and docs under its message; this session's `23e7926` then captured that session's in-flight `nginx.conf` dynamic-upstream fix. Content is intact; history attribution overlaps. All work from this point on was staged file-by-file (no `git add -u`).

### Residual Mimosa scanner notes (advisory, non-blocking)

- `load_tests/scenarios/browsing.py`, `load_tests/common/helpers.py` — `random` for traffic shaping (non-security).
- `orders/application/order_service.py:90,576` — `random` for human-readable order numbers (documented `# noqa: S311`).
- `auth_service` OTP randomness was FIXED this session (`secrets` module).

---

## Verification status summary

| Task | Status | Local verification | CI verification |
|---|---|---|---|
| P0-01 | DONE | ruff/format/eslint/tests/build green; RED test proven | ✅ backend lint gate failed on seeded violation (run 34638473074); green on PR #2 |
| P0-02 | DONE (ZAP execution NOT VERIFIED) | gitleaks clean + seeded-secret detection proven; trivy clean + seeded-vuln exit 1 | ✅ trivy failed on seeded vuln (run 34638472967); gitleaks/trivy green on PR #2 |
| P1-08 | DONE | code inspection + workflow syntax | deploy rehearsal pending (ops) |
| P1-09 | DONE | 178/178 unit tests incl. 2 new | covered by CI pytest |
| P2-01 | DONE (populated-DB NOT VERIFIED) | migration file + models parse; suite green | fresh-DB migration gate runs in CI |
| P2-02 | DONE | 178/178 tests; app boots | covered by CI pytest |

---

## 2026-09-11 — Continuation batch (roadmap P4/P6/P7/P8/P9/P11)

### TASK P7-01 — Catalog → outbox → search sync — **DONE**
- `catalog_service.py`: new `_publish_product_event()` helper; `ProductCreated` on product create, `ProductUpdated` on product/variant update + variant create/delete, `ProductDeleted` on product delete — same transaction as the write; failures logged, never raised.
- The outbox worker already dispatched `sync_single_product` for these events — the pipeline is now end-to-end live.
- **NOT VERIFIED** with a live Elasticsearch (none in this environment).

### TASK P6-01 — Reverse-flow events — **DONE**
- `OrderCanceled` published in `cancel_order` (customer), `admin_update_status` (admin), and `cancel_stale_pending_orders` (system) with `initiated_by`/`reason`.
- `RefundProcessed` published in `refund_payment` (refund id/amount/status).
- `ReturnApproved`/`ReturnRefunded` **NOT WIRED — blocker**: the RMA lifecycle (approve/receive/inspect/refund) has no admin API surface at all (only creation is exposed). Logged as backlog gap BE-20.

### TASK P8-01 — Notifications wired to events — **DONE**
- Outbox worker: `OrderConfirmed` / `PaymentCompleted` / `OrderCanceled` / `RefundProcessed` create a Persian in-app `Notification` (order number resolved from DB) and enqueue `send_notification_task`.
- Dispatch enqueue is deliberately best-effort (a failed enqueue must not duplicate the in-app row on outbox retry); channel failures stay observable in the notifications queue/logs.

### TASK P11-01 — Trusted-proxy IP + rate limits — **DONE**
- `get_real_client_ip` honors `TRUSTED_PROXY_COUNT` (default 1): rightmost trusted XFF hop instead of spoofable leftmost.
- Limits added: cart writes 60/min, cart merge 10/min, checkout create-order 10/min, payment create 10/min + verify 30/min, order cancel/return 10/min, wallet deposit/withdraw/topup 10/min.
- A 429 integration test remains open (roadmap test plan).

### TASK P6-02 — Wallet top-up via gateway — **DONE**
- Migration `b3e7a9c2d154`: `payments.order_id` nullable.
- `POST /wallet/topup` (10/min) creates a `wallet_topup` payment via an online gateway; `verify_payment` credits the owner's wallet inside the locked completion transaction; ownership via `extra_data.wallet_user_id`.
- Deposit modal redirects to the gateway; options are zarinpal/idpay (fake "saman" removed).
- Regression tests: topup credits owner once; non-owner verify → 404; below-minimum rejected.

### Frontend honesty batch — **DONE**
- **P9-01** PDP: fabricated product/reviews/stats deleted; unified guard → skeleton / error+retry / not-found; no unsplash placeholder injection.
- **P9-04** home: featured products fetched server-side (ISR 5 min); section hidden when API unreachable — zero hardcoded products.
- **P9-05** blog: fabricated posts/categories deleted; unknown slug → `notFound()`; unused `fetchRecentBlogPosts` removed.
- **P9-02** account: `INITIAL_*` mock seeds and fake `5,800,000` balance default removed.
- **P9-08**: dead `$RV/$RB` flush hack and `evaluateCoupon` mock engine removed.

### TASK P4-01 — Guest checkout decision — **DONE**
- `docs/adr/0001-guest-checkout-decision.md`: **Option A** — login required (phone-OTP friction is low; every order gets an authenticated owner); guest carts remain pre-login carts with existing merge behavior; Option B documented as revisit path.

### Final verification
| Command | Result |
|---|---|
| `ruff check app tests` / `ruff format --check` | ✅ clean |
| `pytest tests/unit -q` | ✅ **181/181** |
| `create_app()` boot | ✅ 272 routes (incl. `/wallet/topup`) |
| `tsc` / `eslint .` / `vitest` / `next build` | ✅ clean / 0 errors / 30-30 / 39 pages |
| GitHub Actions on `main` | ✅ CI Pipeline + Security Scan & Audit + CodeQL success |


---

## 2026-09-12 — BE-20: durable RMA lifecycle + P7-02 + P2-04 + P11-02

### TASK BE-20 — RMA persistence + admin processing — **DONE**

Discovery: the RMA lifecycle was **stateless theater** — `OrderReturnDomain`
is a pure dataclass; the customer's return request was validated, rendered to
JSON, and then lost. No table, no admin surface. This task built the missing
stack:

- **Models** `backend/app/modules/orders/domain/return_models.py`: `order_returns`
  (unique `rma_number`, FK order/user RESTRICT, status, notes, refund_amount,
  lifecycle timestamps) + `order_return_items` (FKs CASCADE/RESTRICT, quantity
  CHECK > 0, inspection outcome).
- **Migration** `c4d9e1a5f7b2_add_rma_tables` (head now `c4d9e1a5f7b2`); models
  registered in `alembic/env.py` target metadata (initial commit missed this —
  `alembic check` in CI correctly failed wanting to drop the tables; fixed).
- **Persistence**: `request_order_return` now writes the RMA + items in the
  same transaction and returns the real id + `rma_number` (new response field).
- **Admin endpoints** (orders router, `orders:read` / `orders:write` RBAC):
  `GET /orders/admin/returns`, `POST /orders/admin/returns/{id}/transition`
  with body `{target, notes, inspection_outcomes, refund_amount}`. Transition
  rules come exclusively from the domain state machine; an illegal move is a
  clean 422 (`INVALID_RETURN_TRANSITION`), enforced by a pre-check plus the
  domain `transition_to`.
- **P3-01 merged**: `REFUNDED` restocks PASSED inspection items via new
  `inventory_service.restock_returned_items` (committed → available, per-item
  transaction records, damaged items excluded).
- **Events**: `ReturnApproved` / `ReturnRefunded` published; `ReturnApproved`
  creates a customer notification.
- **Tests**: `tests/unit/test_returns_admin.py` — approve persists + publishes;
  illegal transition rejected and state unchanged; unknown target 422; refund
  restocks only passed items; restock moves committed→available.
- **CI verified on real Postgres**: `alembic upgrade head` + `alembic check`
  green (catch confirmed fixed); full pipeline green on `main`.

### TASK P7-02 — Rating data in search index — **DONE**
- `SearchService._get_rating_aggregate(session, product_id)` (avg + count over
  APPROVED reviews); `_product_to_doc` now accepts and indexes
  `rating_average`/`rating_count`; both callers (reindex_all, per-product sync)
  pass live aggregates. Rating sort/filter facets finally have data.

### TASK P2-04 — Router double-mount — **RESOLVED AS DOCUMENTED**
- The seo/vendors second mounts are intentional root-level legacy aliases
  (hidden from OpenAPI), not accidental duplicates. Commented in `main.py`;
  new `test_no_duplicate_schema_routes` asserts no true duplicates.

### TASK P11-02 — Alerting — **DONE (config)**
- `monitoring/prometheus/rules/ecommerce.yml`: alerts for backend scrape-down
  (critical, 2m), 5xx rate >5% for 10m, P95 latency >2.5s, payment-verify 5xx
  (critical), DB pool >90%. Metric names verified against
  `observability/metrics.py`.
- `prometheus.yml`: rules file enabled; dead `celery-worker` scrape target
  disabled with re-enable note (TASK PERF-01); rules directory mounted into
  the prometheus container (dev + prod inherits via base compose).
- **NOT VERIFIED live**: no Prometheus/Alertmanager running locally — rules
  validated as YAML + by metric-name cross-check; firing behaviour needs the
  staging stack (P12-01).

---

## 2026-09-12 — Batch 3 (P11-04, P3-03, P9-03, P12-01/02/05)

### TASK P11-04 — Refresh-token reuse detection — **DONE**
- `auth_service.refresh_token` now queries the session WITHOUT the
  `is_revoked` filter; a revoked token being replayed revokes **every active
  session of the user** (containment without schema change) and raises
  `auth.refresh_token_reuse_detected` via `log_security_event` (Fail2Ban/
  CrowdSec-parseable). Unknown tokens remain plain-invalid (no alarm noise).
- Tests: `tests/unit/test_auth_reuse.py` (reuse → all sessions revoked +
  security event; unknown token → plain 401, no alarm). Opaque fixture
  tokens generated per-run (`uuid4`) — the Mimosa hook correctly rejects
  literal token strings in test files.

### TASK P3-03 — Inventory authorization verification — **DONE (verified)**
- All 5 `/inventory` routes reviewed: every GET carries `inventory:read`,
  the only mutation (`POST /{variant_id}/adjust`) carries `inventory:write`.
  No gaps found; no changes required. (An explicit 403 test can be added to
  the security suite later — noted, not blocking.)

### TASK P9-03 — Admin pages honesty — **DONE (core pages)**
- `admin/users`: `mockUsers` seed deleted; honest error row on API failure
  (endpoint `/users/admin/users` was already correct).
- `admin/products`: wrong-endpoint fallbacks (`/products`) removed from
  fetch/create/update/delete; server-assigned product id used on create;
  swallowed write failures now surface destructive toasts.
- `admin/kanban`: 345-line fabricated order board deleted; endpoint chain
  collapsed to the real `/orders/admin/orders`.
- `admin/dashboard`: fabricated KPI values zeroed (real values flow from
  `/analytics/sales` when available); fabricated recent orders emptied;
  malformed endpoint probes (`/admin/orders` at the wrong prefix,
  `/analytics/overview` non-existent) removed.
- `admin/approvals`: "Fallback simulation" fake-success removed — a failed
  approval action now surfaces as an error (backend
  `POST /approvals/{id}/action` exists and is the source of truth).
- Still OPEN in P9-03 scope: `admin/reports`, `admin/pages`, `admin/settings`
  remain static/hardcoded (no matching backend for several of their fields);
  explicitly out of this batch, tracked in roadmap FE-07.

### TASK P12-01 — Nginx production correctness — **DONE (config)**
- `nginx.prod.conf`: static `upstream` blocks (startup-pinned container IPs
  → 502 after recreation) replaced with Docker-DNS dynamic resolution
  (`resolver 127.0.0.11 valid=10s` + `$backend_up`/`$frontend_up` variables),
  mirroring the dev conf pattern; `${DOMAIN}` placeholders now render via
  envsubst at container start; dead `/health` location replaced by real
  `/healthz` + `/readyz` proxied to the backend.
- `docker-compose.prod.yml`: nginx config mounted as a template at
  `/etc/nginx/templates/nginx.conf.template` with `DOMAIN` env (fail-fast if
  unset) and a `command` that renders + starts nginx with `-c`. **Rendering
  verified locally** with envsubst (DOMAIN substitution confirmed; quoting
  bug — `envsubst "$DOMAIN"` — caught and fixed during that test).
- **NOT VERIFIED live**: a full TLS container boot needs the staging host.

### TASK P12-02 — Exposure hardening — **DONE (dev compose)**
- postgres/redis/elasticsearch/minio(+console)/prometheus/grafana port
  bindings changed from `0.0.0.0` to `127.0.0.1` in `docker-compose.yml` —
  no data service reachable off-host in development.

### TASK P12-05 — Image hygiene — **DONE**
- `frontend/Dockerfile`: `node:22-alpine` (matches CI), lockfile-only
  `npm ci --legacy-peer-deps` (no `|| npm install` fallback, no yarn/pnpm
  probing for a repo that only has npm).
- `backend/Dockerfile`: runtime venv built with `pip install "."` — dev/test
  tooling no longer ships in the production image.

### Verification
| Check | Result |
|---|---|
| `ruff check/format app tests` | ✅ clean (CI caught one missed format on auth_service — fixed) |
| `pytest tests/unit -q` | ✅ **189/189** (+2 reuse tests) |
| `tsc` / `eslint` (changed files) / `vitest` / `build` | ✅ / 0 errors / **31/31** (stale gamification fallback test rewritten to expect honest rejection) / 39 pages |
| `alembic upgrade head` + `alembic check` (CI Postgres) | ✅ green |
| GitHub Actions `main` | ✅ CI Pipeline · Security Scan & Audit · CodeQL all success |
