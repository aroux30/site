# Final E-Commerce Integration & Production Audit — ARoux30 / SITE

**Audit date:** 2026-09-11
**Scope:** full end-to-end integration audit of the repository at `main` (commit `42f3973` + this audit's changes), verified against source code, tests, container/CI configuration, and the runnable frontend/backend toolchains. Documentation claims were treated as hypotheses and independently checked.

**Companion documents:**
- `docs/integration-system-map.md` — the verified runtime architecture and data-ownership map
- `docs/integration-matrix.md` — feature-by-layer integration matrix + journey results
- `docs/cross-system-bug-matrix.md` — every confirmed defect with root cause, fix, and test

---

# Executive Summary

The platform is a real, substantially engineered commerce system — not a facade. The backend implements a coherent single-transaction checkout (live-price line items, row-locked inventory reservation, server-side tax/coupon/shipping, idempotency keys, full snapshots), a genuinely concurrency-safe inventory and wallet ledger, a deterministic order state machine, a production-grade transactional outbox, refresh-rotating JWT auth with brute-force protection, and 4 clean linear Alembic migrations. The frontend is a complete Persian RTL storefront wired to the real API through nginx.

However, the audit found the platform was **one integration step short of safe in the money paths**: three separate defects allowed orders to be confirmed without real payment, one allowed balance to be minted without payment, and the deployment side had quietly deleted its own test suite to keep CI green. The most customer-journey-critical gap — the missing payment-callback page — meant that a customer who *successfully paid* was returned to a 404.

**All P0 defects were fixed in this audit with regression tests.** Backend unit suite: **176/176 green**. Frontend: typecheck clean, **30/30 vitest**, production build of 39 pages green.

# Is the Platform Truly Integrated?

**PARTIALLY — now materially closer to YES after this audit's fixes.**

- The **core commerce spine (browse → cart → server-priced checkout → pay → verify → confirm → fulfill → refund) is integrated and verified end-to-end in code** as of this audit's fixes.
- It is not yet a full "YES" because of remaining known gaps that are documented rather than hidden: the **home page is static**, several **admin pages are mock-first**, **transactional notifications are not wired** to payment/order events, **search indexing is nightly-only**, **guest checkout is not supported**, and deployment/observability hardening (CI-gated deploys, alerting, offsite backups) is incomplete.

# Previous State (as found, before fixes)

- CI contained **zero tests**: 24 backend test files, 7 frontend test files, `vitest.config.ts`, the entire `load_tests/` suite, deploy scripts, and `deploy.yml` had been deleted in the working tree, and the pytest/vitest steps were stripped from `ci.yml` (BUG-INF-01).
- Wallet payments **never debited the wallet** (free orders) — BUG-BE-01.
- `POST /wallet/deposit` credited real balance with **no payment** (free money) — BUG-BE-02.
- Payment creation **never validated amount vs. order total**, ownership, or order state — BUG-BE-03; the verify endpoint had **no ownership check and no row lock** — BUG-BE-04.
- NowPayments IPN signatures were **skipped when the secret was unset** and simulated success was baked into the production provider — BUG-BE-05.
- Cancelled/unpaid orders **never restocked inventory**, and inventory was committed at checkout before payment with no unpaid-order expiry — guaranteed phantom overselling — BUG-BE-07.
- The reservation-expiry and outbox-drain tasks existed but were **not scheduled** — BUGS BE-08/09.
- The payment callback page **did not exist** — paying customers hit a 404 — BUG-FE-01; checkout never initiated `/payments` for wallet or crypto — BUG-FE-02.
- The products listing silently displayed **fabricated products with fake prices** on API failure and during loading — BUG-FE-03.

# Current State (after this audit)

| Verification standard | Result |
|---|---|
| Backend unit suite (incl. 10 new regression tests) | **176/176 PASS** |
| Backend integration suite (Postgres-backed) | Runs in CI with service containers; not runnable in this audit environment (**NOT TESTABLE here**) |
| Frontend `tsc --noEmit` | PASS |
| Frontend vitest | **30/30 PASS** |
| Frontend production build | PASS (39 routes; new callback routes present) |
| Alembic chain | 4 linear migrations, single head, no destructive upgrades |
| Fail-closed boot guards | Verified (`PAYMENT_PROVIDER=mock`/sandbox rejected in production; placeholder JWT secrets rejected) |
| Money-path row locking | Verified: payments, orders, inventory, wallet all `FOR UPDATE` |

# Target State

One coherent commerce system where every P0 above is fixed (done), the OPEN items in `cross-system-bug-matrix.md` are closed in the recommended order below, and a live deployment is compared against the repository (deployment-environment audit could not be performed from this machine — **NOT TESTABLE** here).

# Top Integration Problems (ranked, post-fix status)

1. **Free orders via wallet provider** — P0 — **FIXED**
2. **Free wallet balance via deposit endpoint** — P0 — **FIXED**
3. **Unvalidated payment amount / ownership / order state** — P0 — **FIXED**
4. **Verify endpoint IDOR + verify/webhook race** — P0 — **FIXED**
5. **Forgeable NowPayments IPN in production** — P0 — **FIXED**
6. **Gutted CI (all tests deleted)** — P0 — **FIXED**
7. **Permanent stock lock on unpaid/cancelled orders** — P0 — **FIXED**
8. **Payment return journey 404** — P1 — **FIXED**
9. **Wallet/crypto never initiated by checkout** — P1 — **FIXED**
10. **Fake products/prices shown on API failure** — P1 — **FIXED (listing; PDP pattern still OPEN)**
11. **Unscheduled reservation-expiry / outbox-drain / low-stock tasks** — P1 — **FIXED**
12. **IDPay amount ignored** — P1 — **FIXED**
13. **Deploy not CI-gated; prod compose overrides never applied by deploy.sh** — P1 — OPEN
14. **Real-looking credentials committed in `scripts/ssh_deploy.py`** — P1 — OPEN (rotation required)
15. **Transactional notifications never sent** — P2 — OPEN

# Verified Working Features

- **Checkout integrity** — single transaction; live-price line items; coupon redemption under `FOR UPDATE`; server-side tax & shipping; order/item/address snapshots; idempotency enforced by DB unique key (checkout_service.py:345-547).
- **Inventory concurrency** — pessimistic locking on every mutation; overselling rejected under lock; 100-concurrent-reservation test with zero oversell; reservation confirm/release race-safe.
- **Wallet ledger** — append-only signed ledger; debits under `FOR UPDATE`; negative balance impossible; per-transaction `balance_after`.
- **Order state machine** — explicit transition table; customer-cancel restrictions; ownership filters on every order query; status history rows for every transition.
- **Payment webhook idempotency** — `payment_webhook_events` unique `(provider, event_id)`; duplicate/delayed callbacks return current state without double-processing (verified by test).
- **Refund safety** — per-refund and cumulative caps under row locks; double-refund blocked (verified by test).
- **Auth & session security** — JWT access/refresh with type claims; real refresh rotation with session revocation; brute-force progressive lockout (Redis); TOTP/WebAuthn; PII masking incl. card PANs; security audit logging; Casbin enforcer present (though unused — see gaps).
- **Transactional outbox** — `FOR UPDATE SKIP LOCKED` claiming, lease-based crash recovery, exponential backoff, dead-letter state (verified by test).
- **Search infrastructure** — custom Persian analyzer (Arabic→Persian chars/digits, ZWNJ, stopwords, edge-ngram autocomplete); read-only projection; safe empty degradation when ES is down.
- **Invoices** — Jalali/Persian invoice rendering service with tests.
- **Health endpoints** — `/readyz` genuinely checks Postgres/Redis/ES/MinIO and returns 503 with per-dependency status.
- **DB safety** — no destructive migration upgrades; single head; unique constraints on order number/idempotency, payment idempotency, wallet per user, inventory per variant, webhook dedup.
- **Fail-closed production guards** — mock provider, sandbox mode, placeholder secrets all rejected at boot in production.

# Verified Broken Features (all fixed in this audit)

See items 1–12 above; full root-cause write-ups in `cross-system-bug-matrix.md`. Regression coverage: `backend/tests/unit/test_payment_hardening.py`.

# Partially Implemented Features

- **Guest checkout** — guest carts exist (session-header based) but checkout requires login; the guest journey is impossible by design. Decide: implement guest checkout or remove guest-cart affordances from the UI.
- **Returns/RMA** — lifecycle tested; restock on return completion not verified; refunds connect through payments.
- **Shipping** — carrier provider factory + tracking API are real; the frontend shipping-quote fallback is still hardcoded (BUG-FE-05).
- **Cashback** — backend rules + scheduled crediting are real; the storefront wheel economy is client-side demo (BUG-FE-08).
- **Admin backoffice** — orders/payments/vendors/approvals are real and RBAC-enforced backend-side; users/categories/reports/pages/settings pages are mock-first (BUG-FE-07).
- **Search freshness** — nightly reindex only; outbox is now live, so catalog events → `sync_single_product` is the remaining wiring (BUG-BE-11).
- **Notifications** — providers and Celery queue are real; not connected to commerce events (BUG-BE-12).

# Mock / Demo Features (must not face real customers)

- Home page hardcoded products (BUG-FE-09); blog fallback posts (BUG-FE-06); account-dashboard seeded mock orders/wallet/tickets behind real fetches (BUG-FE-04 family); admin kanban/users/reports/pages/settings mocks (BUG-FE-07); gamification `Math.random()` wheel (BUG-FE-08); checkout shipping fallback + static delivery-slot dates (`lib/iranian-commerce.ts:138-181`); the mock payment provider (correctly dev-only and boot-blocked in production).

# Not Testable Due to Missing Infrastructure (this environment)

- Postgres-backed integration suite (`tests/integration/`) — runs in CI with service containers; not executable here.
- Live deployment vs. repository comparison (host `91.107.144.136` not probed).
- Real gateway transactions (Zarinpal/IDPay/NowPayments require merchant credentials + sandbox).
- Load tests (`load_tests/` restored; not executed here — previous reports were removed by the CI-gutting working-tree changes and are recoverable from git history if needed).

# Per-Domain Problem Summary

Condensed; full detail with file:line evidence in `cross-system-bug-matrix.md`.

- **Product/Catalog:** solid; DB is authoritative; ES projection read-only. Gap: no realtime index sync (BUG-BE-11). Duplicate SKUs/barcodes unguarded by DB constraints (P3).
- **Search:** Persian handling verified; no DB fallback by design (safe empty); refresh latency ≤24h pre-outbox-wiring.
- **Pricing:** single server authority at checkout and payment (now enforced end-to-end); frontend display mixes Toman/Rial conventions across files (fragile — P3).
- **Inventory:** locking exemplary; the cancel/expiry lifecycle was the gap (fixed); no DB CHECK constraints (BUG-DB-01).
- **Cart:** server-synced with optimistic UI; `fetchCart` swallows errors silently (P3); two add-to-cart code paths (zustand vs react-query) — the favorites page path does not refresh the header badge (P3).
- **Checkout:** verified; the frontend should stop inventing shipping weights (`1.5`) and display-only fallbacks (BUG-FE-05).
- **Payments:** all five gateways real; Zarinpal/IDPay refunds are manual by design (documented, recorded as APPROVED with admin attestation); crypto needs prod keys + IPN secret to be production-usable.
- **Orders:** state machine strict; snapshots complete; auto-cancel now closes the unpaid-order lifecycle.
- **Wallet:** ledger authoritative; cached `balance` column can drift from ledger sum with only a log warning (P3 — add reconciliation to the scheduled task).
- **Notifications:** real providers, no event wiring (BUG-BE-12).
- **Analytics:** module + daily report real; purchase events must only fire from backend-confirmed states (outbox events now exist to drive this).
- **Authorization:** ownership verified on orders/payments/wallet/addresses; RBAC claims enforced on ~20 admin routers; Casbin wired only to a diagnostic endpoint (dead weight — remove or adopt).
- **Security:** rate limiting sparse (3 routes) and XFF-trusting (BUG-BE-13); access token duplicated in a JS-readable cookie by design (XSS tradeoff — documented in SECURITY_ARCHITECTURE.md); middleware does not verify JWT signatures at the edge (backend enforces — acceptable); CSP allows `unsafe-inline`/`unsafe-eval` (P3).
- **CI/CD:** tests restored; still missing lint gates, Trivy exit-code, ZAP rules file, CI-gated deploys, prod-override filename fix (BUG-INF-02/06).
- **Observability:** metrics + readiness real; no alerting/dashboards (BUG-INF-07).
- **Backups:** Postgres procedure real and documented; no MinIO backup, no scheduler, no restore drill evidence (BUG-INF-08).

# Root Cause Summary

1. **"Feature exists" was treated as "feature works."** Every P0 was a module whose happy path was implemented but whose adversarial path (wrong amount, no debit, replayed webhook, missing page) was not — each was also untested, which is why the gaps survived "green" suites.
2. **Async glue was written but never commissioned.** The outbox, reservation expiry, and notifications were all built to a high standard and then left unscheduled/unwired — integration debt, not implementation debt.
3. **The frontend papered over backend absence with demo data**, which converted infrastructure failures into silent lies (fake products, fake success toasts, fake confirmation steps).
4. **Process failure:** the test suite was deleted to make CI pass, removing the only mechanism that would have caught items 1–3. This was the first thing restored and the suites then drove the fixes.

# Recommended Fix Order

## P0 — done in this audit
Wallet debit; deposit fail-closed; amount/ownership/state validation; verify lock+ownership; IPN fail-closed; simulation blocked in prod; unpaid-order auto-cancel + restock; task scheduling; CI restoration.

## P1 — next
1. Rotate **all** credentials embedded in `scripts/ssh_deploy.py` and purge them from the repo (BUG-INF-05).
2. Fix `deploy.sh` override filename + gate `deploy.yml` on CI success (BUG-INF-02).
3. Remove the PDP fake-fallback pattern (same treatment as the listing) and remaining silent-fallback pages (BUG-FE-03/06).
4. Wire notification handlers to the now-live outbox events (BUG-BE-12).
5. Publish catalog events to the outbox for realtime search sync (BUG-BE-11).

## P2
Rate-limit the write-heavy routes + fix XFF trust; DB CHECK/unique constraints migration (BUG-DB-01); admin mock-first pages (BUG-FE-07); server-authoritative gamification (BUG-FE-08); Trivy/ZAP gates (BUG-INF-06); alert rules + dashboards (BUG-INF-07); MinIO backup + scheduling + restore drill (BUG-INF-08); dev compose binding/weak defaults (BUG-INF-04); guest checkout decision.

## P3
Nginx prod config `${DOMAIN}` substitution + `/healthz` location; wallet `balance` reconciliation task; unify Toman/Rial formatting into one util; consolidate the two add-to-cart paths; invoice token out of query string; CSP tightening; delete the dead `$RV/$RB` flush in `providers.tsx` and the unused `evaluateCoupon` mock engine; node version alignment (CI 22 vs Docker 20); dev deps out of the backend runtime image.

# Final Scorecard (0–10)

| Dimension | Before | After | Remaining gap to 10 |
|---|---|---|---|
| Product Integration | 6 | **8.5** | catalog event → search sync, notifications wiring |
| Catalog / Product Model / Variants | 8 | 8.5 | uniqueness constraints, PDP fallback removal |
| Search | 6.5 | 7.5 | realtime sync, no tests |
| Pricing | 7 | **9** | Toman/Rial consolidation; amount validation now enforced |
| Promotions / Coupons | 8 | 8.5 | DB-level uniqueness |
| Inventory | 7 | **9** | CHECK constraints; return-restock verification |
| Cart | 7.5 | 8 | guest merge story, silent error handling |
| Checkout | 7.5 | **9** | e2e test coverage; shipping-quote honesty |
| Orders | 7 | **9** | unpaid-order e2e test; invoice token |
| Payments | 3 | **8.5** | live gateway verification; crypto config; Zarinpal/IDPay refund automation is out of scope (manual by design) |
| Wallet | 3 | **9** | balance reconciliation task |
| Refunds | 7 | 8.5 | gateway-automated refunds (Iranian gateways are manual) |
| Returns | 7.5 | 7.5 | restock-on-return verification |
| Shipping | 7 | 7.5 | frontend quote fallback |
| Fulfillment | 7 | 8 | carrier sandbox verification |
| ERP | 4 | 4.5 | invoices only; no external ERP |
| CRM | 2 | 2 | not present |
| B2B | n/a | n/a | not present in code |
| AI | 1 | 1 | no module exists (claims aspirational) |
| Notifications | 4 | 5.5 | event wiring (P1) |
| Analytics | 5.5 | 6.5 | backend-driven purchase events |
| Frontend | 6 | **8** | remove remaining mocks/fallbacks |
| Backend | 7.5 | **9** | rate-limit coverage, notifications |
| API | 7.5 | 8 | contract-type cleanup (types/index.ts vs services.ts) |
| Database | 7 | 7.5 | CHECK/unique defense-in-depth |
| Security | 7 | **8** | credential rotation, rate-limit coverage, reuse detection |
| Privacy | 7.5 | 7.5 | solid masking; data-retention policy absent |
| Performance | 7 | 7.5 | load tests restored but not re-run here |
| Mobile | 7 | 7 | responsive verified in code; device-lab pass outstanding |
| Accessibility | 6.5 | 7 | contrast/token fixes landed; full audit outstanding |
| Testing | 2 | **7** | e2e journey tests; integration suite locally; coverage gates |
| Observability | 5 | 5.5 | alerting/dashboards |
| CI/CD | 1 | **7.5** | lint gate, security-gate exit codes, CI-gated deploys |
| Internationalization | 8 | 8 | single date/currency util |
| SEO | 7 | 7 | sitemap/robots real; hardcoded IP fallback |
| Architecture | 8 | **8.5** | outbox now commissioned |
| **Production Readiness** | **3** | **6.5** | see verdict |

# Production Readiness Verdict

**YELLOW** — up from RED as found.

The commerce core (money flow, inventory integrity, order lifecycle, auth, webhooks) is now fail-closed, race-safe, and regression-tested — the blocking P0s that made the platform unsafe for real money are fixed and verified. The platform is **operational for a controlled launch** once the P1 items are completed, in particular: **credential rotation** (`scripts/ssh_deploy.py`), **CI-gated deployment with the prod compose overrides actually applied**, and **transactional notifications**. A GREEN verdict additionally requires the P2 hardening set (DB constraints, alerting, backup drills, admin-page honesty), a run of the restored load tests against a real deployment, and the deployment-vs-repository comparison that was not testable from this environment.

**Evidence discipline note:** every "FIXED" claim above is backed by a named regression test in `backend/tests/unit/test_payment_hardening.py` or by the frontend typecheck/vitest/build runs; every "OPEN" claim is backed by file:line evidence in `cross-system-bug-matrix.md`. Nothing is marked working without evidence, and nothing was fixed by weakening validation, suppressing errors, or mocking success.
