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
