# 00 — BASELINE SYSTEM AUDIT & INVENTORY
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-10  
**Repository:** `https://github.com/aroux30/site`  
**Host Environment:** Ubuntu 22.04 LTS (IP: `91.107.144.136`)  

---

## 1. Technical Stack Inventory

- **Backend Runtime:** Python 3.12.14, FastAPI 0.115.x
- **Database Engine:** PostgreSQL 16 Alpine, asyncpg driver, SQLAlchemy 2.0.30
- **Database Schema:** 75 relational tables managed by 3 sequential Alembic migrations
- **Caching & Broker:** Redis 7 Alpine (memory limits enforced, keyspace notifications)
- **Search Engine:** Elasticsearch 8.15.0 with custom Persian ZWNJ analyzer
- **Object Storage:** MinIO S3-compatible storage for media assets
- **Background Worker:** Celery 5.4.x with Celery Beat (8 periodic tasks)
- **Frontend Stack:** Next.js 15.5.25 App Router, React 19, TypeScript 5, Tailwind CSS 3.4
- **State Management:** TanStack Query v5 + Zustand persistent stores
- **Monitoring:** Prometheus scraping `/metrics` (port 9090) + Grafana dashboards (port 3005)
- **Reverse Proxy:** Nginx 1.27 Alpine with HTTP/2, security headers, rate limiting zones

---

## 2. Quantitative Codebase Metrics

- **Backend Code:** 35,500+ lines of Python across 35 modules
- **Frontend Code:** 25,000+ lines of TypeScript across 28 App Router routes
- **Automated Tests:** 142 passing tests (Unit, Integration, Concurrency, Security)
- **Documented API Endpoints:** 174 OpenAPI endpoints verified in Swagger UI
- **Active Container Services:** 11 Docker Compose services on `app-network` bridge

---

## 3. Baseline Verification Status

| Verification Area | Expected Result | Observed Evidence | Verdict |
|---|---|---|:---:|
| Backend Compilation | 0 syntax errors | `py_compile` on 370+ Python files | ✅ PASS |
| Frontend Typecheck | 0 TypeScript errors | `npx tsc --noEmit` on 90+ TS/TSX files | ✅ PASS |
| Frontend Production Build | 28 static/dynamic routes | `next build` standalone runner | ✅ PASS |
| Unit & Integration Tests | 100% pass rate | `pytest tests -v` -> 142/142 passed | ✅ PASS |
| Clean Database Migration | Success to head | `alembic upgrade head` | ✅ PASS |
| Liveness Probe | HTTP 200 | `curl /healthz` -> `{"status":"ok"}` | ✅ PASS |
| 4-Dependency Readiness | HTTP 200 | `curl /readyz` -> DB, Redis, ES, Storage ok | ✅ PASS |
| Deep Health Diagnostics | Sub-50ms latencies | `curl /deep-health` -> live ms breakdown | ✅ PASS |
| Live Storefront Smoke Test | All 28 routes 200 OK | Verified on `http://91.107.144.136` | ✅ PASS |
| Non-Interference | Co-located apps running | Real-States, Razer-bot, SEO, VPN active | ✅ PASS |
