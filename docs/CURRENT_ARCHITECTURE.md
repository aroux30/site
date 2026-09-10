# CURRENT ARCHITECTURE SPECIFICATION & DOMAIN MAP
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Repository:** [https://github.com/aroux30/site](https://github.com/aroux30/site) (Public)  
**Host IP:** `http://91.107.144.136`  
**Document Type:** Authoritative Architecture Reference (Single Source of Truth)  
**Version:** 2.0.0 (Production Hardened)  
**Date:** 2026-09-10  

---

## 1. Architectural Definitions & Taxonomy

To prevent conflicting terminology across documentation and code, the following precise definitions are established and enforced across the repository:

- **Domain:** A high-level sphere of business knowledge and logic (e.g., Identity, Commerce, Finance, Fulfillment, Marketing, Content).
- **Module:** A self-contained package under `backend/app/modules/{module_name}/` that encapsulates a bounded context following Clean Architecture with strict layer separation (`domain/`, `schemas/`, `application/`, `infrastructure/`, and `api/`).
- **Router:** A FastAPI `APIRouter` instance located in `api/routes.py` that maps HTTP endpoints, performs schema validation, and extracts authentication context without containing business logic.
- **Service:** A pure application or domain service in `application/{module}_service.py` that orchestrates transactions, enforces invariants, manages locking, and emits events.
- **Worker:** A Celery background task defined in `application/tasks.py` that executes asynchronous or scheduled background operations out of band from HTTP request-response cycles.

---

## 2. Global Architecture Topology

```text
                                Internet (Clients: Web & Mobile)
                                                │
                                                ▼
                                    Nginx Reverse Proxy (:80)
                                     /                      \
                                    /                        \
                                   ▼                          ▼
                         Next.js 15 Frontend            FastAPI Backend (:8000)
                         (App Router, SSR,              (35 Modules, 174 Endpoints,
                          Client Islands)                 Fail-Fast Router Loader)
                                                              │
                            ┌─────────────────────────────────┼─────────────────────────────────┐
                            ▼                                 ▼                                 ▼
                     PostgreSQL 16                         Redis 7                       Elasticsearch 8.15
                   (Source of Truth,                  (Cache, Sessions,                  (Derived Projection,
                  75 Normalized Tables,               Celery Task Broker,                Persian ZWNJ Analyzer,
                   Alembic Migrations)                  Key-Value Store)                    Faceted Search)
                            │                                 │
                            └─────────────────┬───────────────┘
                                              ▼
                                     Celery Async Workers
                                      ├── Worker (8 queues)
                                      ├── Beat (7 periodic jobs)
                                      └── Transactional Outbox
```

---

## 3. Subsystem Architecture Specifications

### 3.1 Backend Architecture (FastAPI & Clean Architecture)
- **Framework:** FastAPI 0.115+ running on Python 3.12 with Uvicorn.
- **Lifecycle & Routing:** Fail-Fast router discovery in `backend/app/main.py`. If any registered module fails to load or exports an invalid router, startup raises `RuntimeError` immediately, eliminating partial silent failures.
- **Diagnostics:**
  - `/healthz`: Pure process liveness check (`HTTP 200`).
  - `/readyz`: Verifies 4 core dependencies: PostgreSQL connection, Redis ping, Elasticsearch cluster health, and MinIO storage availability.
  - `/deep-health`: Real-time latency diagnostics for each infrastructure dependency with milliseconds breakdown.
  - `/metrics`: Prometheus metrics scrape endpoint.

### 3.2 Database & Data Architecture (PostgreSQL 16)
- **Driver:** `asyncpg` with asynchronous SQLAlchemy 2.0 engine and session pooling.
- **Schema Volume:** 75 relational tables managed exclusively by sequential Alembic migrations (`2026_09_09_2335-b48724723233_initial_schema.py`, `ec9dd94538b4`, `01bc8bed842e`).
- **Primary Keys:** UUIDv4 primary keys throughout, avoiding integer ID enumeration attacks.
- **Monetary Integrity:** Zero floating-point representation. Every price, subtotal, tax, discount, and wallet balance is stored as a 64-bit integer (`BigInteger` in Rials). Display conversion to Toman (`Toman = Rials // 10`) is computed deterministically.
- **Concurrency & Locking:** `SELECT ... FOR UPDATE` row-level locks applied on inventory reservations and wallet debits, eliminating race conditions and double-spending under high concurrency.
- **Transactional Outbox:** The `outbox_messages` table records domain events atomically within the originating business transaction. Events are claimed by workers using `SELECT ... FOR UPDATE SKIP LOCKED`, guaranteeing at-least-once delivery to Elasticsearch and notification channels without dual-write inconsistency.

### 3.3 Authentication & Authorization
- **Storage:** Short-lived JWT access tokens (30 minutes) + rotating refresh tokens (7 days) delivered exclusively via **HttpOnly Secure SameSite=Lax cookies**. No tokens are accessible to client-side JavaScript, neutralizing XSS credential theft.
- **Password Security:** Argon2id password hashing via passlib (time_cost=4, memory_cost=65536, parallelism=2).
- **Mobile OTP:** Iranian phone normalization (`09xxxxxxxxx`), 6-digit verification codes with 120s expiry, and sliding-window rate-limiting cooldowns.
- **RBAC:** Server-side `RequirePermissions(...)` FastAPI dependency; roles and permissions are embedded into token claims for zero-DB-roundtrip authorization.

### 3.4 Payment & Banking
- **Strategy Pattern:** `PaymentProvider` abstract interface implemented by:
  - `ZarinpalProvider` (زرین‌پال)
  - `IDPayProvider` (آی‌دی‌پی)
  - `NowPaymentsProvider` (Cryptocurrency: USDT TRC20/ERC20, BTC, ETH with HMAC-SHA512 IPN verification)
  - `CardToCardProvider` (Bank transfer with tracking code and receipt upload)
  - `WalletPaymentProvider` (Internal digital wallet debit)
  - `MockPaymentProvider` (Isolated for development/testing)
- **Idempotency:** Payment creation and callbacks enforce unique idempotency keys, preventing duplicate captures or duplicate order fulfillments on retry.

### 3.5 Full-Text Search (Elasticsearch 8.15)
- **Role:** Derived read-projection; PostgreSQL is always the canonical source of truth.
- **Persian Text Chain:**
  - Character filters: Arabic-to-Persian character mapping (`ي` ➔ `ی`, `ك` ➔ `ک`), digit normalization, zero-width non-joiner (ZWNJ) handler.
  - Token filters: Lowercase, Persian stop words removal, Persian stemmer, edge n-gram filter (min 2, max 15) for live autocomplete.
- **Features:** Multi-field boosting (`name^3`, `description`, `tags`), fuzzy matching, category and price range faceted aggregations.

### 3.6 Frontend Architecture (Next.js 15.5 App Router)
- **Rendering Strategy:** Server Components by default. The homepage, catalog, blog, and static pages render on the server, streaming semantic HTML and JSON-LD structured data.
- **Client Islands:** Interactive features (3D Hero scene, interactive countdown timer, product quick-buy card, cart drawer, compare toggle) are isolated into lightweight client islands (`"use client"`), keeping initial page bundle size under 9kB.
- **Mobile-First UX:**
  - Sticky 5-item Mobile Bottom Navigation Bar (`/`, `/products`, `/cart`, `/favorites`, `/account`).
  - Sticky Mobile Add-to-Cart Action Bar on Product Detail Pages.
  - Touch-optimized targets (minimum 44x44px), thumb-friendly navigation, and full RTL layout.
- **State Management:** TanStack Query v5 for server query caching and mutations with automatic invalidation; Zustand for persisted local client stores (Cart, Compare).

---

## 4. Complete Domain & Module Map (35 Modules)

| # | Module Name | Bounded Context | Core Tables | Key Features |
|---|---|---|---|---|
| 1 | `auth` | Identity | `user_sessions`, `otp_requests` | OTP, Argon2id, JWT cookies, token rotation |
| 2 | `users` | Identity | `users`, `user_profiles`, `addresses` | Profile, 10-digit postal code addresses |
| 3 | `rbac` | Identity | `roles`, `permissions`, `role_permissions`, `user_roles` | Granular permission checks, custom roles |
| 4 | `audit` | Governance | `audit_logs` | Security audit trail, before/after JSONB |
| 5 | `catalog` | Commerce | `categories`, `brands`, `products`, `product_variants`, `product_images`, `tags`, `attributes` | Variants, SKU, Materialized Path category tree |
| 6 | `inventory` | Commerce | `inventory_items`, `inventory_reservations`, `inventory_transactions` | Multi-state stock, TTL reservation, atomic locking |
| 7 | `cart` | Commerce | `carts`, `cart_items` | Guest cart `X-Session-ID`, login merge, price validation |
| 8 | `checkout` | Commerce | `tax_rules` | 4-step flow, shipping quotes, Idempotency-Key |
| 9 | `orders` | Commerce | `orders`, `order_items`, `order_status_history` | 12-state FSM, printable official Iranian tax invoice |
| 10 | `payments` | Commerce | `payments`, `payment_transactions`, `refunds` | Zarinpal, IDPay, Crypto USDT, Card-to-Card, Wallet |
| 11 | `wallet` | Finance | `wallets`, `wallet_transactions` | Double-entry ledger, row-level locks, zero float math |
| 12 | `shipping` | Fulfillment | `shipping_methods`, `shipping_rates`, `shipments`, `shipment_items` | Province/weight matrix, Pishtaz, Tipax, tracking |
| 13 | `discounts` | Promotion | `discounts`, `coupons`, `coupon_redemptions` | Fixed/percent basis-points rules, usage limits |
| 14 | `reviews` | Social Proof | `reviews`, `review_votes` | Verified purchase reviews, 1-5 stars, helpful votes |
| 15 | `wishlist` | Engagement | `wishlists`, `wishlist_items` | Customer saved products, toggle API |
| 16 | `referrals` | Growth | `referrals`, `referral_commissions` | Two-tier referral tracking, commission ledger |
| 17 | `cashback` | Growth | `cashback_rules`, `cashback_transactions` | Automated cashback calculation and wallet crediting |
| 18 | `loyalty` | Retention | `loyalty_accounts`, `loyalty_transactions` | Points earning & redemption, 4 loyalty tiers |
| 19 | `gamification` | Retention | `gamification_rules`, `gamification_events`, `rewards` | Points for events, claimable catalog, Wheel of Fortune |
| 20 | `notifications` | Messaging | `notifications`, `notification_templates` | Multi-channel dispatch (In-App, SMS, Email) |
| 21 | `messaging` | Marketing | `broadcast_campaigns`, `broadcast_recipients` | Broadcast campaigns, A/B testing, 5 user segments |
| 22 | `support` | Service | `support_tickets`, `ticket_messages`, `ticket_attachments` | Customer ticketing, priority levels, threaded messages |
| 23 | `blog` | Content | `blog_posts`, `blog_categories` | Technology magazine, reading time, Article JSON-LD |
| 24 | `seo` | Discoverability| `seo_metadata` | Dynamic sitemap, robots, Rank Math 0-100 scoring engine |
| 25 | `search` | Discoverability| *(Derived ES)* | Elasticsearch 8.15, Persian ZWNJ analyzer, autocomplete |
| 26 | `analytics` | Intelligence | `analytics_events`, `daily_metrics` | Event tracking, sales/order/customer reporting |
| 27 | `recommendations`| Intelligence| *(Redis cache)* | 14-day trending products, similar products algorithm |
| 28 | `approvals` | Governance | `approval_requests`, `approval_actions` | Human approval queue with automated side-effects |
| 29 | `media` | Assets | `media_assets` | 10MB limit, MIME validation, anti-traversal, dimensions |
| 30 | `vendors` | Marketplace | `vendors`, `vendor_settlements` | Multi-vendor registration, Iranian IBAN, settlements |
| 31 | `settings` | Configuration | `site_settings` | Dynamic key-value configuration store with JSONB |
| 32 | `automation` | Core Async | `outbox_messages` | Outbox processor, Celery beat scheduled orchestrator |
| 33 | `content` | CMS | *(CMS blocks)* | Structured marketing banners and promotional slots |
| 34 | `integrations`| Extensibility | *(Adapters)* | Third-party webhook interfaces and API adapters |
| 35 | `shared` | Kernel | *(Core types)* | Canonical `Money` (integer Rials), UUIDs, Outbox models |

---

## 5. Deployment & Orchestration Model

- **Primary Orchestration:** Docker Compose on single-node Ubuntu 22.04 LTS (`docker-compose.yml` for development, `docker-compose.prod.yml` for hardened production).
- **Horizontal Scaling Roadmap:**
  - Frontends and Backends are stateless and scale horizontally via `docker compose --scale backend=N --scale frontend=N up -d` behind Nginx upstream load balancers.
  - PostgreSQL, Redis, and Elasticsearch maintain persistent named volumes.
  - Worker concurrency scales via Celery `--concurrency` flags across worker nodes.
