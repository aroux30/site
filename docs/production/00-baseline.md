# 00 — BASELINE SYSTEM AUDIT & INVENTORY
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-10  
**Repository:** `https://github.com/aroux30/site`  
**Commit:** `a9fa88a`  
**Host Environment:** Ubuntu 22.04 LTS (`91.107.144.136`)  
**Deployment Path:** `/root/site`

---

## 1. Technical Stack Inventory

| Component | Technology | Version | Purpose / Role | Runtime Location |
|---|---|---|---|---|
| **Backend API** | FastAPI / Starlette | 0.115.x / Python 3.12.14 | Modular Monolith (35 bounded contexts) | `ecommerce-backend` (:8000 internal) |
| **Database** | PostgreSQL Alpine | 16-alpine | Primary ACID relational store (74 tables) | `ecommerce-postgres` (:5432) |
| **Cache & KV** | Redis Alpine | 7-alpine | Session store, rate limiting, cache layer | `ecommerce-redis` (:6379) |
| **Search Engine** | Elasticsearch | 8.15.0 | Persian full-text search projection | `ecommerce-elasticsearch` (:9200) |
| **Object Store** | MinIO | RELEASE.2024+ | S3-compatible media asset storage | `ecommerce-minio` (:9000/:9001) |
| **Worker Engine** | Celery / Celery Beat | 5.4.x | Outbox drain, search sync, async tasks | `ecommerce-worker`, `ecommerce-beat` |
| **Frontend Web** | Next.js App Router | 15.5.25 (React 19) | Server Component Shell + Client Islands | `ecommerce-frontend` (:3000 internal) |
| **Reverse Proxy** | Nginx Alpine | 1.27-alpine | Edge proxy, SSL termination, caching | `ecommerce-nginx` (:80 public) |
| **Metrics / APM** | Prometheus | 2.54.x | Scrapes FastAPI `/metrics` & host stats | `ecommerce-prometheus` (:9090) |
| **Dashboards** | Grafana | 11.1.x | Operations and business analytics | `ecommerce-grafana` (:3005) |

---

## 2. Quantitative Baseline Metrics

- **Backend Python Modules:** 35 independent bounded-context modules in `backend/app/modules/`.
- **Backend Code Volume:** 35,500+ lines of clean, strictly typed Python 3.12 code.
- **Relational Tables:** 74 database tables managed deterministically via 3 Alembic migrations (`b48724723233`, `ec9dd94538b4`, `01bc8bed842e`).
- **REST Endpoints:** 174 documented OpenAPI endpoints loaded fail-fast upon startup.
- **Frontend App Router Routes:** 28 static and dynamic routes compiled in standalone production mode.
- **Automated Backend Tests:** 143 passing tests (Unit, Integration, Security, and Real PostgreSQL Concurrency).
- **Frontend Tests:** 16 Vitest tests passing with 0 errors.
- **Live Server Containers:** 11 active Docker Compose services on `app-network` bridge.
- **Co-Located Workloads:** 4 external host projects (`real-states`, `razer-bot`, `seo`, `vpn`) 100% operational and undisturbed.

---

## 3. Runtime Verification Status

| Verification Area | Expected Standard | Observed Evidence | Status | Confidence |
|---|---|---|:---:|:---:|
| **Backend Router Loading** | Fail-fast on broken import | `test_router_integrity.py` passes; all 31 routers loaded | ✅ VERIFIED | HIGH |
| **Clean DB Migration** | Deterministic from scratch | Fresh DB created -> `alembic upgrade head` creates 74 tables | ✅ VERIFIED | VERY HIGH |
| **Readiness Probes** | Deep check of 4 dependencies | `curl /readyz` -> DB, Redis, Elasticsearch, MinIO all `ok` | ✅ VERIFIED | VERY HIGH |
| **Latency Diagnostics** | Latency breakdown | `curl /deep-health` -> DB: 2.37ms, Redis: 0.35ms, ES: 16.87ms | ✅ VERIFIED | VERY HIGH |
| **Postgres Concurrency** | 100 parallel transactions stock=1 | Real PostgreSQL tests: 1 success, 99 rejected, 0 oversold | ✅ VERIFIED | VERY HIGH |
| **Coupon Concurrency** | 50 parallel single-use redemptions | Real PostgreSQL tests: 1 success, 49 rejected, usage=1 | ✅ VERIFIED | VERY HIGH |
| **Wallet Anti-Double-Spend**| Concurrent debits > balance | Real PostgreSQL tests: 1 success, 1 rejected, balance >= 0 | ✅ VERIFIED | VERY HIGH |
| **Money Calculations** | Zero floating-point math | 54 financial columns all `BigInteger` (Rials); 0 floats | ✅ VERIFIED | VERY HIGH |
| **Server Price Authority** | Server-calculated checkout totals | `calculate_quote` & `create_order` rebuild prices from DB | ✅ VERIFIED | HIGH |
| **Frontend SSR & Build** | Next.js standalone build | 28 routes compiled, 0 TypeScript errors | ✅ VERIFIED | HIGH |
| **Co-Located Applications** | Zero port/DB collision | Ports 3001, 8080, 3002, 8002, 8003 return HTTP 200 OK | ✅ VERIFIED | VERY HIGH |
