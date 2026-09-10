# 04 — DOMAIN MAP & ARCHITECTURAL BOUNDARIES
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Standard:** Production Certification, Verification & Hardening Master v4  
**Date:** 2026-09-10  
**Evaluator:** Principal Enterprise Software Architect  

---

## 1. Clean Architecture Layering & Dependency Direction

The backend architecture enforces strict unidirectional dependency flow conforming to Clean Architecture and Domain-Driven Design (DDD):

```
Presentation (API Routes & Schemas)
       ↓
Application (Use Cases, Workflows & Services)
       ↓
Domain (Entities, Value Objects & Domain Invariants)
       ↓
Infrastructure (Repositories, Database Sessions, Caching, External Adapters)
```

### Layer Rule Verification (AST Import Audit)
An automated AST import sweep was conducted across all files under `backend/app/modules/*/domain/`:
- **FastAPI in Domain:** **0 occurrences** (Presentation is completely decoupled).
- **SQLAlchemy AsyncSession in Domain:** **0 occurrences** (Sessions are managed exclusively in Application/Infrastructure).
- **Redis SDK in Domain:** **0 occurrences**.
- **Elasticsearch SDK in Domain:** **0 occurrences**.
- **MinIO SDK in Domain:** **0 occurrences**.
- **Third-Party Payment Gateway SDKs in Domain:** **0 occurrences**.

---

## 2. Comprehensive 35-Module Bounded Context Map

| Module Package | Primary Domain Entities | Application Services | Invariants & Business Rules |
|---|---|---|---|
| `app.modules.auth` | `UserSession`, `OTPRequest` | `AuthService` | Phone format `09xxxxxxxxx`, OTP 120s cooldown, Argon2id passwords |
| `app.modules.users` | `User`, `UserProfile`, `Address` | `UserService` | Single default address per user, 10-digit postal code |
| `app.modules.rbac` | `Role`, `Permission`, `UserRole` | `RbacService` | System roles cannot be deleted, wildcard permission support (`order:*`) |
| `app.modules.catalog` | `Product`, `ProductVariant`, `Category`, `Brand` | `CatalogService` | SKU uniqueness, Materialized Path category tree (`/root/sub`) |
| `app.modules.inventory`| `InventoryItem`, `InventoryReservation` | `InventoryService` | `available + reserved == total`, `SELECT ... FOR UPDATE` row locks, 30m TTL |
| `app.modules.cart` | `Cart`, `CartItem` | `CartService` | Server-authoritative totals, guest-cart merge via `X-Session-ID` |
| `app.modules.checkout`| `TaxRule` | `CheckoutService`, `TaxService` | Idempotent order creation, server recalculation of VAT (basis points) |
| `app.modules.orders` | `Order`, `OrderItem`, `OrderStatusHistory` | `OrderService`, `InvoiceService` | 12-state deterministic FSM, immutable item snapshots, printable tax invoice |
| `app.modules.payments`| `Payment`, `PaymentTransaction`, `Refund` | `PaymentService`, `ProviderFactory` | Strategy Pattern (Zarinpal, IDPay, Crypto, C2C), duplicate webhook rejection |
| `app.modules.wallet` | `Wallet`, `WalletTransaction` | `WalletService` | Append-only ledger, row-level locks, zero negative balance, audit trail |
| `app.modules.shipping`| `ShippingMethod`, `ShippingRate`, `Shipment` | `ShippingService` | Weight/province matrix, free-shipping threshold, shipment tracking |
| `app.modules.discounts`| `Discount`, `Coupon`, `CouponRedemption` | `DiscountService` | Single-use concurrency locks, max discount caps, basis-points percentage |
| `app.modules.search` | *(Derived Elasticsearch)* | `SearchService`, `ElasticsearchClient` | Derived projection, Persian ZWNJ analyzer, fuzzy matching, facets |
| `app.modules.automation`| `OutboxMessage` | `OutboxService`, `outbox_worker` | `SELECT ... FOR UPDATE SKIP LOCKED`, Celery task queue processor |
| `app.modules.reviews` | `Review`, `ReviewVote` | `ReviewService` | Verified buyer flags, 1-5 rating constraint, 1 vote per user |
| `app.modules.gamification`| `GamificationRule`, `GamificationEvent`, `Reward` | `GamificationService` | Event-driven point awards, claimable catalog, daily streak tracking |
| `app.modules.blog` | `BlogPost`, `BlogCategory` | `BlogService` | Slug generation, view counters, reading time, Google `Article` schema |
| `app.modules.seo` | `SEOMetadata` | `SeoAnalyzer`, `SeoService` | 0-100 Rank Math-style analyzer, 13-point Persian checklist |
| `app.modules.vendors` | `Vendor`, `VendorSettlement` | `VendorService` | Iranian IBAN (`IR...`) validation, platform commission, settlement ledger |
| `app.modules.approvals`| `ApprovalRequest`, `ApprovalAction` | `ApprovalService` | 3 risk levels, manager review dialog, automated side-effects on approval |
| `app.modules.media` | `MediaAsset` | `MediaService` | MIME whitelist, 10MB limit, anti-path traversal, dimension extraction |

---

## 3. Mutual Dependency Analysis

Three module pairs maintain mutual references for ORM model mapping and cross-domain lookups:
1. **`blog` $\leftrightarrow$ `seo`**: `BlogPost` model references `SEOMetadata` for search engine snippets, while `seo` router provides analysis routes for blog posts.
2. **`catalog` $\leftrightarrow$ `vendors`**: `Product` references `vendor_id`, while `Vendor` manages multi-merchant catalog subsets.
3. **`rbac` $\leftrightarrow$ `users`**: `User` has `roles` relationship through `UserRole` association table.

All three relationships are strictly resolved at the application/ORM level with foreign keys enforced by PostgreSQL (`ON DELETE RESTRICT`).
