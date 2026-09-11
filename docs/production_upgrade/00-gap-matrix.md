# 00 — PRODUCTION GAP MATRIX & RISK CLASSIFICATION
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-11  
**Repository:** `https://github.com/aroux30/site`  
**Standard:** Production Upgrade / Hardening / Verification Master v3.0  
**Evaluator:** Principal Software Architect & Lead Security Engineer  

---

## 1. Architectural Reconciliation (ARCH-003 & ARCH-004)

### ARCH-003: Model vs Alembic Migration Reconciliation
A complete comparison of the SQLAlchemy 2.x Declarative Base metadata against the Alembic migration history was performed on the live PostgreSQL 16 database:
- **Sequential Migrations:**
  1. `b48724723233_initial_schema.py` (Base tables: users, catalog, orders, payments, cart, inventory, etc.)
  2. `ec9dd94538b4_add_messaging_and_vendors.py` (Vendors, messaging campaigns, ab-tests)
  3. `01bc8bed842e_add_tax_and_outbox.py` (Tax rules, outbox messages)
  4. `41444c67e586_add_payment_webhook_events.py` (Payment webhook event deduplication table)
- **Alembic Check Command:** `docker exec ecommerce-backend alembic check`
- **Output:** `No new upgrade operations detected.`
- **Schema Parity:** **100% CONVERGED** (75 tables, all foreign keys, unique constraints, and indexes aligned).

### ARCH-004: Duplicate & Legacy Architecture Audit
- **Authentication:** Unified under `app.modules.auth` (Argon2id + JWT). No secondary authentication systems exist.
- **Permission System:** Unified under `app.modules.rbac` with database-persisted roles, permissions, and `RequirePermissions` FastAPI dependency. No JSON-only permission bypasses.
- **Monetary Logic:** Unified under `app.shared.money.money.Money` and database integer Rials (`BigInteger`). No parallel floating-point modules exist.
- **Dead / Unused Files:** No legacy v1/v2 duplicate models or directories discovered.

---

## 2. Comprehensive Domain Gap Analysis

| Domain | Implemented Baseline | Target Production Requirement | Gap Description | Severity | Remediated in v3.0 Pass? |
|---|---|---|---|:---:|:---:|
| **Payments** | Gateway strategy pattern (Zarinpal, IDPay, C2C) | Signature verification, fail-closed mock, idempotent webhooks | C2C `-APPROVED` backdoor closed; Webhook table created; Order status transition added | **P0** | **YES (Fixed)** |
| **Inventory** | `with_for_update()` locking | Zero oversell under 100 concurrent DB transactions | Concurrency proven via real 100-txn PostgreSQL test | **P0** | **YES (Verified)** |
| **Security / IDOR**| `RequirePermissions` on admin | Server-enforced object ownership on user endpoints | Payment details & receipt submission IDOR patched | **P0** | **YES (Fixed)** |
| **Edge / SSL** | Raw IP on port 80 | Valid commercial SSL on FQDN | `site.arouxpingg.com` live with Let's Encrypt SSL | **P0** | **YES (Resolved)** |
| **CI / CD** | Directory git-ignored | Automated CI pipeline on push/PR | Token scopes updated; GitHub Actions CI passed green | **P1** | **YES (Resolved)** |
| **Discounts** | Coupon rules with lock | 100 concurrent redemptions of single-use coupon | Upgraded concurrency test from 50 to 100 txns | **P1** | **YES (Verified)** |
| **Wallet** | Atomic row-locking ledger | 100 concurrent debits preserving balance invariants | Added 100-txn concurrent wallet debit test | **P1** | **YES (Verified)** |
| **Load Testing** | 100-txn DB concurrency test | 10,000 concurrent user Locust stress test | Implemented modular distributed Locust suite (`load_tests/`) & capacity tuning | **P1** | **YES (Implemented)** |
| **Docker Probes** | `|| exit 0` fallbacks | Genuine healthcheck reporting real process state | Replaced with `celery status` & native `/proc` probes | **P1** | **YES (Fixed)** |
| **MinIO Storage** | Host port 9000 exposed | S3 storage isolated to internal Docker network | Removed host port mapping from `docker-compose.prod.yml` | **P1** | **YES (Fixed)** |
| **Media Assets** | Direct S3 upload with MIME check | Asynchronous WebP thumbnailing via Celery worker | Pillow background resizing pipeline is deferred | **P1** | **PARTIAL (Tracked)** |
| **CMS** | Dynamic banner blocks & settings | Visual drag-and-drop page block builder | Deferred in favor of structured Next.js components | **P2** | **PARTIAL (Tracked)** |
| **Commercial Keys**| Sandbox credentials | Live Iranian merchant IDs (Zarinpal / Kavenegar) | Requires human merchant activation with bank | **P1** | **PENDING USER** |

---

## 3. Prioritized Issue Classification (P0 / P1 / P2)

### Priority P0: Production Blockers (STOP-THE-LINE)
*Criteria: Financial corruption, fake payment success, inventory oversell, unauthorized access, schema drift.*
1. **[RESOLVED]** C2C payment auto-approval backdoor in `card_to_card.py` (Fixed in `2ac2ec4`).
2. **[RESOLVED]** Orphaned order state upon payment verification in `payment_service.py` (Fixed in `2ac2ec4`).
3. **[RESOLVED]** IDOR vulnerability on `GET /payments/{id}` and receipt submission (Fixed in `eb12553`).
4. **[RESOLVED]** Missing database webhook event deduplication table and row locks (Fixed in `a20ed09`).
5. **[RESOLVED]** Unlocked concurrent refund overpayment risk (Fixed in `a20ed09`).
6. **[RESOLVED]** Production settings validator crashing on missing attribute (Fixed in `2ac2ec4`).
7. **[RESOLVED]** Scratch database migration and schema convergence (Verified in `01bc8bed842e` & `41444c67e586`).

### Priority P1: Major Quality & Operational Reliability
*Criteria: CI/CD automation, edge security, search consistency, crash recovery, health probes.*
1. **[RESOLVED]** GitHub Actions CI pipeline execution blocked by token scope (Resolved via OAuth refresh; CI green).
2. **[RESOLVED]** Absence of commercial SSL/TLS certificate for payment callbacks (Resolved via `site.arouxpingg.com`).
3. **[RESOLVED]** Cheating `|| exit 0` container healthchecks in Celery worker/beat (Fixed in `d7af81d`).
4. **[RESOLVED]** MinIO port 9000 exposed to public host network (Fixed in `d7af81d`).
5. **[TRACKED]** Asynchronous image resizing pipeline via Celery worker (Direct S3 storage operational).
6. **[PENDING USER]** Live Iranian payment gateway merchant credentials in `.env` (Currently in Sandbox).

### Priority P2: Premium Improvements
*Criteria: Advanced AI recommendations, visual drag-and-drop builders, personalization.*
1. **[TRACKED]** Visual drag-and-drop CMS builder (Managed via structured headless components).
2. **[TRACKED]** Real-time AI recommendations engine (Managed via deterministic rules).
