# E-Commerce Integration Matrix — ARoux30 / SITE

> Audit date: 2026-09-11. Every cell reflects verified code behavior (paths in
> `docs/integration-system-map.md`), not documentation claims.
>
> Legend: ✅ integrated & verified · 🟡 partial (works with caveats) · ❌ broken/unwired · 🧪 mocked/demo · ➖ not applicable

| Feature | UI | Frontend State | API | Backend | DB | Search | Inventory | Pricing | Payment | Order | Shipping | Wallet | ERP | CRM | Notifications | Analytics | AI | Tests | Status (post-audit) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Home | 🧪 hardcoded hero products | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ | 🟡 static content; no real data fetch (BUG-FE-09) |
| Catalog / Categories / Brands | ✅ /products real API (fake fallbacks removed this audit) | react-query | `/catalog/*` | catalog_service + repository | ✅ | ES projection | ➖ | ✅ variant prices | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | partial | ✅ integrated |
| Product Detail / Variants | ✅ (fallback removed) | react-query | `/catalog/products/{slug}` | catalog_service | ✅ | ES | ✅ stock display | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | partial | ✅ integrated |
| Search | ✅ header search → /products | URL params | `/search` | search_service (Persian analyzer, ZWNJ, digits) | read-only | ✅ ES | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | search analytics module exists | ➖ | ❌ no tests | 🟡 works; ES-down degrades to empty; index staleness ≤ 24h without outbox-driven sync |
| Filters / Sorting | ✅ | URL params | query params | catalog_service | ✅ | n/a | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ | ✅ integrated |
| Auth (login/OTP/register/refresh) | ✅ | zustand + cookies | `/auth/*` | auth_service (JWT, refresh rotation, sessions) | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ security alerts | ➖ | ➖ | ✅ security suite | ✅ integrated |
| Cart (guest + user) | ✅ | zustand mirror | `/cart` | cart_service + session header | ✅ | ➖ | ➖ | display only | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ concurrency tests (carts) | ✅ integrated |
| Coupons | ✅ apply/remove | display only | `/coupons/*` | discount_service, FOR UPDATE redemption | ✅ | ➖ | ➖ | ✅ server-side at checkout | ➖ | ✅ usage increment | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ coupon race test | ✅ integrated |
| Checkout | ✅ | idempotency key | `/checkout/create-order` | checkout_service (single tx) | ✅ | ➖ | ✅ reserve→confirm | ✅ server recompute (tax/coupon/shipping) | ➖ | ✅ creation | ✅ rate lookup | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ e2e untested (noted) | ✅ integrated (verified line-by-line) |
| Payments — Zarinpal | ✅ redirect | ➖ | `/payments`, `/payments/webhooks/zarinpal` | provider v4 API, verify codes 100/101 | ✅ | ➖ | ➖ | ✅ amount==order.total (fixed) | ✅ | ✅ confirm on verify | ➖ | ➖ | ➖ | ➖ | 🟡 not connected | 🟡 via outbox | ➖ | ✅ factory tests | ✅ integrated (refund = manual by design) |
| Payments — IDPay | ✅ redirect | ➖ | same | provider v1.1 | ✅ | ➖ | ➖ | ✅ amount cross-check (fixed) | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | 🟡 | 🟡 | ➖ | partial | ✅ integrated |
| Payments — Crypto (NowPayments) | ✅ redirect | ➖ | `/payments/webhooks/crypto` | IPN HMAC fail-closed (fixed), simulation blocked in prod (fixed) | ✅ | ➖ | ➖ | ✅ (IRR→USD rate configurable) | ✅ | ✅ | ➖ | 🟡 refund path | ➖ | ➖ | 🟡 | 🟡 | ➖ | ✅ IPN tests | ✅ integrated (needs prod API key + IPN secret) |
| Payments — Card-to-card | ✅ instructions + receipt | ➖ | `/payments/{id}/card-receipt` | admin approve/reject (`payments:manage`) | ✅ | ➖ | ➖ | ✅ | ✅ | ✅ on approval | ➖ | ➖ | ➖ | ➖ | 🟡 | 🟡 | ➖ | ✅ lifecycle tests | ✅ integrated |
| Payments — Wallet | ✅ in-page (fixed) | ➖ | `/payments` + verify | debit inside payment tx (fixed) | ✅ | ➖ | ➖ | ✅ | ✅ | ✅ | ➖ | ✅ ledger | ➖ | ➖ | 🟡 | 🟡 | ➖ | ✅ NEW regression tests | ✅ integrated (was free-order bug) |
| Payment webhooks | ➖ | ➖ | `/payments/webhooks/{provider}` | PaymentWebhookEvent dedup + row locks | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ duplicate-webhook test | ✅ integrated |
| Orders list/detail/cancel | ✅ | display only | `/orders` | order_service (ownership filters) | ✅ | ➖ | ✅ restock on cancel (fixed) | snapshots | ➖ | ✅ state machine | ➖ | ➖ | ➖ | ➖ | 🟡 | 🟡 | ➖ | ✅ state-machine tests | ✅ integrated |
| Unpaid order lifecycle | ➖ | ➖ | ➖ | beat auto-cancel (added) | ✅ | ➖ | ✅ restock (added) | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | 🟡 | ➖ | ➖ | ✅ NEW test | ✅ integrated (was stock-lock leak) |
| Inventory / reservation | ➖ | display only | `/inventory` | FOR UPDATE everywhere | ✅ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ 100-user race test | ✅ integrated |
| Shipping quote + carriers | ✅ (fake fallback for quote remains — BUG-FE-05) | display only | `/shipping/quote` | shipping_service + carrier factory | ✅ | ➖ | ➖ | ✅ server-side rate | ➖ | ➖ | ✅ shipment dispatch + tracking | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ provider tests | 🟡 integrated; frontend quote fallback still fake |
| Returns / RMA | ✅ account UI | ➖ | `/orders/{id}/returns` | returns_service (7-day window) | ✅ | ➖ | ➖ | ➖ | 🟡 refund via payments | ✅ RETURNED | ➖ | 🟡 | ➖ | ➖ | 🟡 | ➖ | ➖ | ✅ lifecycle tests | 🟡 integrated; restock on return completion not verified |
| Refunds | ➖ admin-only | ➖ | `/payments/{id}/refund` | caps + cumulative lock, wallet credit to customer (fixed) | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ REFUNDED | ➖ | ✅ | ➖ | ➖ | 🟡 | 🟡 | ➖ | ✅ double-refund tests | ✅ integrated |
| Wallet (ledger/balance) | ✅ account | display only | `/wallet` | FOR UPDATE, negative-balance prevented | ✅ | ➖ | ➖ | ➖ | ✅ debit at payment | ➖ | ➖ | ✅ | ➖ | ➖ | 🟡 | ➖ | ➖ | ✅ concurrency tests | ✅ integrated (deposit fail-closed in prod) |
| Cashback | 🧪 gamification wheel is client-side | localStorage points | `/cashback` | rules + scheduled crediting | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ credit | ➖ | ➖ | 🟡 | ➖ | ➖ | ❌ | 🟡 backend real; **wheel economy is client-side demo** (BUG-FE-08) |
| Loyalty / Referrals / Gamification | 🟡 /rewards | localStorage | real APIs exist | real services | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | 🟡 | ➖ | ➖ | 🟡 | ➖ | ➖ | partial (restored) | 🟡 backend real; frontend mixes localStorage with API |
| Notifications | ➖ (no preference UI) | ➖ | `/notifications` | providers (Kavenegar/Ghasedak/email/in-app) + Celery queue | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ❌ provider tests absent | 🟡 dispatch works; **not wired to order/payment events** (BUG-BE-12) |
| Analytics | ✅ admin dashboard (mock-first fallback) | — | `/analytics/*` | analytics service + daily report | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ metrics | ➖ | ❌ | 🟡 |
| Recommendations | 🟡 | — | real endpoints | weekly task | ✅ | ES | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ | 🟡 |
| AI commerce | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ NOT PRESENT (no AI module in code) |
| Reviews / Wishlist / Compare | ✅ | zustand (compare) | real APIs | real services | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | partial | ✅ integrated |
| Blog / CMS | ✅ (fallback posts remain) | — | `/blog` | blog service | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ | 🟡 real API; silent fallback posts on error (BUG-FE-06) |
| Support / Messaging | ✅ admin + account tickets | — | `/support`, `/messaging` | real services | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | 🟡 | ➖ | ➖ | ✅ messaging tests | ✅ integrated |
| Vendors / Approvals | ✅ admin UI | — | `/vendors`, `/approvals` | real services, RBAC | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | 🟡 | ➖ | ➖ | ➖ | ➖ | ✅ vendor tests | ✅ integrated (admin UI catch→simulate remains, BUG-FE-07) |
| Admin backoffice | 🟡 | — | mixed | RBAC enforced backend-side | ✅ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | partial | 🟡 several admin pages are mock-first or write to wrong endpoints (BUG-FE-07) |
| ERP / Finance | ➖ | ➖ | invoice PDF/HTML | invoice_service (Jalali) | ✅ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ invoice tests | 🟡 invoices real; full ERP not present (no external ERP integration in code) |
| CRM | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ NOT PRESENT as a distinct system; user/order data in Postgres is the customer record |
| Audit log | ➖ | ➖ | admin audit API | audit service + security audit logging | ✅ | ➖ | ➖ | ➖ | ➖ | ✅ status history | ➖ | ✅ ledger | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ integrated |
| Observability | ➖ | ➖ | `/metrics`, `/readyz`, `/deep-health` | Prometheus middleware | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | partial | 🟡 backend real; no alert rules/dashboards (BUG-INF-07) |
| Security (RBAC, brute force, PII) | ✅ admin guard | token cookie | RequirePermissions on ~20 admin routers | Argon2id, JWT, lockout, masking, IP filter | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ security suites | ✅ integrated (rate limiting on 3 routes only — BUG-BE-13) |

## Journey verification summary

| Journey (audit spec) | Result |
|---|---|
| A — Discovery (home→category→PLP→search→PDP) | 🟡 works on real data (post-fix); home page still static |
| B — Product purchase | ✅ verified end-to-end in code; payment amount + wallet debit fixed; callback page added |
| C — Guest purchase | ❌ **not supported by design** — guest carts exist but checkout requires login (checkout routes `Depends(get_current_user_id)`) |
| D — Authenticated purchase | ✅ |
| E — Multi-item cart | ✅ (server line items, per-item reservation) |
| F — Inventory race | ✅ 100-concurrent reservation test, zero oversell, FOR UPDATE verified |
| G — Payment success / order failure | ✅ single-transaction checkout prevents split state; webhook dedup verified |
| H — Order success / delayed callback | ✅ webhook dedup + verify row-lock (fixed) + idempotent verify; duplicate order impossible (unique idempotency key) |
| I — Refund | ✅ caps + double-refund protection verified; wallet credit targets customer (fixed) |
| J — Return | 🟡 RMA lifecycle tested; restock-on-return-completion not verified |
| K — Cancel | ✅ (now restocks — fixed) |
| L — Wallet | ✅ ledger authoritative; free-money paths closed (fixed) |
| M — Search | 🟡 Persian analysis verified; ES-down → empty (safe); no outbox-driven realtime sync yet (nightly only) |
| N — AI commerce | ➖ no AI module exists in code (prompt claims are aspirational) |
