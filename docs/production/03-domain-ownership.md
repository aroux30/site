# 03 — DOMAIN OWNERSHIP & BOUNDARY MATRIX
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-10  

---

| Bounded Context | Module Package | Domain Entities | Application Service | Invariants & Transaction Boundaries |
|---|---|---|---|---|
| **Core Identity** | `app.modules.auth` | `UserSession`, `OTPRequest` | `AuthService` | Phone format (`09xxxxxxxxx`), OTP 120s cooldown, Argon2id passwords |
| **Customer Management** | `app.modules.users` | `User`, `UserProfile`, `Address` | `UserService` | Single default address per user, 10-digit postal code |
| **Authorization** | `app.modules.rbac` | `Role`, `Permission`, `UserRole` | `RbacService` | System roles cannot be deleted, wildcard permission support |
| **Product Catalog** | `app.modules.catalog` | `Product`, `ProductVariant`, `Category`, `Brand`, `Tag`, `Attribute` | `CatalogService` | SKU uniqueness, Materialized Path tree (`/root/sub`), immutable variant prices |
| **Stock & Inventory** | `app.modules.inventory`| `InventoryItem`, `InventoryReservation`, `InventoryTransaction` | `InventoryService` | `available + reserved == total`, `SELECT ... FOR UPDATE` row locks, TTL reservation |
| **Shopping Cart** | `app.modules.cart` | `Cart`, `CartItem` | `CartService` | Server-authoritative totals, guest-cart merge via `X-Session-ID`, stale price refresh |
| **Checkout & Taxation**| `app.modules.checkout`| `TaxRule` | `CheckoutService`, `TaxService` | Idempotent order creation, server recalculation of VAT (basis points) |
| **Orders Lifecycle** | `app.modules.orders` | `Order`, `OrderItem`, `OrderStatusHistory` | `OrderService`, `InvoiceService` | 12-state deterministic FSM, immutable item snapshots, official printable tax invoice |
| **Payments** | `app.modules.payments` | `Payment`, `PaymentTransaction`, `Refund` | `PaymentService` | Strategy Pattern (Zarinpal, IDPay, NowPayments USDT, C2C), duplicate webhook rejection |
| **Digital Wallet** | `app.modules.wallet` | `Wallet`, `WalletTransaction` | `WalletService` | Double-entry ledger, row-level locks, zero negative balance, audit trail |
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
