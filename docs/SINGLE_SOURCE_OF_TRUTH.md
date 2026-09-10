# SINGLE SOURCE OF TRUTH (SSOT) — CURRENT SYSTEM ARCHITECTURE
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Repository:** [https://github.com/aroux30/site](https://github.com/aroux30/site) (Public)  
**Host IP:** `http://91.107.144.136`  
**Last Verified Date:** 2026-09-10  
**Status:** FULLY VERIFIED, HARDENED & PRODUCTION-READY  

---

## 1. Authoritative Technical Inventory

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Backend Framework** | FastAPI | 0.115.x | High-concurrency async REST API, OpenAPI docs |
| **ORM / Database Driver** | SQLAlchemy (async) + asyncpg | 2.0.x | Async PostgreSQL queries, connection pooling |
| **Primary Database** | PostgreSQL | 16 (Alpine) | Canonical ACID relational store (75 tables) |
| **In-Memory Cache / Broker**| Redis | 7 (Alpine) | Session cache, rate limiting, Celery broker |
| **Background Task Workers** | Celery + Celery Beat | 5.4.x | 8 periodic & asynchronous scheduled jobs |
| **Full-Text Search Engine** | Elasticsearch | 8.15.0 | Derived search projection with Persian ZWNJ analyzer |
| **Object Storage** | MinIO | RELEASE.2024+ | S3-compatible media assets & product photo bucket |
| **Reverse Proxy & Web Server**| Nginx | 1.27 (Alpine) | HTTP/2, reverse proxy, gzip, SSL, rate-limiting |
| **Frontend Framework** | Next.js App Router | 15.5.25 | SSR Server Components, Client Islands, standalone |
| **UI Library & Styling** | Tailwind CSS + shadcn/ui | 3.4.x / Radix | RTL-first Persian design system, Vazirmatn font |
| **Client State Management** | Zustand + TanStack Query | v5 | Local/persistent stores & query cache with mutations |
| **Observability Stack** | Prometheus + Grafana | Latest | Scrapes `/metrics`, Prometheus port 9090, Grafana 3005 |
| **Containerization** | Docker Compose | v2.26+ | 11 orchestration services on `app-network` bridge |

---

## 2. Complete Module Map (Authoritative List: 35 Modules)

Every module listed below is strictly organized under `backend/app/modules/{module_name}/` adhering to Clean Architecture with layers `domain/`, `schemas/`, `application/`, `infrastructure/`, and `api/`:

| # | Module | Category | Primary Responsibility |
|---|---|---|---|
| 1 | `auth` | Core Identity | Mobile-first registration, OTP cooldown, Argon2id passwords, HttpOnly Secure cookies, refresh token rotation |
| 2 | `users` | Core Identity | Customer profile, addresses book with 10-digit postal codes, default delivery address toggle |
| 3 | `rbac` | Security | Role-Based Access Control, granular resource-action permissions, custom roles, `RequirePermissions` |
| 4 | `audit` | Security | Immutable security event logging (actor, action, resource, IP, user-agent, before/after snapshots) |
| 5 | `catalog` | Commerce | Simple & variable products, SKU/barcode uniqueness, Materialized Path category tree, brands, attributes |
| 6 | `inventory` | Commerce | Multi-state stock (`available`, `reserved`, `committed`, `damaged`), TTL reservation, `SELECT ... FOR UPDATE` |
| 7 | `cart` | Commerce | Guest cart via `X-Session-ID` header, authenticated server cart, instant login merge, stock/price revalidation |
| 8 | `checkout` | Commerce | 4-step idempotent checkout flow, automatic shipping & tax calculation, coupon validation, Idempotency-Key |
| 9 | `orders` | Commerce | 12-state deterministic finite state machine, status timeline history, printable official Iranian tax invoice |
| 10 | `payments` | Commerce | Strategy Pattern: Zarinpal, IDPay, NowPayments (USDT/Crypto), Card-to-Card with receipt upload, Mock, Wallet |
| 11 | `wallet` | Finance | Double-entry ledger-based digital wallet with row-level locks, zero floating point math, no double-spending |
| 12 | `shipping` | Fulfillment | Rate calculator by weight and province, methods (Pishtaz, Tipax, Express), shipment creation and tracking |
| 13 | `discounts` | Promotion | Rule-based engine (fixed, percentage basis-points), coupon codes, usage limits, concurrency-safe redemption |
| 14 | `reviews` | Social Proof | Verified-buyer reviews, 1-5 star ratings, pros/cons list, community voting on review helpfulness |
| 15 | `wishlist` | Engagement | Customer saved items, toggle endpoint, cross-device sync |
| 16 | `referrals` | Growth | Two-tier referral program with unique user invite links, commission calculations, and ledger credit |
| 17 | `cashback` | Growth | Rule-based cashback allocation on completed orders with automated digital wallet deposit |
| 18 | `loyalty` | Retention | Points earning & redemption program with 4 tier ranks (Bronze, Silver, Gold, Platinum) |
| 19 | `gamification`| Retention | Points for customer events, claimable reward catalog, daily streak calendar, animated Wheel of Fortune |
| 20 | `notifications`| Messaging | Multi-channel notifications (In-App, SMS, Email) with template variable substitution |
| 21 | `messaging` | Marketing | Broadcast campaigns, A/B testing (50/50 split), dynamic audience segmentation (5 segments) |
| 22 | `support` | Service | Customer support ticketing system with priority levels, department assignment, threaded messages |
| 23 | `blog` | Content | Technology magazine and buying guides, reading time, view counters, Google `Article` JSON-LD schema |
| 24 | `seo` | Discoverability| Metadata management, dynamic `sitemap.xml`, `robots.txt`, automated 0-100 Rank Math-style SEO scoring engine |
| 25 | `search` | Discoverability| Elasticsearch 8.15 integration with Persian ZWNJ analyzer, fuzzy matching, facets, autocomplete |
| 26 | `analytics` | Intelligence | Client event tracking, sales/order/product/customer reporting, KPI aggregation |
| 27 | `recommendations`| Intelligence| Trending products feed (14-day window), similar products algorithm, frequently bought together |
| 28 | `approvals` | Governance | Human approval queue for sensitive actions (price changes, large refunds, product publishing) with side-effects |
| 29 | `media` | Assets | Upload service with MIME validation, 10MB limit, path traversal prevention, image dimension extraction |
| 30 | `vendors` | Marketplace | Multi-vendor registration, commission rate management, bank IBAN (`IR...`) validation, settlements ledger |
| 31 | `settings` | Core Config | Dynamic key-value site settings store with JSONB values and public exposure control |
| 32 | `automation` | Core Async | Celery periodic task orchestrator and transactional outbox queue processor |
| 33 | `content` | CMS | Structured CMS content blocks and promotional banners |
| 34 | `integrations`| Extensibility | External webhooks and third-party API adapter interfaces |
| 35 | `shared` | Shared Kernel| Canonical `Money` (integer Rials), UUID generators, cursor/offset pagination, `OutboxMessage` models |

---

## 3. Verified Metrics & Health Status

- **Automated Pytest Tests:** 138 passing tests (`pytest tests -v` exit code: 0)
- **Automated Vitest Tests:** 16 passing frontend tests (`npm test` exit code: 0)
- **Documented OpenAPI Endpoints:** 174 endpoints documented in Swagger UI (`/docs`)
- **Total PostgreSQL Tables:** 75 tables managed by Alembic migrations
- **Liveness Probe:** `GET /healthz` -> `{"status":"ok","app":"iranian-ecommerce"}`
- **Readiness Probe:** `GET /readyz` -> Checks DB, Redis, Elasticsearch, and MinIO storage
- **Deep Health Probe:** `GET /deep-health` -> Returns dependency latencies (DB ~40ms, Redis ~1ms, ES ~14ms, MinIO ~9ms)
- **Frontend Pages:** 28 static & dynamic routes compiled in standalone production mode (0 TypeScript errors)
