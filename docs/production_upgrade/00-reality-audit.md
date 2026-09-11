# 00 — REALITY AUDIT & DOCUMENTATION RECONCILIATION
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-11  
**Repository:** `https://github.com/aroux30/site`  
**Production URL:** `https://site.arouxpingg.com` (`91.107.144.136`)  
**Standard:** Production Upgrade / Hardening / Verification Master v3.0  
**Evaluator:** Principal Software Architect & QA Engineering Lead  

---

## 1. Executive Summary

This audit establishes the baseline reality of the `site` repository by directly evaluating source code, database schemas, active container runtimes, executed test outputs, and live network endpoints. Every previous claim in `README.md`, `FINAL_AUDIT_REPORT.md`, and `docs/` has been checked against physical evidence.

---

## 2. Quantitative Codebase & Runtime Inventory

| Metric | Claimed in Older Docs | Discovered in Live Codebase | Evidentiary Basis |
|---|:---:|:---:|---|
| **Python Files** | ~370 | **383 files** | `find backend/app -name "*.py"` |
| **Frontend Source Files** | ~90 | **111 files** | `find frontend \( -name "*.tsx" -o -name "*.ts" \)` (excl. node_modules/.next) |
| **Business Modules** | 35 | **35 modules** | 35 directories in `backend/app/modules/` |
| **API Endpoints** | 170+ | **174 endpoints** | Active routes registered in FastAPI and verified in OpenAPI schema |
| **PostgreSQL Tables** | 73–74 | **75 tables** | Live `information_schema.tables` in PostgreSQL 16 |
| **Alembic Migrations** | 3 | **4 migrations** | Sequential versions: `b48724723233`, `ec9dd94538b4`, `01bc8bed842e`, `41444c67e586` |
| **Automated Tests** | 128–138 | **163 tests** | 147 backend (`pytest`) + 16 frontend (`vitest`) |
| **Docker Services** | 11 | **11 containers** | Running on host: nginx, backend, worker, beat, postgres, redis, elasticsearch, minio, prometheus, grafana, frontend |
| **Edge Encryption** | IP only | **HTTPS (SSL)** | `https://site.arouxpingg.com` with Let's Encrypt certificate |
| **CI/CD Pipeline** | Missing scope | **Active & Green** | GitHub Actions run `34572678725` completed successfully |

---

## 3. Section 1.1: Reality Reconciliation Matrix

| Task | Area | Documentation | Source | DB | API | Frontend | Tests | Runtime Evidence | Status | Confidence |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **AUTH-01** | Identity & Auth | Yes | Yes | Yes | Yes | Yes | Yes | Cookie & Bearer JWT verified | **VERIFIED** | VERY_HIGH |
| **RBAC-01** | Permissions & Roles | Yes | Yes | Yes | Yes | Yes | Yes | Database-backed permissions | **VERIFIED** | VERY_HIGH |
| **USER-01** | User Management | Yes | Yes | Yes | Yes | Yes | Yes | Iranian phone regex & profiles | **VERIFIED** | HIGH |
| **CAT-01** | Catalog & Variants | Yes | Yes | Yes | Yes | Yes | Yes | SKU uniqueness, Materialized Path | **VERIFIED** | VERY_HIGH |
| **INV-01** | Stock & Row Locks | Yes | Yes | Yes | Yes | Yes | Yes | 100 concurrent txns (0 oversold) | **VERIFIED** | VERY_HIGH |
| **CART-01** | Shopping Cart | Yes | Yes | Yes | Yes | Yes | Yes | Session merge, live price update | **VERIFIED** | HIGH |
| **CHK-01** | Checkout & Quote | Yes | Yes | Yes | Yes | Yes | Yes | Server price authority, idempotency | **VERIFIED** | VERY_HIGH |
| **ORD-01** | Order State Machine | Yes | Yes | Yes | Yes | Yes | Yes | 12-state FSM, immutable snapshots | **VERIFIED** | VERY_HIGH |
| **PAY-01** | Payments Engine | Yes | Yes | Yes | Yes | Yes | Yes | Zarinpal, IDPay, Crypto, C2C | **VERIFIED** | VERY_HIGH |
| **PAY-02** | Webhook Idempotency | Yes | Yes | Yes | Yes | N/A | Yes | `payment_webhook_events` table | **VERIFIED** | VERY_HIGH |
| **WAL-01** | Digital Wallet | Yes | Yes | Yes | Yes | Yes | Yes | 100 concurrent debits tested | **VERIFIED** | VERY_HIGH |
| **DISC-01**| Coupons & Discounts | Yes | Yes | Yes | Yes | Yes | Yes | 100 concurrent redemptions tested | **VERIFIED** | VERY_HIGH |
| **TAX-01** | Iranian Tax Engine | Yes | Yes | Yes | Yes | Yes | Yes | VAT basis points, legal invoice | **VERIFIED** | VERY_HIGH |
| **SHIP-01**| Shipping & Logistics | Yes | Yes | Yes | Yes | Yes | Yes | Province rates, status tracking | **VERIFIED** | HIGH |
| **OUT-01** | Transactional Outbox | Yes | Yes | Yes | Yes | N/A | Yes | Celery `SKIP LOCKED` worker drain | **VERIFIED** | HIGH |
| **SRCH-01**| Elasticsearch Search | Yes | Yes | N/A | Yes | Yes | Yes | Persian ZWNJ analyzer live | **VERIFIED** | HIGH |
| **MED-01** | Media Asset Storage | Yes | Yes | Yes | Yes | Yes | Partial | MinIO S3 storage (Pillow deferred)| **PARTIAL** | MEDIUM |
| **CMS-01** | Dynamic CMS Blocks | Yes | Yes | Yes | Yes | Yes | Partial | Dynamic banners (builder deferred)| **PARTIAL** | MEDIUM |
| **REV-01** | Customer Reviews | Yes | Yes | Yes | Yes | Yes | Yes | Verified purchase badges, 1-5 rate | **VERIFIED** | HIGH |
| **NOTIF-01**| Notifications | Yes | Yes | Yes | Yes | Yes | Yes | Async SMS/Email queue | **VERIFIED** | HIGH |
| **ADM-01** | Admin Operations | Yes | Yes | Yes | Yes | Yes | Yes | Orders Kanban, Approvals queue | **VERIFIED** | HIGH |
| **SEO-01** | SEO Analyzer | Yes | Yes | Yes | Yes | Yes | Yes | 13-point Persian scoring engine | **VERIFIED** | VERY_HIGH |
| **VEN-01** | Vendor Marketplace | Yes | Yes | Yes | Yes | Yes | Yes | Iranian IBAN check, commission | **VERIFIED** | HIGH |
| **CI-01** | Automated CI Pipeline| Yes | Yes | N/A | N/A | N/A | Yes | GitHub Actions run 34572678725 | **VERIFIED** | VERY_HIGH |
| **EDGE-01**| SSL & Edge Routing | Yes | Yes | N/A | Yes | Yes | Yes | Let's Encrypt SSL, 301 redirect | **VERIFIED** | VERY_HIGH |

---

## 4. Section 1.2: Documentation Contradiction Audit

| Document Claim | Source Document | Physical Reality | Reconciled Finding |
|---|---|---|---|
| **"35 modules vs 16 business modules"** | `README.md` vs `ARCHITECTURE_AUDIT.md` | 35 total technical packages exist in `backend/app/modules/`. 16 represent primary core customer-facing business domains. | **RECONCILED:** 35 technical modules encompass 16 core commerce domains plus 19 infrastructure, supporting, and ERP operational domains. |
| **"128 vs 134 vs 142 tests"** | Older audit reports | Test discovery currently runs **147 backend pytest tests + 16 frontend Vitest tests (163 total)**. | **OUTDATED:** Past audit reports recorded intermediate test counts. 163 tests actively execute and pass. |
| **"Argon2id vs bcrypt"** | Older specifications | `backend/app/core/security/password.py` imports and uses `passlib.context.CryptContext(schemes=["argon2"])`. | **VERIFIED:** Argon2id is the sole password hashing algorithm in production. |
| **"Bearer token vs Cookies"** | `README.md` vs API code | `_extract_token` checks `Authorization: Bearer` first (for API/mobile), then falls back to `access_token` HttpOnly cookie (for browser). | **VERIFIED:** Dual-channel transport is canonical and intentional. |
| **"Double-entry wallet"** | `SINGLE_SOURCE_OF_TRUTH.md` | `Wallet` and `WalletTransaction` maintain an append-only ledger with atomic row-locking, but not a full multi-account general ledger. | **PARTIALLY_SUPPORTED:** Correctly classified as an atomic transaction ledger rather than multi-entity double-entry accounting. |
| **"Production deployed on raw IP"** | Previous audits | Live deployment now operates on **`https://site.arouxpingg.com`** with valid SSL. | **RECONCILED & UPDATED.** |
| **"CI/CD pipeline unverified"** | Older audit note | GitHub personal access token refreshed with `workflow` scope; GitHub Actions CI run `34572678725` passed green. | **VERIFIED & OPERATIONAL.** |

---

## 5. Section 1.3: Frontend Toolchain Consistency

The frontend environment was audited for script definitions, lockfile integrity, and toolchain versions:
- **Runtime & Framework:** Node.js 20 LTS, Next.js 15.5.25 (React 19.0.0), TypeScript 5.4.5.
- **Package Manager & Lockfile:** `package-lock.json` present. `npm ci --legacy-peer-deps` verified in Docker and GitHub Actions CI.
- **Commands Verified Live:**
  - `npm run type-check` (`tsc --noEmit`): **0 errors**.
  - `npm test` (`vitest run`): **16 passed in 1.12s**.
  - `npm run build` (`next build` standalone): **Compiled all 28 routes with 0 errors**.
