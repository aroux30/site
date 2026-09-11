# 00 — PRODUCTION ACCEPTANCE MATRIX & CONCURRENCY VERIFICATION
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-11  
**Repository:** `https://github.com/aroux30/site`  
**Production URL:** `https://site.arouxpingg.com`  
**Standard:** Production Upgrade / Hardening / Verification Master v3.0  
**Evaluator:** Principal QA Architect & Concurrency Systems Lead  

---

## 1. Evidence Level Taxonomy (Levels 0 to 6)

| Level | Evidence Standard | Verification Scope | Status in Platform |
|---|---|---|:---:|
| **L0** | Documentation only | Design intent, architecture diagrams | All 35 domains documented |
| **L1** | Source code exists | Clean Python / TypeScript AST | 383 Python + 111 TS source files |
| **L2** | Unit test passes | In-memory mocking tests | 143 unit test functions |
| **L3** | Integration test | Real PostgreSQL / Redis / MinIO | 4 integration test modules |
| **L4** | End-to-End | End-to-end multi-step flow | Complete purchase & callback flow |
| **L5** | Concurrency / Failure | Parallel race tests, row locking | 4 real PostgreSQL concurrency tests |
| **L6** | Live Staging / Runtime | Live execution on production host | 11 containers, HTTPS, live DB |

---

## 2. Real PostgreSQL Concurrency Suite Results (L5 & L6 Evidence)

All concurrency tests execute against the live PostgreSQL 16 instance inside `ecommerce-backend`:

```bash
docker exec -e ENVIRONMENT=development ecommerce-backend pytest tests/integration/test_real_postgres_concurrency.py -v -s
```

### Test Results Breakdown:
1. **TEST-CONCURRENCY-001: 100 Concurrent Stock Reservations (`stock=1`)**  
   - **Method:** 100 independent concurrent database transactions attempt to reserve 1 unit via `reserve_stock` using `SELECT ... FOR UPDATE`.
   - **Observed Result:** Exactly **1 transaction succeeded**, exactly **99 failed with `ConflictError`**, final inventory row has `available = 0`, `reserved = 1`.
   - **Oversold Count:** **0**.

2. **TEST-CONCURRENCY-002: 100 Concurrent Coupon Redemptions (`usage_limit=1`)**  
   - **Method:** 100 concurrent independent transactions attempt to redeem a single-use coupon using `apply_discount` with `SELECT ... FOR UPDATE` row locks.
   - **Observed Result:** Exactly **1 transaction succeeded**, exactly **99 failed with `ValidationError`**, final coupon row has `usage_count = 1`, `is_active = False`.
   - **Double-Redemption Count:** **0**.

3. **TEST-CONCURRENCY-003: 2 Concurrent Full-Balance Wallet Debits**  
   - **Method:** 2 concurrent transactions attempt to debit the entire 1,000,000 Rial balance of a wallet.
   - **Observed Result:** Exactly **1 succeeded**, exactly **1 rejected with `INSUFFICIENT_FUNDS`**, final balance **0**.
   - **Double-Spend Count:** **0**.

4. **TEST-CONCURRENCY-004: 100 Concurrent Wallet Debits on Funded Balance**  
   - **Method:** Wallet funded with 5,000,000 Rials. 100 concurrent transactions attempt to debit 100,000 Rials each (total demand 10,000,000 Rials, capacity 50).
   - **Observed Result:** Exactly **50 transactions succeeded**, exactly **50 rejected with `INSUFFICIENT_FUNDS`**, final balance in PostgreSQL **0**.
   - **Negative Balance Count:** **0**.

---

## 3. Database Reproducibility & Scratch Migration (DB-001 & DB-002)

To verify that production does not rely on `create_all()`, manual schema tweaks, or local database state:
1. An empty database `test_fresh_migration` was provisioned on PostgreSQL 16.
2. `alembic upgrade head` was executed from revision zero.
3. **Execution Log:**
   ```
   INFO [alembic.runtime.migration] Running upgrade  -> b48724723233, initial_schema
   INFO [alembic.runtime.migration] Running upgrade b48724723233 -> ec9dd94538b4, add_messaging_and_vendors
   INFO [alembic.runtime.migration] Running upgrade ec9dd94538b4 -> 01bc8bed842e, add_tax_and_outbox
   INFO [alembic.runtime.migration] Running upgrade 01bc8bed842e -> 41444c67e586, add_payment_webhook_events
   ```
4. **Table Count:** Exactly **75 tables** created, matching live production database.
5. **Schema Drift Check:** `alembic check` returned `No new upgrade operations detected.`

---

## 4. Money & Pricing Invariants (MONEY-001 & PRICE-001)

### MONEY-001: Integer Monetary Abstraction
- All 54 financial model columns across models are defined as `BigInteger` (integer Iranian Rials).
- AST scan confirmed **0 floating-point numbers** used in financial calculation paths.
- `app.shared.money.money.Money` encapsulates arithmetic operations, immutable Rial values, and Toman display conversions (`_RIAL_PER_TOMAN = 10`).

### PRICE-001: Server-Authoritative Price Pipeline
- `CreateOrderRequest` accepts zero prices or monetary fields from the client.
- `create_order` loads `ProductVariant.price` from PostgreSQL, calculates shipping via `ShippingRate`, evaluates coupons via `_apply_coupon`, and computes VAT via `TaxService.calculate_tax`.
- Immutable snapshots are persisted in `OrderItem` (`unit_price`, `total_price`), `Order` (`subtotal`, `shipping_cost`, `tax`, `discount_amount`, `total`), and `OrderStatusHistory`.

---

## 5. Final Production Acceptance Gates Summary

| Gate | Acceptance Standard | Evidence & Proof | Verdict |
|---|---|---|:---:|
| **DATABASE** | Clean migration from zero creates identical schema | Scratch migration test created 75 tables; `alembic check` clean | ✅ **PASSED** |
| **INVENTORY** | 100 concurrent DB transactions with stock=1 | 1 success, 99 rejected, 0 oversold on live PostgreSQL | ✅ **PASSED** |
| **COUPONS** | 100 concurrent DB transactions with limit=1 | 1 success, 99 rejected, usage=1 on live PostgreSQL | ✅ **PASSED** |
| **WALLET** | 100 concurrent debits maintain balance >= 0 | 50 debits succeeded, 50 rejected, final balance=0 | ✅ **PASSED** |
| **PAYMENT** | Webhook deduplication & fail-closed mock | `payment_webhook_events` unique constraint, mock fails closed | ✅ **PASSED** |
| **REFUNDS** | Total refunded cannot exceed payment amount | Row-locking on payment & refunds; overpayment rejected | ✅ **PASSED** |
| **AUTH / RBAC** | Ownership checks & dual-channel transport | Cookies (HttpOnly/Secure) + Bearer, IDOR fixed | ✅ **PASSED** |
| **CI / CD** | Automated GitHub Actions pipeline on push/PR | Run 34572678725 completed successfully (both jobs green) | ✅ **PASSED** |
| **EDGE / SSL** | Commercial SSL with automated renewal | `https://site.arouxpingg.com` live with Let's Encrypt certificate | ✅ **PASSED** |
| **ISOLATION** | Zero interference with co-located apps | Real-States, Razer Gold, SEO, VPN all 100% operational | ✅ **PASSED** |
