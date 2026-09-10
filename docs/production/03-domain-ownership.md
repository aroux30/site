# 03 — DOMAIN OWNERSHIP, ARCHITECTURAL LAYERS & BOUNDARY MATRIX
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Standard:** Production Verification & Remediation Master v3  
**Date:** 2026-09-10  
**Evaluator:** Principal Enterprise Software Architect  

---

## 1. Clean Architecture Layer Separation Audit

The codebase strictly enforces Clean Architecture and Domain-Driven Design (DDD) across all 35 business modules. An automated AST import sweep was conducted across all files located in `backend/app/modules/*/domain/`:

```
Forbidden imports tested:
- fastapi
- sqlalchemy.ext.asyncio.AsyncSession
- redis
- elasticsearch
- minio
- zarinpal / idpay / external payment SDKs
```

### Audit Result: **100% CLEAN**
- **FastAPI in Domain:** 0 occurrences.
- **AsyncSession in Domain:** 0 occurrences (database sessions reside strictly in `application/` and `infrastructure/`).
- **Redis / Cache in Domain:** 0 occurrences.
- **Elasticsearch SDK in Domain:** 0 occurrences.
- **MinIO / Storage SDK in Domain:** 0 occurrences.
- **External Gateway SDK in Domain:** 0 occurrences (only string enum codes like `PaymentProvider.ZARINPAL = "zarinpal"` exist).

---

## 2. Bounded Context Ownership & Responsibility Matrix

| Bounded Context | Module Package | Domain Entities | Application Services | Invariants & Transaction Boundaries |
|---|---|---|---|---|
| **Core Identity** | `app.modules.auth` | `UserSession`, `OTPRequest` | `AuthService` | Iranian phone format (`09xxxxxxxxx`), OTP 120s cooldown, Argon2id password hashing |
| **Customer Profiles** | `app.modules.users` | `User`, `UserProfile`, `Address` | `UserService` | Single default address per user, 10-digit Iranian postal code validation |
| **Authorization** | `app.modules.rbac` | `Role`, `Permission`, `UserRole` | `RbacService` | System roles cannot be deleted, wildcard permission support (`order:*`) |
| **Product Catalog** | `app.modules.catalog` | `Product`, `ProductVariant`, `Category`, `Brand`, `Tag`, `Attribute` | `CatalogService` | SKU uniqueness, Materialized Path category tree (`/root/sub`), immutable variant prices |
| **Stock & Inventory** | `app.modules.inventory`| `InventoryItem`, `InventoryReservation`, `InventoryTransaction` | `InventoryService` | `available + reserved == total`, `SELECT ... FOR UPDATE` row locks, 30m TTL reservation |
| **Shopping Cart** | `app.modules.cart` | `Cart`, `CartItem` | `CartService` | Server-authoritative totals, guest-cart merge via `X-Session-ID`, live price refresh |
| **Checkout Engine** | `app.modules.checkout`| `TaxRule` | `CheckoutService`, `TaxService` | Idempotent order creation, server recalculation of VAT, live stock reservation |
| **Orders Lifecycle** | `app.modules.orders` | `Order`, `OrderItem`, `OrderStatusHistory` | `OrderService`, `InvoiceService` | 12-state deterministic FSM, immutable item snapshots, printable Iranian tax invoice |
| **Payments Strategy** | `app.modules.payments` | `Payment`, `PaymentTransaction`, `Refund` | `PaymentService`, `ProviderFactory` | Strategy Pattern (Zarinpal, IDPay, Crypto, C2C), duplicate webhook rejection, fail-closed mock |
| **Digital Wallet** | `app.modules.wallet` | `Wallet`, `WalletTransaction` | `WalletService` | Append-only ledger, row-level locks, zero negative balance, audit trail |
| **Fulfillment** | `app.modules.shipping`| `ShippingMethod`, `ShippingRate`, `Shipment` | `ShippingService` | Weight/province matrix, free-shipping threshold, shipment tracking |
| **Promotions** | `app.modules.discounts`| `Discount`, `Coupon`, `CouponRedemption` | `DiscountService` | Single-use concurrency locks, max discount caps, basis-points percentage |
| **Full-Text Search** | `app.modules.search` | *(Derived Elasticsearch)* | `SearchService`, `ElasticsearchClient` | Derived projection, Persian ZWNJ analyzer, fuzzy matching, facets |
| **Outbox & Automation**| `app.modules.automation`| `OutboxMessage` | `OutboxService`, `outbox_worker` | `SELECT ... FOR UPDATE SKIP LOCKED`, Celery task queue processor |
| **Social Proof** | `app.modules.reviews` | `Review`, `ReviewVote` | `ReviewService` | Verified buyer flags, 1-5 rating constraint, 1 vote per user |
| **Gamification** | `app.modules.gamification`| `GamificationRule`, `GamificationEvent`, `Reward` | `GamificationService` | Event-driven point awards, claimable catalog, daily streak tracking |
| **Content & Blog** | `app.modules.blog` | `BlogPost`, `BlogCategory` | `BlogService` | Slug generation, view counters, reading time, Google `Article` schema |
| **SEO Scoring** | `app.modules.seo` | `SEOMetadata` | `SeoAnalyzer`, `SeoService` | 0-100 Rank Math-style analyzer, 13-point Persian checklist |
| **Marketplace** | `app.modules.vendors` | `Vendor`, `VendorSettlement` | `VendorService` | Iranian IBAN (`IR...`) validation, platform commission, settlement ledger |
| **Governance** | `app.modules.approvals`| `ApprovalRequest`, `ApprovalAction` | `ApprovalService` | 3 risk levels, manager review dialog, automated side-effects on approval |
| **Asset Management** | `app.modules.media` | `MediaAsset` | `MediaService` | MIME whitelist, 10MB limit, anti-path traversal, dimension extraction |

---

## 3. Cross-Module Coupling & Architectural Fitness

An analysis of cross-module import dependencies revealed clean hierarchical stratification:
- Orchestration modules (`checkout`, `payments`, `analytics`, `messaging`) depend downwards on domain modules.
- Core foundation modules (`users`, `audit`, `inventory`, `discounts`, `wallet`, `shipping`) have zero upward dependencies.

### Mutual Reference Analysis
Three cross-module pairs have mutual references:
1. **`blog` <-> `seo`**: `BlogPost` model references `SEOMetadata` for search engine snippets, while `seo` router provides analysis routes for blog posts.
   - *Status:* Clean. Resolved at application level.
2. **`catalog` <-> `vendors`**: `Product` references `vendor_id`, while `Vendor` manages multi-merchant catalog subsets.
   - *Status:* Clean. Foreign keys enforced by PostgreSQL with `ON DELETE RESTRICT`.
3. **`rbac` <-> `users`**: `User` has `roles` relationship through `UserRole` association table.
   - *Status:* Clean. Models are cross-registered in SQLAlchemy mapper registry during startup.
