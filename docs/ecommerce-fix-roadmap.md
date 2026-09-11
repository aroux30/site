# E-Commerce Fix Roadmap — ARoux30 / SITE

> Derived from the 2026-09-11 end-to-end integration audit. Source documents:
> `docs/ecommerce-final-integration-audit.md`, `docs/cross-system-bug-matrix.md`,
> `docs/integration-matrix.md`, `docs/integration-system-map.md`.
>
> **This document is a plan. No source code was modified to produce it.**
> Items marked **DONE (audit)** were already implemented and regression-tested during the
> audit itself; they are listed so the backlog is complete and classifications are on record.
> Everything else is OPEN work, ordered by the phase plan in section 4.

**Classification legend**

- Priority: P0 = must fix before production · P1 = before serious production usage · P2 = important improvement · P3 = polish/debt
- Class: BUG · ARCHITECTURE GAP · INTEGRATION GAP · SECURITY ISSUE · DATA CONSISTENCY ISSUE · PERFORMANCE ISSUE · UX ISSUE · TESTING GAP · OBSERVABILITY GAP · TECHNICAL DEBT · MOCK/DEMO · NOT CONFIGURED · INFRASTRUCTURE BLOCKER

---

## 1. Master Fix Backlog

| ID | Priority | Classification | Domain | Problem | Root Cause | Affected Files | Dependencies | Proposed Fix | Test Required | Risk | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BE-01 | P0 | BUG + SECURITY + DATA CONSISTENCY | Payments/Wallet | Wallet orders confirmed without debiting wallet | `WalletPaymentProvider.verify_payment` returned success and never debited | `payments/infrastructure/providers/wallet.py`, `payments/application/payment_service.py` | none | Debit inside locked verify transaction; fail payment on failed debit | Unit + concurrency | Low (shipped) | **DONE (audit)** |
| BE-02 | P0 | SECURITY ISSUE | Wallet | `POST /wallet/deposit` minted balance with no payment | Endpoint credited directly by design shortcut | `wallet/api/routes.py` | none | Fail-closed 403 in production; real top-up flow = P6-02 | Unit (route) | Low (shipped) | **DONE (audit)** |
| BE-03 | P0 | SECURITY + DATA CONSISTENCY | Payments | Amount/ownership/order-state never validated at payment creation | Service trusted client payload | `payments/application/payment_service.py` | none | Enforce owner + `PENDING` + `amount == order.total` | Unit ×3 | Low (shipped) | **DONE (audit)** |
| BE-04 | P0 | SECURITY ISSUE | Payments | Verify endpoint IDOR + verify/webhook race | Unlocked fetch, no ownership check | `payments/api/routes.py`, `payment_service.py` | BE-03 | Owner check + `FOR UPDATE` fetch | Unit | Low (shipped) | **DONE (audit)** |
| BE-05 | P0 | SECURITY + NOT CONFIGURED | Payments/Crypto | IPN signature skipped when secret unset; simulated success in prod | `verify_ipn_signature` returned True on empty secret; simulation branch unconditional | `providers/crypto.py`, `payments/api/routes.py` | none | Fail-closed signature enforcement; block simulation in prod; require `NOWPAYMENTS_API_KEY`/`NOWPAYMENTS_IPN_SECRET` in prod (see P12-02) | Unit (existing IPN suite) | Low (shipped) | **DONE (audit)** |
| BE-06 | P1 | DATA CONSISTENCY | Payments/IDPay | Settled amount never cross-checked | Verify payload ignored amount | `providers/idpay.py` | none | Send + verify amount, fail on mismatch | Unit | Low (shipped) | **DONE (audit)** |
| BE-07 | P0 | DATA CONSISTENCY | Inventory/Orders | Cancelled/unpaid orders permanently locked stock; no unpaid-order expiry | `cancel_order` didn't restock; checkout commits inventory pre-payment with no TTL enforcement | `inventory/application/inventory_service.py`, `orders/application/order_service.py`, `orders/application/tasks.py` (new), `worker/celery_app.py` | none | `restock_order()` on all cancel paths + beat task `cancel_stale_pending_orders` (5 min, TTL 60 min) | Unit ×2 | Low (shipped) | **DONE (audit)** |
| BE-08 | P1 | INTEGRATION GAP | Inventory | Expired reservations never released | Task existed, not in beat schedule | `worker/celery_app.py` | none | Beat entry `*/5` | Schedule check | Low (shipped) | **DONE (audit)** |
| BE-09 | P1 | INTEGRATION GAP | Events | Outbox had zero publishers and unscheduled drain | Built but never commissioned | `worker/celery_app.py`, `payment_service.py`, `shared/events/*` | none | Publish Payment/Order events; schedule drain `*/1` | Unit asserts publish | Low (shipped) | **DONE (audit)** |
| BE-10 | P2 | DATA CONSISTENCY | Refunds/Wallet | Wallet refund could credit admin's wallet on order-lookup failure | `user_id=customer or actor` fallback | `payment_service.py` | none | Refund credit strictly to customer | Existing refund suite | Low (shipped) | **DONE (audit)** |
| BE-11 | P2 | INTEGRATION GAP + DATA CONSISTENCY | Search | Index stale up to 24h; no realtime sync on catalog writes; `rating_average` never populated | Catalog writes publish nothing; nightly reindex only | `catalog/application/catalog_service.py`, `search/application/search_service.py` | BE-09 (outbox live) | **P7-01/P7-02**: publish Product events; populate rating in doc builder | Unit + integration | Low–Med | OPEN |
| BE-12 | P2 | INTEGRATION GAP | Notifications | No transactional notifications ever sent (order/payment/refund/cancel) | Providers + Celery queue real; no caller | `automation/application/outbox_worker.py`, `notifications/application/*`, `payment_service.py`, `orders/application/tasks.py` | BE-09 | **P8-01**: outbox handlers → `notification_service.create_notification` + `send_notification_task` | Unit + integration | Low | OPEN |
| BE-13 | P2 | SECURITY ISSUE | Security | Rate limiting on 3 routes only; client IP from spoofable `X-Forwarded-For` | Decorators never rolled out; `get_real_client_ip` trusts XFF blindly | `core/security/rate_limiter.py` (27-45), route files | none | **P11-01**: `TRUSTED_PROXY_COUNT` setting, rightmost-XFF hop logic, decorate cart/checkout/payment/order routes | Unit (IP extraction) + integration (429s) | Medium (lockout risk if wrong) | OPEN |
| BE-14 | P2 | SECURITY ISSUE | Auth | No refresh-token reuse detection | Rotation revokes old token silently | `auth/application/auth_service.py` | none | **P11-04**: token-family ID; reuse ⇒ revoke family + security event | Unit + security test | Low | OPEN |
| BE-15 | P3 | SECURITY ISSUE | Orders | Invoice JWT accepted via query string | Convenience header-or-query implementation | `orders/api/routes.py` (39-54), `invoice_service.py` | none | **P5-03**: short-lived single-purpose invoice token | Unit | Low | OPEN |
| FE-01 | P1 | INTEGRATION GAP + UX | Payments UI | Gateway redirect landed on 404; success never shown | `/payment/callback` route never created | `frontend/app/(store)/payment/**` | none | Callback pages calling server verify | Build + manual journey | Low (shipped) | **DONE (audit)** |
| FE-02 | P1 | INTEGRATION GAP | Checkout | `/payments` never called for wallet/crypto; payment failures faked as confirmation | Provider list incomplete; catch swallowed errors | `frontend/app/(store)/checkout/page.tsx` | BE-01 | All online providers initiate payment; wallet verifies in-page; failures surface | tsc + build | Low (shipped) | **DONE (audit)** |
| FE-03 | P1 | MOCK/DEMO + UX | Storefront | Products listing showed 8 fake products (incl. during loading) on API failure | Hardcoded fallback arrays | `frontend/app/(store)/products/page.tsx` | none | Fallbacks deleted; skeleton/error/empty states | tsc + build | Low (shipped) | **DONE (audit)** |
| FE-04 | P2 | UX ISSUE + MOCK/DEMO | Account | Fake-success toasts (deposit fixed; profile/addresses/review-submit still fake); dashboard mock seeds | `.catch(() => null)` pattern | `components/account/account-dashboard.tsx`, `products/[slug]/page.tsx` (review) | none | **P9-02**: honest error surfaces, remove mock seeds | tsc + component tests | Low | OPEN (deposit DONE) |
| FE-05 | P2 | MOCK/DEMO + UX | Checkout/Shipping | Hardcoded shipping fallback (fake UUIDs), `weight: 1.5`, static delivery-slot dates | Display-layer fabrication | `frontend/app/(store)/checkout/page.tsx` (275-345), `lib/iranian-commerce.ts` (138-181) | none | **P4-04**: real quote or explicit failure; real cart weight; slot data from API or remove | tsc | Low | OPEN |
| FE-06 | P3 | MOCK/DEMO | Blog | Fallback posts returned silently on API error | Hardcoded fallback in api layer | `frontend/lib/api/blog.ts` | none | **P9-05**: remove fallbacks, error state | tsc | Low | OPEN |
| FE-07 | P2 | MOCK/DEMO + INTEGRATION GAP | Admin | users/categories/reports/pages/settings mock-first; product writes target wrong path; kanban probes malformed URL; approvals fakes success | Pages written against guessed endpoints | `frontend/app/admin/**` | none | **P9-03**: re-point to real endpoints, remove mocks, surface failures | tsc + manual admin QA | Medium (admin workflows) | OPEN |
| FE-08 | P2 | SECURITY + ARCHITECTURE GAP | Gamification | Points/spins/prizes decided client-side (`Math.random`, localStorage) — farmable economy | No server authority for gamification | `frontend/components/gamification/**`, backend `gamification` module | none | **P9-06**: server-side spin/claim with ledger + rate limit | Unit + security test | Medium | OPEN |
| FE-09 | P3 | MOCK/DEMO | Home | Homepage shows 6 hardcoded demo products | Never wired to API | `frontend/app/(store)/page.tsx` | none | **P9-04**: `useProducts({is_featured:true})` + real fallback-to-empty | tsc | Low | OPEN |
| INF-01 | P0 | TESTING GAP + INFRASTRUCTURE BLOCKER | CI | Every test file + CI test steps had been deleted to keep CI green | Working-tree deletions + ci.yml edits | `backend/tests/**`, `frontend/**__tests__**`, `ci.yml` | none | Restore all from git; suites green | Full suites | None (shipped) | **DONE (audit)** |
| INF-02 | P1 | INFRASTRUCTURE BLOCKER | Deploy | deploys not gated on CI; `deploy.sh` never applies prod overrides (wrong filename) | `workflow_dispatch` only; `docker-compose.${ENVIRONMENT}.yml` vs existing `docker-compose.prod.yml` | `.github/workflows/deploy.yml`, `scripts/deploy.sh` (58) | INF-01 | **P1-08**: filename mapping + `workflow_run` gate | Staging rehearsal | Medium | OPEN |
| INF-03 | P2 | INFRASTRUCTURE BLOCKER | Nginx | Prod conf: `${DOMAIN}` never substituted; proxies nonexistent `/health`; no `/healthz`//readyz` locations | No envsubst entrypoint; stale route names | `nginx/nginx.prod.conf`, `docker-compose.prod.yml` | none | **P12-01** | Container boot test | Medium | OPEN |
| INF-04 | P2 | SECURITY + NOT CONFIGURED | Docker/Secrets | Dev compose binds data services to 0.0.0.0 with weak defaults; local `.env` still weak (MinIO/Grafana/ES) | Compose fallbacks never rotated | `docker-compose.yml`, `.env` (local, untracked) | none | **P12-02** | Compose config review | Low | OPEN |
| INF-05 | P1 | SECURITY + INFRASTRUCTURE BLOCKER | Secrets | Real-looking credentials embedded in `scripts/ssh_deploy.py`; password root SSH with `AutoAddPolicy`; hardcoded public IP in scripts/nginx/robots/sitemap; gitleaks blanket-exempts `tests/` | Provisioning script doubles as credential store | `scripts/ssh_deploy.py`, `scripts/fast_sync_and_test.py`, `nginx/nginx.conf` (95), `frontend/app/robots.ts`+`sitemap.ts`, `.gitleaks.toml` | none (rotation is external) | **P1-07**: rotate everything, env-only secrets, key SSH + pinned host keys, purge IPs, scope gitleaks allowlist | gitleaks full-history + deploy dry run | Medium | OPEN |
| INF-06 | P2 | OBSERVABILITY GAP | Security tooling | Trivy never fails build (no `exit-code: 1`); ZAP advisory-only with missing rules file | Scan config incomplete | `.github/workflows/security.yml` (45-51), `zap.yml`, `.zap/rules.tsv` (missing) | none | **P0-02** | CI run on seeded vuln | Low | **DONE** (2026-09-11: trivy exit-code 1, .zap/rules.tsv created, gitleaks allowlists narrowed; seeded-vuln CI run failed as required — PR #1) |
| INF-07 | P2 | OBSERVABILITY GAP | Monitoring | No alert rules/Alertmanager/dashboards; worker scrape target dead (`:8001` has no server) | Monitoring scaffolding incomplete | `monitoring/prometheus/prometheus.yml`, `docker-compose*.yml`, `backend/app/worker/*` | none | **P11-02** | Alert fired in staging drill | Low–Med | OPEN |
| INF-08 | P2 | NOT CONFIGURED | Backup | No MinIO backup, no scheduler, backups same-host by default, no restore drill evidence | Backup scripts Postgres-only | `scripts/backup.sh`, `scripts/restore.sh`, `docker-compose*.yml`, `docs/deployment/README.md` | INF-02 (scheduler host) | **P12-03** | Restore drill | Medium | OPEN |
| DB-01 | P2 | DATA CONSISTENCY | Database | No DB-level guard against duplicate coupon redemption, negative wallet/inventory, zero-qty items | Constraints never added (one unrelated CHECK exists) | new Alembic revision on head `41444c67e586`, `wallet/domain/models.py`, `inventory/domain/models.py`, `orders/domain/models.py` | BE-07 (task semantics) | **P2-01**: unique `(coupon_id, order_id)`; CHECKs `balance>=0`, `available>=0`, `reserved>=0`, `committed>=0`, `quantity>0` | Migration up/down + concurrency | Medium | OPEN |
| DB-02 | P3 | DATA CONSISTENCY | Database | Minor schema hardening (order-item unique (order_id, variant_id)) | — | same revision as DB-01 | DB-01 | Fold into **P2-01** migration | Migration test | Low | OPEN |
| BE-16 | P1 | SECURITY + DATA CONSISTENCY | Payments/Crypto | Real-API crypto verify accepts `finished` payments without checking `actually_paid >= price_amount` (underpaid completion) | Verify only polls status string | `providers/crypto.py` (real verify branch ~446-484) | none | **P1-09**: compare `actually_paid` vs expected USD (tolerance for fees), else keep PENDING/flag for review | Unit (underpaid case) | Low | OPEN |
| FE-10 | P3 | TECHNICAL DEBT | Frontend | Divergent canonical types (`types/index.ts` vs `ApiProduct`), snake/camel defensive chains in order UI | Types written before API shape settled | `frontend/types/**`, `lib/api/types.ts`, `components/account/account-dashboard.tsx` | P9-03 | **P9-07**: single source of types generated from backend schemas | tsc | Low | OPEN |
| FE-11 | P3 | TECHNICAL DEBT + DATA CONSISTENCY | Frontend | Toman/Rial conversion scattered (÷10, ×10 across files) | No single money-format util | `stores/cart-store.ts`, `checkout/page.tsx`, `lib/utils.ts` | none | **P3-02** | Unit tests on formatter | Low | OPEN |
| FE-12 | P3 | BUG + UX | Cart | Favorites page add-to-cart doesn't update zustand badge; dead `useCartQuery` path | Two add-to-cart implementations | `lib/api/queries.ts` (230-245), `hooks/use-cart.ts` | none | **P4-03** | Component test | Low | OPEN |
| FE-13 | P3 | TECHNICAL DEBT | Providers | Dead `$RV/$RB` flush hack; unused `evaluateCoupon` mock engine | Leftover experiments | `frontend/app/providers.tsx` (9-25), `lib/iranian-commerce.ts` (210-251) | none | **P9-08** | tsc + build | Low | OPEN |
| BE-17 | P3 | TECHNICAL DEBT | Auth | Casbin enforcer implemented but unused (diagnostic endpoint only) | RBAC via JWT claims instead | `core/security/casbin_enforcer.py`, `core/security/rbac_*` | none | **P11-06**: adopt per-route or remove | Router integrity test | Low | OPEN |
| BE-18 | P3 | BUG | Search | Duplicate `"filter"` key in `PERSIAN_ANALYSIS_SETTINGS` (second silently wins) | Dict literal duplication | `search/infrastructure/elasticsearch_client.py` (57/93) | none | **P7-03** | Unit on analysis settings | Low | OPEN |
| BE-19 | P3 | TECHNICAL DEBT | API | seo & vendors routers mounted twice (once schema-hidden) | Mount list quirk | `backend/app/main.py` (175-184) | none | **P2-04** | `test_router_integrity` extension | Low | OPEN |
| ARCH-01 | P2 | ARCHITECTURE GAP + INTEGRATION GAP | Checkout | Guest checkout impossible (guest carts exist, checkout requires login) | Checkout deps require user id | `checkout/api/routes.py`, `checkout_service.py`, frontend checkout | DB-01 (schema decision) | **P4-01**: decision + implement guest path (nullable order user + required contact snapshot) or remove guest affordances | Integration (guest journey) | High if implemented | OPEN (decision) |
| ARCH-02 | P3 | TECHNICAL DEBT | AI | No AI commerce module exists (external claims aspirational) | Never implemented | — | — | **P10-01**: explicit decision record; do not build speculatively | — | — | OPEN (decision) |
| ARCH-03 | P2 | DATA CONSISTENCY | Wallet | Cached `wallet.balance` can drift from ledger sum; `get_balance` docstring claims ledger is truth but returns cache | Reconciliation missing | `wallet/application/wallet_service.py` (68-101) | DB-01 | **P2-02**: return ledger sum + daily reconcile task with drift alert | Unit + reconciliation test | Low–Med | OPEN |
| TEST-01 | P2 | TESTING GAP | E2E | No end-to-end checkout→payment→order test at any layer | Suite grew feature-by-feature | `backend/tests/integration/` | DB-01 | **P5-01/P5-02** | E2E (backend integration) | Low | OPEN |
| TEST-02 | P2 | TESTING GAP | CI | No lint/format gate; no coverage floor | ci.yml minimal | `.github/workflows/ci.yml`, `pyproject.toml`, `frontend/eslint*` | INF-01 | **P0-01** | CI green/red check | Low | **DONE** (2026-09-11: ruff+format+eslint gates in ci.yml; seeded-violation CI run failed as required — PR #1) |
| TEST-03 | P3 | TESTING GAP | Performance | Load tests restored but stale vs current flows | Reports deleted previously | `load_tests/**` | Staging env (P12-01) | **P11-03** | Load | Low | OPEN |
| UX-01 | P2 | UX ISSUE | Reviews | Review submit shows success even on API failure (comment admits it) | catch sets success | `frontend/app/(store)/products/[slug]/page.tsx` (515-524) | none | Fold into **P9-02** | tsc | Low | OPEN |
| PERF-01 | P3 | PERFORMANCE ISSUE | Observability | Worker metrics scrape points at closed port; celery prometheus metrics not exposed | No metrics HTTP server in worker | `backend/app/worker/celery_app.py`, `monitoring/prometheus/prometheus.yml` (46-52) | INF-07 | Fold into **P11-02** | Scrape check | Low | OPEN |

---

## 2. Dependency Graph

```
INF-01 (tests restored) ──► TEST-02 (lint gates) ──► everything merges through green CI
                                     │
BE-01..BE-10, FE-01..FE-03, BE-06/08/09 (DONE) ──► regression baseline (green suites)

INF-05 (credential rotation) ──────────────────────► P12-04 (deploy verification)
INF-02 (deploy gating + prod overrides) ──► P12-01 (nginx fixes) ──► P12-03 (backup drill) ──► P12-04

DB-01/DB-02 (constraint migration) ──► TEST-01 (e2e needs populated DB semantics)
        │                                   └──► P11-03 (load tests meaningful)
        └──► ARCH-03/P2-02 (wallet reconcile task assumes CHECK balance>=0)

BE-09 (outbox live) ──► BE-11/P7-01 (catalog publishes) ──► search freshness
        └──────────────► BE-12/P8-01 (notifications consume) ──► P6-02 (top-up flow reuses verify path)

P4-01 (guest checkout decision) ──► checkout e2e scope in P5-01

P9-* frontend honesty tasks: independent of each other (parallel safe), after BE-12 (so UI can show real notification-driven states)
P11-* observability: after P12-01 (staging reachable) for alert drill; rate limiting independent
```

**Rule applied:** backend/domain causes are fixed before frontend symptoms; schema changes precede tests that depend on them; anything touching payments is serialized (no parallel payment tasks).

---

## 3. Phase Plan (Phases 0–12)

> Each task below carries: **WHY / WHAT / WHERE / HOW / TEST / DONE WHEN**, plus `PARALLEL SAFE` or `SEQUENTIAL REQUIRED`.

---

### PHASE 0 — Safety / Baseline
**Goal:** guarantee that no future change can merge without the full suite, and that secret scanning is trustworthy.
**Issues:** INF-01 (DONE), TEST-02, INF-06.
**Files:** `.github/workflows/ci.yml`, `security.yml`, `zap.yml`, `pyproject.toml`, `frontend/eslint.config.*`, `.gitleaks.toml`.
**Dependencies:** none (INF-01 done).
**Rollback:** revert workflow file; no runtime impact.

- **TASK P0-01 — Lint/format gates in CI** `PARALLEL SAFE` — **DONE (2026-09-11)**
  - WHY: the gutted-CI incident shows suites alone don't catch drift; style-consistent diffs review faster.
  - WHAT: add ruff (+format check) to `backend-checks`, eslint to `frontend-checks`; fix current violations once, in a dedicated commit.
  - WHERE: `ci.yml` jobs after install steps.
  - HOW: `ruff check app tests` and `npx next lint`/`npx eslint .`; treat warnings as errors for new rules via config, not inline disables.
  - TEST: CI run on a deliberately broken branch fails; main passes.
  - DONE WHEN: both gates required on PRs and passing on main.

- **TASK P0-02 — Security scans actually gate** `PARALLEL SAFE` — **DONE (2026-09-11)** (INF-06 closed; ZAP *execution* itself remains schedule-gated — see implementation-log NOT VERIFIED note)
  - WHY: Trivy currently reports CRITICAL/HIGH and exits 0; ZAP references a missing rules file.
  - WHAT: add `exit-code: 1` (+ `severity: CRITICAL,HIGH`) to Trivy; commit a minimal `.zap/rules.tsv` (or drop `rules_file_name`); keep gitleaks as-is until P1-07 tightens the allowlist.
  - WHERE: `security.yml` Trivy step, `zap.yml`, new `.zap/rules.tsv`.
  - HOW: one-line flag changes; rules file starts as pass-through with the two documented FPs.
  - TEST: seed a known-vulnerable dep in a scratch branch → build fails.
  - DONE WHEN: a CRITICAL finding blocks merge.

---

### PHASE 1 — P0 Security & Money
**Goal:** close every money-movement hole and make deployment impossible without green CI.
**Issues:** BE-01..BE-10 (DONE), INF-05, INF-02, BE-16.
**Files:** `scripts/ssh_deploy.py`, `scripts/fast_sync_and_test.py`, `.github/workflows/deploy.yml`, `scripts/deploy.sh`, `providers/crypto.py`, `.gitleaks.toml`, nginx/robots/sitemap (IP purge).
**Dependencies:** none new; INF-05 rotation requires server access (ops coordination).
**Rollback:** script/workflow changes are file-level reverts; credential rotation is not rollback-able — do it once, with a validated secret handover.

- **TASK P1-07 — Rotate and purge committed credentials** `SEQUENTIAL REQUIRED` (rotation first, then purge) — OPEN (INF-05)
  - WHY: credentials in git are compromised regardless of repo visibility history; AutoAddPolicy SSH enables MITM.
  - WHAT: rotate Postgres/Redis/JWT/MinIO/Grafana credentials on the server; move all deploy secrets to GitHub Environment secrets; rewrite `ssh_deploy.py` to take host/user/key from env with **no defaults**; switch to key-based SSH with pinned `ssh.Ed25519Key` + host-key verification (drop `AutoAddPolicy`); remove hardcoded IP defaults from both deploy scripts, `nginx.conf:95`, `robots.ts:4`, `sitemap.ts:4`; narrow the gitleaks `tests/` allowlist to specific fixtures.
  - WHERE: files above + server-side rotation (ops runbook `docs/runbooks/`).
  - HOW: 1) generate new secrets → 2) update server env + GitHub secrets → 3) purge repo values in one commit → 4) `gitleaks detect --no-banner` full history documents (not erases) the old leak; force-push history rewrite is optional and requires team coordination — record the rotation instead.
  - TEST: gitleaks full-history scan shows no live-looking credentials in HEAD; deploy rehearsal with new key succeeds; old password rejected.
  - DONE WHEN: `grep -rE "(91\.107\.144\.136|minioadmin123|change_me)" scripts/ nginx/ frontend/app/` is empty and rotation is logged in the runbook.

- **TASK P1-08 — CI-gated deployment + correct compose override** `PARALLEL SAFE` (with P1-07 after rotation) — OPEN (INF-02)
  - WHY: a broken main must not be deployable; prod resource/port/ES-security overrides currently never load.
  - WHAT: in `deploy.sh:58` map `production → docker-compose.prod.yml`, `staging → docker-compose.yml` (fail on unknown); in `deploy.yml` add `workflow_run: ci.yml {completed, success}` guard (or `needs` via reusable workflow).
  - WHERE: `scripts/deploy.sh`, `.github/workflows/deploy.yml`.
  - HOW: case-statement for the override file; `workflow_run` trigger with `jobs.deploy.if: github.event.workflow_run.conclusion == 'success'`; keep manual dispatch for hotfix with explicit `skip_ci=true` input requiring admin environment approval.
  - TEST: staging rehearsal — deploy succeeds on green main; deliberately red CI blocks dispatch.
  - DONE WHEN: deploy logs show `docker-compose.prod.yml` loaded and a red CI makes deployment refuse.

- **TASK P1-09 — Crypto underpayment protection** `PARALLEL SAFE` — OPEN (BE-16)
  - WHY: NowPayments `finished` status does not mean fully paid; accepting it settles an underpaid order.
  - WHAT: in the real-API verify branch, require `actually_paid >= outcome_amount` (or `price_amount_usd` minus fee tolerance from settings, e.g. `CRYPTO_UNDERPAYMENT_TOLERANCE_PCT`, default 1%); underpaid ⇒ return success=False with error_code `CRYPTO_UNDERPAID` and keep payment PROCESSING + `extra_data.underpaid=true` for manual review.
  - WHERE: `backend/app/modules/payments/infrastructure/providers/crypto.py` real verify path (~446-484).
  - HOW: compute expected USD via existing `_convert_irr_to_usd(amount)`; compare against `data["actually_paid"]`.
  - TEST: unit test — mocked poll with `finished` + `actually_paid` 50% ⇒ PaymentResult failure, payment stays PROCESSING; fully-paid ⇒ success.
  - DONE WHEN: underpaid fixture cannot complete a payment.

*(P1-01…P1-06, BE-06/08/09 are DONE (audit) — see backlog.)*

---

### PHASE 2 — Database & Domain Consistency
**Goal:** make the invariants the app enforces in code unbreakable at the schema level, and make the wallet ledger provably authoritative.
**Issues:** DB-01, DB-02, ARCH-03, BE-19.
**Files:** new `backend/alembic/versions/xxxx_add_money_integrity_constraints.py`, `wallet/application/wallet_service.py`, `wallet/application/tasks.py` (new), `worker/celery_app.py`, `main.py`.
**Dependencies:** none blocking; run before e2e/load phases.
**Rollback:** migration `downgrade()` drops the added constraints; constraints are additive (no data reshaping) after the audit step.

- **TASK P2-01 — Money-integrity migration** `SEQUENTIAL REQUIRED` (one revision, one deploy) — OPEN (DB-01/DB-02)
  - WHY: app-level locks are correct but a single unlocked code path or manual SQL can create negative balances/oversell/double redemption.
  - WHAT: single Alembic revision on head `41444c67e586` adding:
    1. `CREATE UNIQUE INDEX uq_coupon_redemptions_coupon_order ON coupon_redemptions (coupon_id, order_id)` — DB guarantee that an order can never redeem one coupon twice, regardless of code path.
    2. CHECK constraints: `wallets.balance >= 0`; `inventory_items.available >= 0`, `reserved >= 0`, `committed >= 0`; `order_items.quantity > 0`; `cart_items.quantity > 0`; optional `order_items` unique `(order_id, variant_id)` (DB-02).
  - WHERE: new revision; model `__table_args__` updated to match.
  - HOW: **pre-flight data audit first** (read-only queries for existing violations: negative balances, duplicate (coupon_id, order_id), zero/negative quantities) — remediate rows in the same revision before adding constraints; use `batch_alter_table` for SQLite-dev compatibility; `downgrade()` drops in reverse order.
  - TEST: migration up/down on fresh DB and on a populated snapshot; `test_concurrency_and_idempotency.py` extended — concurrent duplicate redemption now also fails at DB level; CI migration gate (`alembic check`) stays green.
  - DONE WHEN: constraints exist in `information_schema`, violation attempts raise IntegrityError, and all suites pass.

- **TASK P2-02 — Wallet ledger authority + reconciliation** `PARALLEL SAFE` (after P2-01) — OPEN (ARCH-03)
  - WHY: `get_balance` documents the ledger as source of truth but returns the cached column (wallet_service.py:68-101) — drift is invisible.
  - WHAT: `get_balance` returns the ledger `SUM` (keep the cached column as a hot-path mirror); add daily beat task `reconcile_wallet_balances` that recomputes all ledger sums, updates cached `balance`, and logs + records an exception-center entry when drift exceeded a threshold (drift > 0 pre-fix).
  - WHERE: `wallet_service.py`, new `wallet/application/tasks.py`, `celery_app.py` beat.
  - HOW: reuse the existing SUM query; reconcile in batches of 500 wallets with `FOR UPDATE SKIP LOCKED`-style claiming (mirror outbox pattern).
  - TEST: unit — ledger 100 / cache 90 ⇒ `get_balance` returns 100 and task re-syncs cache; integration — cashback credit then reconcile idempotent.
  - DONE WHEN: drift between cache and ledger is self-healing and alerted, never silent.

- **TASK P2-04 — De-duplicate router mounts** `PARALLEL SAFE` — OPEN (BE-19)
  - WHY: double mounting means duplicate route registration and confusing OpenAPI.
  - WHAT: remove the second (schema-hidden) mount of seo and vendors in `main.py:175-184`.
  - TEST: extend `test_router_integrity.py` to assert no duplicate route paths.
  - DONE WHEN: unique route path set, suites green.

---

### PHASE 3 — Inventory & Pricing
**Goal:** prove the restock lifecycle end-to-end including returns, and eliminate display-layer money ambiguity.
**Issues:** FE-11, returns-restock verification, inventory endpoint auth verification.
**Files:** `orders/application/returns_service.py`, `inventory/application/inventory_service.py`, `frontend/lib/utils.ts` + call sites.
**Dependencies:** BE-07 (restock primitive exists).
**Rollback:** per-commit reverts; no schema impact.

- **TASK P3-01 — Return (RMA) restock** `PARALLEL SAFE` — OPEN
  - WHY: BE-07 fixed cancel-restock; the RETURNED→restock path was never verified.
  - WHAT: when an RMA reaches final approval (`returns_service` transition to RETURNED/completed), call `inventory_service.restock_order` **or** a new `restock_return_items(db, return_id)` that returns only the inspected/approved quantities; decide policy: restock only sellable-condition returns (add `condition` on return items if absent).
  - WHERE: `orders/application/returns_service.py`, `inventory/application/inventory_service.py`.
  - HOW: reuse the reservation-reference fallback in `restock_order`; return items reference order items — map variant→inventory item the same way.
  - TEST: unit — approved full return restocks N units exactly once (idempotent via return status transition); partial return restocks only approved lines.
  - DONE WHEN: a completed return leaves `available` increased by exactly the restocked quantity and inventory transaction rows exist.

- **TASK P3-02 — Single money-format util** `PARALLEL SAFE` — OPEN (FE-11)
  - WHY: ÷10/×10 scattered across `cart-store.ts`, `checkout/page.tsx` is one refactor away from a 10× price bug in display.
  - WHAT: `formatMoney(rials)` + `formatToman(rials)` in `lib/utils.ts` (storage unit = Rial everywhere; display = Toman); replace all call-site conversions; add a comment contract at the util.
  - TEST: vitest unit tests on the formatter (rounding, separators, Persian digits).
  - DONE WHEN: `grep -rn "(\* ?10|/ ?10)" frontend/stores frontend/app` shows no ad-hoc conversions outside the util.

- **TASK P3-03 — Inventory admin-endpoint authorization verification** `PARALLEL SAFE` — OPEN
  - WHY: stock mutation must be admin-only; audit verified RBAC on ~20 routers but inventory router (152 lines) needs explicit verification.
  - WHAT: verify every mutating `/inventory` route has `RequirePermissions("inventory:write")` (or equivalent); add missing guards; add an authz test hitting each route with a customer token expecting 403.
  - TEST: security test (route matrix).
  - DONE WHEN: customer token cannot mutate inventory from any route.

---

### PHASE 4 — Cart & Checkout
**Goal:** honest cart behavior and an explicit guest-checkout decision.
**Issues:** FE-05, FE-12, ARCH-01, cart silent errors.
**Files:** `stores/cart-store.ts`, `hooks/use-cart.ts`, `lib/api/queries.ts`, `checkout/page.tsx`, backend `checkout/**` (decision-dependent).
**Dependencies:** BE-03 (payment validation done) — no further backend blockers.
**Rollback:** frontend commits revert cleanly; guest-checkout schema change gets its own migration.

- **TASK P4-01 — Guest checkout decision** `SEQUENTIAL REQUIRED` (decision gates P5-01 scope) — OPEN (ARCH-01)
  - WHY: guest carts are advertised by the UI but cannot be converted; this is a product decision, not a bug fix.
  - WHAT (decision): **Option A (recommended for Iranian market — phone-OTP is low-friction): keep login-required checkout; remove guest-cart affordances from the UI and document it. Option B: implement guest checkout** — make `orders.user_id` nullable + add `guest_email/guest_phone` columns, accept `X-Session-ID` carts in checkout, capture contact info in the address snapshot, and attach the order to a user at registration/login via session match.
  - WHERE: `checkout/api/routes.py`, `checkout_service.py`, orders models/migration (Option B), frontend checkout guard.
  - TEST (Option B): integration guest journey — guest cart → order → payment → verify; order ownership via session id; registration later claims the order.
  - DONE WHEN: decision recorded in `docs/adr/` and the chosen path implemented or the UI no longer implies guest checkout.

- **TASK P4-02 — Cart error honesty** `PARALLEL SAFE` — OPEN
  - WHY: cart mutations currently swallow API errors leaving optimistic state that lies (cart-store.ts:248-252, 299-303, 357-361, fetchCart 183-186).
  - WHAT: on sync failure roll back the optimistic change (or re-fetch server state) and toast the failure; `fetchCart` failure sets an error flag consumed by the cart page for a retry banner.
  - TEST: vitest store tests — mocked failing POST ⇒ state reverts, error flag set.
  - DONE WHEN: no code path leaves optimistic-only cart state after a failed sync.

- **TASK P4-03 — One add-to-cart path** `PARALLEL SAFE` — OPEN (FE-12)
  - WHY: favorites page bypasses the zustand sync path; header badge goes stale.
  - WHAT: make `favorites/page.tsx` use `useCart().addItem`; delete the unused `useCartQuery`/`useAddToCart` query path in `queries.ts:135-145, 230-245`.
  - TEST: tsc + manual favorites→add→badge check.
  - DONE WHEN: single implementation referenced by all surfaces.

- **TASK P4-04 — Shipping quote honesty** `PARALLEL SAFE` — OPEN (FE-05)
  - WHY: fake shipping methods with fabricated UUIDs can silently diverge from the charged amount.
  - WHAT: on quote failure show an explicit error panel ("نرخ حمل در دسترس نیست؛ هزینه نهایی در ثبت سفارش محاسبه می‌شود") and disable the submit button until a quote succeeds; compute `weight` from cart items (sum variant weights, fallback per-item 1.5 declared as such); replace static delivery-slot strings with an API-backed picker or remove the UI.
  - WHERE: `checkout/page.tsx:275-345`, `lib/iranian-commerce.ts:138-181`.
  - TEST: tsc + manual quote-failure path (block backend port) shows error, not fake options.
  - DONE WHEN: no fabricated shipping method ids can be submitted.

---

### PHASE 5 — Payment & Order
**Goal:** codify the corrected money flow as executable journey tests; harden invoices.
**Issues:** TEST-01, BE-15.
**Files:** `backend/tests/integration/test_checkout_payment_journey.py` (new), `orders/api/routes.py`, `invoice_service.py`.
**Dependencies:** DB-01 migration (runs against real schema semantics); P4-01 decision (journey scope).
**Rollback:** tests only + optional invoice-token feature flag.

- **TASK P5-01 — Checkout→payment→order E2E (backend integration)** `SEQUENTIAL REQUIRED` (after P2-01) — OPEN (TEST-01)
  - WHY: the corrected flow currently has unit coverage per piece but no end-to-end executable proof.
  - WHAT: integration test (CI Postgres): seed user/variant/stock/coupon → login → add to cart → `POST /checkout/create-order` → assert single order, snapshots, committed stock, cart CONVERTED → `POST /payments` (mock provider, dev) → webhook verify → assert payment COMPLETED, order CONFIRMED exactly once → cancel → assert restock. Variants: amount mismatch (422), foreign order (404), non-PENDING (409), insufficient wallet (402).
  - DONE WHEN: journey test passes in CI with real Postgres service.

- **TASK P5-02 — Duplicate/delayed webhook E2E** `PARALLEL SAFE` — OPEN
  - WHAT: replay the same callback 3× (interleaved with a racing `POST /payments/{id}/verify`) ⇒ exactly one wallet debit (wallet provider), exactly one order transition, exactly one `PaymentWebhookEvent.processed`.
  - DONE WHEN: assertion of single-effect under race holds repeatedly (property-style loop of 20 runs).

- **TASK P5-03 — Invoice token hardening** `PARALLEL SAFE` — OPEN (BE-15)
  - WHAT: replace header-or-query JWT with a short-lived (5 min), single-purpose, order-scoped HMAC token minted by `POST /orders/{id}/invoice-link` (owner-only); invoice page accepts only that token type; remove query-JWT acceptance.
  - TEST: unit — expired/reused/foreign-order token rejected.
  - DONE WHEN: query-string JWT acceptance removed.

---

### PHASE 6 — Refund / Return / Wallet
**Goal:** complete the reverse-money loop with events and a legitimate top-up path.
**Issues:** P6-02 feature (replaces the fail-closed deposit), refund/cancel event publication.
**Files:** `payment_service.py`, `wallet/api/routes.py`, `providers/zarinpal.py` (reuse), frontend wallet UI.
**Dependencies:** BE-01..03 (done); notification consumption (P8-01) for the UX loop.
**Rollback:** feature-flag the new top-up endpoint.

- **TASK P6-01 — Publish reverse-flow events** `PARALLEL SAFE` — OPEN
  - WHAT: publish `OrderCanceled`, `RefundProcessed`, `ReturnApproved` outbox events in `cancel_order`, `refund_payment`, `returns_service` transitions (same publish-in-transaction pattern as verify).
  - TEST: unit asserts publish per transition.
  - DONE WHEN: reverse-flow events observable in outbox after each action.

- **TASK P6-02 — Wallet top-up via gateway** `SEQUENTIAL REQUIRED` (after P6-01) — OPEN
  - WHY: the fail-closed deposit leaves production users with no way to top up.
  - WHAT: `POST /wallet/topup` creates a Payment with `extra_data.purpose="wallet_topup"`, amount validated ≥ minimum; on gateway verify success, `verify_payment` special-cases top-up payments (no order) by crediting the wallet **once** (idempotency: payment status transition) instead of confirming an order; admin manual-adjust endpoint (permission `wallet:manage`) for support corrections with audit reason.
  - WHERE: `payment_service.py` (verify branch), `wallet/api/routes.py`, `payment_service.create_payment` (allow purpose without order), frontend wallet UI.
  - TEST: unit — top-up verify credits exactly once, double verify no double credit; integration — full zarinpal(mock) top-up journey.
  - DONE WHEN: production users can top up end-to-end and the old dev-only deposit remains 403.

---

### PHASE 7 — Search & Cache
**Goal:** make the search index event-driven and provably a projection.
**Issues:** BE-11, BE-18.
**Files:** `catalog/application/catalog_service.py` (write paths), `search/application/search_service.py`, `search/infrastructure/elasticsearch_client.py`.
**Dependencies:** BE-09 (outbox live) — DONE.
**Rollback:** publisher calls are additive; handler exists already.

- **TASK P7-01 — Catalog → outbox → index** `PARALLEL SAFE` — OPEN (BE-11)
  - WHAT: publish `ProductCreated/Updated/Deleted` (payload `{product_id}`) inside the same transaction as every admin product/variant/price/stock write in `catalog_service`; the outbox handler already dispatches `sync_single_product`. Add a publish helper to avoid N copies.
  - TEST: unit — update product ⇒ outbox row; integration (CI) — create/update/delete product then drained outbox ⇒ index reflects change (or sync task invoked; assert via task mock if ES unavailable).
  - DONE WHEN: a price/stock change is visible in search without waiting for the nightly reindex.

- **TASK P7-02 — Rating in index** `PARALLEL SAFE` — OPEN
  - WHAT: populate `rating_average`/`rating_count` in `_product_to_doc` from the reviews aggregate (subquery), recompute on review approval via the same outbox mechanism.
  - TEST: unit on doc builder; integration on review approval.
  - DONE WHEN: sort by rating works on real data.

- **TASK P7-03 — Analyzer settings cleanup** `PARALLEL SAFE` — OPEN (BE-18)
  - WHAT: merge the duplicate `"filter"` dicts in `PERSIAN_ANALYSIS_SETTINGS` into one; assert index-creation settings with a unit test.
  - DONE WHEN: single filter list; index settings test passes.

- **TASK P7-04 — Cache ownership audit** `PARALLEL SAFE` — OPEN
  - WHAT: enumerate every Redis key family (settings cache, rate limits, sessions, ES-free caches), document owner/TTL/invalidation in `docs/integration-system-map.md` §5; remove any cache that is read as business truth.
  - DONE WHEN: cache inventory documented; no cache is authoritative for money/stock.

---

### PHASE 8 — ERP / CRM / Notifications
**Goal:** every customer-visible business event produces the right notification exactly once; document the ERP/CRM boundary honestly.
**Issues:** BE-12, docs.
**Files:** `automation/application/outbox_worker.py`, `notifications/application/notification_service.py`, `orders/application/tasks.py`.
**Dependencies:** BE-09 (DONE), P6-01 (reverse events).
**Rollback:** handler changes revert cleanly; notifications are best-effort by design (failure logged, never blocks payment).

- **TASK P8-01 — Event→notification wiring** `PARALLEL SAFE` (with Phase 7) — OPEN (BE-12)
  - WHAT: outbox handlers map: `OrderConfirmed` → order-confirmation notification; `PaymentCompleted` → receipt; `OrderCanceled` → cancellation (+refund-pending note); `RefundProcessed` → refund receipt; `ReturnApproved` → return instructions. Each handler: resolve user → `notification_service.create_notification` (DB row = delivery record) → `send_notification_task.delay(notification_id)` (existing signature). Failures: log + leave outbox retry to surface in DLQ (already observable).
  - TEST: unit per handler (mock providers); integration — webhook → payment completed → notification row exists with correct recipient/order id.
  - DONE WHEN: a real journey produces exactly one notification per event, with duplicate webhook producing zero duplicates (dedup upstream).

- **TASK P8-02 — ERP/CRM boundary record** `PARALLEL SAFE` — OPEN
  - WHAT: `docs/adr/000X-erp-crm-boundary.md`: invoices (invoice_service) are the finance artifact; no external ERP integration exists; CRM-as-customer-record = Postgres users/orders; any future integration must consume outbox events only. Prevents aspirational docs from implying nonexistent integrations.
  - DONE WHEN: ADR merged and linked from README.

---

### PHASE 9 — Frontend / UX / Mobile
**Goal:** remove every silent mock/fabricated success a real customer or admin can hit; single source of frontend truth for types and money.
**Issues:** FE-03 remainder, FE-04, FE-06, FE-07, FE-08, FE-09, FE-10, FE-13, UX-01.
**Files:** `frontend/app/**`, `frontend/components/**`, `frontend/lib/**`.
**Dependencies:** backend truth already fixed; P8-01 makes notification states available.
**Rollback:** per-page commits; each task independently revertible.

- **TASK P9-01 — PDP fallback removal** `PARALLEL SAFE` — OPEN (FE-03 remainder)
  - WHAT: mirror the listing fix in `products/[slug]/page.tsx`: delete `fallbackProduct/fallbackReviews/fallbackStats`; error card with retry; 404 state for unknown slug; remove the fake "success on review failure" catch (UX-01).
  - DONE WHEN: API-down PDP never renders a product that isn't in the DB.

- **TASK P9-02 — Account dashboard honesty** `PARALLEL SAFE` — OPEN (FE-04/UX-01)
  - WHAT: delete `INITIAL_*` mock seeds; render real empty states ("هنوز سفارشی ثبت نکرده‌اید" etc.); error banners with retry for the 5 fetches; profile/address mutations surface server errors (no unconditional success toast); keep the deposit fix.
  - DONE WHEN: killing the backend yields empty/error states, never fake orders or balances.

- **TASK P9-03 — Admin backoffice reality pass** `PARALLEL SAFE` — OPEN (FE-07)
  - WHAT: (1) product writes → `/catalog/products`; (2) `admin/users`: real list + remove `mockUsers`, wire role edit to RBAC endpoints; (3) categories: real create/edit or remove the button; (4) approvals: remove "fallback simulation", show errors; (5) kanban/dashboard: fix malformed `/orders/admin/orders` probes to the real admin orders endpoint; (6) reports/pages/settings: wire to settings/approvals APIs where they exist, otherwise mark explicitly "خارج از محدوده" (no fake save states).
  - TEST: tsc + scripted admin smoke (playwright optional).
  - DONE WHEN: every admin mutation either hits the backend or is visibly disabled.

- **TASK P9-04 — Home page real data** `PARALLEL SAFE` — OPEN (FE-09)
  - WHAT: featured products via `useProducts({is_featured:true, page_size:8})` with skeleton/empty handling; graceful hide of sections whose API fails.
  - DONE WHEN: no hardcoded product objects remain in the file.

- **TASK P9-05 — Blog fallback removal** `PARALLEL SAFE` — OPEN (FE-06)
  - WHAT: remove `fallbackPosts/fallbackCategories` in `lib/api/blog.ts`; unknown slug → notFound(); error → page-level retry.
  - DONE WHEN: `grep -c fallback` in blog api file is 0.

- **TASK P9-06 — Server-authoritative gamification** `SEQUENTIAL REQUIRED` (new endpoints before UI switch) — OPEN (FE-08)
  - WHAT: backend: `POST /gamification/spin` (server RNG, per-user daily limits, prize recorded in ledger/points table), `POST /gamification/claims/{id}/redeem` (permission + stock of rewards); frontend: replace localStorage points/spins with API state; migrate-on-read from old localStorage keys once.
  - TEST: unit (RNG bounds, daily limit, concurrency — no double claim), security (cannot self-assign prize).
  - DONE WHEN: manipulating localStorage grants nothing.

- **TASK P9-07 — Type contract consolidation** `PARALLEL SAFE` — OPEN (FE-10)
  - WHAT: make `lib/api/services.ts` shapes canonical; delete/align `types/index.ts` + `lib/api/types.ts`; remove the `o.total_price || o.total || o.final_price` defensive chains once types match.
  - DONE WHEN: `tsc` green with single Product/Order type imports.

- **TASK P9-08 — Dead code removal** `PARALLEL SAFE` — OPEN (FE-13)
  - WHAT: delete `$RV/$RB` flush in `providers.tsx:9-25`, `evaluateCoupon` mock (iranian-commerce.ts:210-251); keep Luhn/BIN/postal validators (real logic).
  - DONE WHEN: removed, suites green.

- **TASK P9-09 — Mobile journey QA pass** `PARALLEL SAFE` (after P9-01..04) — OPEN
  - WHAT: scripted manual pass at 320/360/375/390/412/430 for home, PLP, PDP, cart, checkout, callback, orders, wallet; file defects as tasks; fix blockers (sticky CTA overlap, bottom-sheet traps, input zoom).
  - DONE WHEN: checklist in `docs/production/` completed with screenshots.

---

### PHASE 10 — AI / Analytics
**Goal:** no aspirational AI claims; analytics fires only on backend-confirmed truth.
**Issues:** ARCH-02, analytics event sourcing.
**Files:** `docs/adr/`, `analytics/**`.
**Rollback:** docs + additive event handlers.

- **TASK P10-01 — AI decision record** `PARALLEL SAFE` — OPEN (ARCH-02)
  - WHAT: ADR stating AI commerce is not implemented and will consume only outbox events + existing search APIs if ever built (never a source of truth). Removes ambiguity for stakeholders.
  - DONE WHEN: ADR merged.

- **TASK P10-02 — Backend-sourced commerce analytics** `PARALLEL SAFE` — OPEN
  - WHAT: analytics event ingestion hooks to outbox `OrderConfirmed/PaymentCompleted/RefundProcessed` (server-side `purchase_complete` etc.); frontend fires only discovery events (view/search/cart); delete or gate any client-side purchase events.
  - TEST: integration — verify payment ⇒ one purchase event; duplicate webhook ⇒ still one.
  - DONE WHEN: no analytics success event exists that the backend did not confirm.

---

### PHASE 11 — Performance / Observability
**Goal:** make the system measurable and limit abuse at the right layer.
**Issues:** BE-13, BE-14, INF-07, PERF-01, TEST-03, BE-17.
**Files:** `core/security/rate_limiter.py`, route files, `auth_service.py`, `monitoring/**`, `worker/*`, `load_tests/**`.
**Dependencies:** P12-01 for alert drill; load tests need a staging deployment.
**Rollback:** limiter settings are env-tunable; monitoring files additive.

- **TASK P11-01 — Rate limiting + trusted proxy IP** `SEQUENTIAL REQUIRED` (IP fix before limiter expansion — wrong IP logic would key limits on spoofable values) — OPEN (BE-13)
  - WHAT: add `TRUSTED_PROXY_COUNT` (default 1 behind nginx); `get_real_client_ip` takes the rightmost-N hop of XFF, falling back to socket addr; decorate with sensible limits: `POST /cart/items` 60/min, `/checkout/*` 10/min, `/payments` 10/min, `/orders/*/cancel|returns` 10/min, review/wishlist writes 30/min; document per-route limits in one module.
  - TEST: unit — XFF `1.2.3.4, 10.0.0.1` with TRUSTED_PROXY_COUNT=1 ⇒ `10.0.0.1`; integration — 11th checkout in a minute ⇒ 429.
  - DONE WHEN: spoofed XFF cannot rotate rate-limit identity; write routes limited.

- **TASK P11-02 — Alerting + dashboards + worker metrics** `PARALLEL SAFE` — OPEN (INF-07/PERF-01)
  - WHAT: Prometheus rules: `readyz==0` 2m, payment verify failure rate, outbox DEAD_LETTER count > 0, reservation-expiry backlog, 5xx rate, P95 latency; Alertmanager → email/SMS; provision 2 Grafana dashboards (commerce, infra); expose celery worker metrics on the existing port or fix the scrape target; enable the commented postgres/redis exporters.
  - DONE WHEN: killing redis in staging fires an alert within 3 minutes.

- **TASK P11-03 — Load-test rerun** `SEQUENTIAL REQUIRED` (after DB-01 + staging) — OPEN (TEST-03)
  - WHAT: run restored locust scenarios (browse/checkout/wallet) against staging; record P95/P99 + error budgets; fix any N+1 surfaced (query-performance script is in CI-able form).
  - DONE WHEN: report committed under `load_tests/reports/` with targets met (or documented exceptions).

- **TASK P11-04 — Refresh reuse detection** `PARALLEL SAFE` — OPEN (BE-14)
  - WHAT: add `token_family` (uuid) to `user_sessions`; on refresh with a revoked-family token ⇒ revoke all family sessions + `log_security_event`; tested.
  - DONE WHEN: replayed refresh kills the family and raises a security event.

- **TASK P11-05 — Casbin decision** `PARALLEL SAFE` — OPEN (BE-17)
  - WHAT: either replace `RequirePermissions` claims-check with casbin policy checks on admin routers, or delete casbin + policy files; do not keep both.
  - DONE WHEN: one authorization mechanism remains, documented.

---

### PHASE 12 — Final Production Hardening
**Goal:** deployment-environment truth: TLS/proxy correctness, minimal exposure, proven backups, verified deploy.
**Issues:** INF-03, INF-04, INF-08, ALLOWED_HOSTS, node/dev-deps alignment, P12-04 go/no-go.
**Files:** `nginx/nginx.prod.conf`, `docker-compose*.yml`, `.env.example`, `scripts/backup.sh` scheduler, `docs/deployment/**`, `backend/Dockerfile`, `frontend/Dockerfile`.
**Dependencies:** INF-02 (deploy gating), P1-07 (rotation).
**Rollback:** infra files versioned; backup drill is additive.

- **TASK P12-01 — Nginx prod correctness** `SEQUENTIAL REQUIRED` (blocks alert drill + load tests) — OPEN (INF-03)
  - WHAT: entrypoint `envsubst` on `${DOMAIN}` vars (official nginx image pattern) or template + render step in deploy; add `location /healthz`, `/readyz` (proxy to backend, no auth, no rate limit), remove `/health`; keep ACME path.
  - TEST: `nginx -t` in container; external probe of `/readyz` returns backend JSON.
  - DONE WHEN: deploy health checks in `deploy.yml` hit a real readiness endpoint.

- **TASK P12-02 — Exposure & defaults hardening** `PARALLEL SAFE` — OPEN (INF-04)
  - WHAT: dev compose binds postgres/redis/es/minio/prometheus/grafana to `127.0.0.1`; remove weak compose fallbacks (require env, fail fast); prod settings fail-fast requires `NOWPAYMENTS_API_KEY`, `NOWPAYMENTS_IPN_SECRET`, non-default MinIO/Grafana creds when `ENVIRONMENT=production` (extend the existing PAY-001 guard); `BACKEND_ALLOWED_HOSTS` default → explicit domain list; rotate the weak local `.env` values (ops).
  - TEST: boot with production env missing a required secret ⇒ refuses to start (test the settings guard).
  - DONE WHEN: no weak default can reach a production boot.

- **TASK P12-03 — Backup + restore proof** `PARALLEL SAFE` — OPEN (INF-08)
  - WHAT: nightly scheduled `backup.sh` (host cron or systemd timer) + MinIO `mc mirror` off-box; document RPO/RTO; execute one full restore drill into a scratch container and record table counts + checksum match in `docs/deployment/restore-drill-YYYY-MM-DD.md`.
  - DONE WHEN: restore drill artifact exists and is dated after this roadmap.

- **TASK P12-04 — Deployment-vs-repo verification + go/no-go** `SEQUENTIAL REQUIRED` (last) — OPEN
  - WHAT: runbook: verify deployed SHA == main HEAD, `alembic current == head`, `/readyz` green, callback URL round-trip, gateway credentials live, search index fresh, backups scheduled; final verdict update in `docs/ecommerce-final-integration-audit.md` (YELLOW → GREEN criteria listed there).
  - DONE WHEN: runbook executed with evidence; verdict updated.

- **TASK P12-05 — Image/dependency hygiene** `PARALLEL SAFE` — OPEN
  - WHAT: backend runtime image drops `.[dev]` (install `.` only in builder, copy site-packages); frontend Dockerfile node:22-alpine (align with CI); remove `npm ci || npm install` fallback (lockfile-only).
  - TEST: docker builds + compose up + smoke.
  - DONE WHEN: runtime images contain no test tooling; node versions match.

---

## 4. Test Strategy Map

| Task | Unit | Integration | E2E | Concurrency | Security | Regression |
|---|---|---|---|---|---|---|
| P0-01/02 (CI gates) | — | CI run | — | — | gitleaks/Trivy/ZAP | — |
| P1-07 (rotation) | — | — | — | — | **gitleaks full-history** | — |
| P1-08 (deploy gate) | — | staging rehearsal | — | — | — | — |
| P1-09 (underpayment) | ✅ mocked poll | — | — | — | ✅ | ✅ |
| P2-01 (constraints) | — | ✅ up/down + violation attempts | — | ✅ coupon race | — | ✅ |
| P2-02 (ledger authority) | ✅ | ✅ reconcile idempotent | — | — | — | ✅ |
| P3-01 (return restock) | ✅ | — | — | ✅ idempotent restock | — | ✅ |
| P4-02/03/04 (cart/checkout UI) | ✅ store tests | — | — | — | — | ✅ |
| P4-01 (guest decision) | — | ✅ guest journey (if B) | — | — | ✅ ownership | — |
| P5-01/02 (journey + webhook race) | — | ✅ real-PG journey | ✅ | ✅ verify/webhook race | ✅ 403/404 matrix | ✅ |
| P5-03 (invoice token) | ✅ | — | — | — | ✅ token misuse | — |
| P6-02 (top-up) | ✅ once-only credit | ✅ gateway journey | — | — | — | ✅ |
| P7-01/02 (search sync) | ✅ publish/doc | ✅ index reflects | — | — | — | ✅ |
| P8-01 (notifications) | ✅ handlers | ✅ event→row | — | — | ✅ recipient match | ✅ |
| P9-* (frontend honesty) | ✅ vitest | — | manual/scripted QA | — | — | ✅ tsc/build |
| P10-02 (analytics) | — | ✅ event sourcing | — | — | — | ✅ |
| P11-01 (rate limit/XFF) | ✅ IP extraction | ✅ 429s | — | — | ✅ spoof resistance | — |
| P11-02 (alerts) | — | ✅ staging drill | — | — | — | — |
| P11-03 (load) | — | — | ✅ load | ✅ oversell/double-spend under load | — | — |
| P12-* (hardening) | — | ✅ boot/probe/restore | — | — | ✅ fail-fast boots | — |

Only the needed types are used per task — e.g., no E2E for CI file changes, no load tests for UI honesty fixes.

---

## 5. Parallelization Map

- **PARALLEL SAFE tracks** (independent files, no shared domain writes):
  - Track A (frontend honesty): P9-01, P9-02, P9-03, P9-04, P9-05, P9-07, P9-08
  - Track B (search): P7-01, P7-02, P7-03
  - Track C (notifications): P8-01 (after P6-01 events exist)
  - Track D (infra): P12-02, P12-03, P12-05
  - Track E (security misc): P11-04, P11-05, P3-03
- **SEQUENTIAL REQUIRED:**
  - P1-07 → P1-08 (rotation before deploy changes reference new secrets)
  - P2-01 → P5-01/P5-02 → P11-03 (schema → journey tests → load)
  - P11-01 ordering inside the task (IP fix before limiter expansion)
  - P6-01 → P6-02 → P8-01 consumption of refund/cancel events
  - P12-01 → P11-02 drill + P11-03 → P12-04 (go/no-go last)
- **Never parallelize:** two tasks touching `payment_service.py` (P1-09, P5-03, P6-02 — serialize in the order listed).

---

## 6. Final Prioritized Roadmap

**P0 — must fix before production** *(all DONE in the audit)*
BE-01, BE-02, BE-03, BE-04, BE-05, BE-07, INF-01 — plus P0-01/P0-02 CI gates before the next merge.

**P1 — must fix before serious production usage**
P1-07 (credential rotation — INFRASTRUCTURE BLOCKER), P1-08 (CI-gated deploy + prod overrides), P1-09 (crypto underpayment), then the P2-01 constraint migration (money integrity at rest).

**P2 — important improvements**
P2-02 wallet reconciliation · P4-01 guest-checkout decision · P4-02/03/04 cart & checkout honesty · P7-01/02 search freshness · P8-01 notifications · P9-01/02/03/06 frontend truth (PDP, account, admin, gamification) · P10-02 analytics sourcing · P11-01 rate limiting/XFF · P11-02 alerting · P11-04 reuse detection · P3-01/03 return restock + inventory authz · INF-03/04/06/07/08 infra items in their phases.

**P3 — polish / technical debt**
P5-03 invoice token · P3-02 money util · P7-03/04 · P9-04/05/07/08/09 · P10-01 · P11-05 · P2-04 · DB-02 · BE-15/17/18/19 · FE-06/09/10/11/12/13.

### Critical Path (exact order)

```
[Already done: BE-01..10, FE-01..03, INF-01 — regression baseline green]

1. P0-01 + P0-02        CI gates (lint + security scans fail builds)
2. P1-07                rotate + purge credentials          (SEQUENTIAL)
3. P1-08                CI-gated deploy, prod overrides on  (parallel after 2)
4. P2-01                money-integrity migration           (blocks 5, 9)
5. P5-01 + P5-02        journey + webhook-race E2E          (parallel after 4)
6. P1-09                crypto underpayment guard           (parallel; payment file serialized)
7. P6-01                reverse-flow events                 → 8
8. P6-02 + P8-01        top-up flow + notifications         (8 consumes 7)
9. P2-02 + P3-01        wallet reconcile + return restock   (parallel, after 4)
10. Track A ∥ B         frontend honesty ∥ search freshness (parallel)
11. P11-01              rate limits + trusted-proxy IP
12. P12-01              nginx prod correctness              (blocks 13, 14)
13. P11-02 + P11-03     alert drill ∥ load-test rerun       (parallel, after 12)
14. P12-02 + P12-03 + P12-05  hardening, backups, images    (parallel)
15. P12-04              deployment-vs-repo verification + go/no-go → verdict GREEN criteria check
```

**Stopping rule:** no task is "done" without its listed test passing in CI; any acceptance criterion that cannot be met becomes a new row in the backlog rather than a silent scope cut.
