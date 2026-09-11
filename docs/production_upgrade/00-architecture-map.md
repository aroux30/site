# 00 — MODULAR MONOLITH ARCHITECTURE MAP & BOUNDARY MATRIX
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-11  
**Repository:** `https://github.com/aroux30/site`  
**Standard:** Production Upgrade / Hardening / Verification Master v3.0  
**Evaluator:** Principal Software Architect & Domain Systems Engineer  

---

## 1. Clean Architecture Stratification

The codebase adheres to Clean Architecture and Domain-Driven Design (DDD) principles with unidirectional dependency flow:

```
[ Transport / API Layer ]  ──> FastAPI routers, request/response Pydantic v2 schemas
          ↓
[ Application Layer ]      ──> Command/query use-case services, transaction orchestration
          ↓
[ Domain Layer ]           ──> Pure entities, value objects (Money), business invariants
          ↓
[ Infrastructure Layer ]   ──> SQLAlchemy ORM sessions, Redis caching, Elasticsearch client, MinIO S3
```

### Architectural Fitness Audit (AST Validation)
An automated Abstract Syntax Tree (AST) analysis confirmed **zero framework leaks** in `backend/app/modules/*/domain/`:
- `fastapi`: **0 imports**
- `AsyncSession`: **0 imports**
- `redis`: **0 imports**
- `elasticsearch`: **0 imports**
- `minio`: **0 imports**
- Third-party payment gateway SDKs: **0 imports**

---

## 2. Command / Query Separation Boundaries (ARCH-006)

To prevent God-services and maintain testability, application services enforce explicit command and query separation:

| Domain | Command Methods (Mutations with DB Transaction) | Query Methods (Read-Only Projections) |
|---|---|---|
| **Inventory** | `reserve_stock`, `release_reservation`, `adjust_stock` | `get_inventory`, `get_inventory_list`, `check_availability` |
| **Orders** | `create_order`, `cancel_order`, `admin_update_status` | `get_order`, `get_orders`, `admin_get_orders`, `get_order_timeline` |
| **Payments** | `create_payment`, `verify_payment`, `approve_payment`, `refund_payment` | `get_payment`, `get_payment_methods` |
| **Wallet** | `credit`, `debit`, `get_or_create_wallet` | `get_balance`, `get_transactions` |
| **Checkout** | `create_order` (atomic reservation + order persistence) | `calculate_quote`, `validate_checkout` |
| **Catalog** | `create_product`, `update_product`, `delete_product` | `get_product_by_slug`, `list_products`, `get_category_tree` |
| **Discounts** | `apply_discount` (records redemption, increments counters) | `validate_coupon`, `calculate_discount` |

---

## 3. Canonical Authentication & Authorization Architecture (IAM-001 & IAM-002)

### IAM-001: Authentication Dual-Channel Transport Model
```
[ Incoming Request ]
        │
        ├── Header: "Authorization: Bearer <JWT>"  ──> Mobile Apps / Programmatic API
        │
        └── Cookie: "access_token" (HttpOnly, Secure) ──> Web Storefront / Admin Browsers
                │
                ▼
        verify_token(token, expected_type="access")
                │
                ▼
        Token Subject (UUID user_id) + Claims (roles, permissions)
```
- **Password Security:** Argon2id hashing via `passlib.context.CryptContext(schemes=["argon2"])`.
- **Session Duration:** Access tokens expire in 30 minutes; refresh tokens expire in 7 days.
- **CSRF & XSS Mitigation:** Browser access tokens are stored in `HttpOnly=True, Secure=True, SameSite=Lax` cookies. JavaScript cannot access tokens, eliminating token theft via XSS.

### IAM-002: Authorization & IDOR Protection
- **Role-Based Access Control:** Database-backed `roles`, `permissions`, and `role_permissions` tables.
- **Permission Dependencies:** Privileged endpoints enforce `RequirePermissions("orders:write")` in FastAPI dependencies.
- **Resource Ownership Validation:** Customer endpoints enforce `Order.user_id == current_user_id` and `Wallet.user_id == current_user_id` directly in SQL queries, rejecting ID tampering with 404 Not Found.

---

## 4. Domain Ownership Matrix (ARCH-005)

| Bounded Context | Module Directory | Core Domain Entities | Primary Service | Invariants Enforced |
|---|---|---|---|---|
| **Identity** | `app.modules.auth` | `UserSession`, `OTPRequest` | `AuthService` | Iranian phone regex `09xxxxxxxxx`, OTP 120s cooldown |
| **Users** | `app.modules.users` | `User`, `UserProfile`, `Address` | `UserService` | Single default address per user, 10-digit postal code |
| **RBAC** | `app.modules.rbac` | `Role`, `Permission`, `UserRole` | `RbacService` | System roles non-deletable, wildcard permission matching |
| **Catalog** | `app.modules.catalog` | `Product`, `ProductVariant`, `Category`| `CatalogService` | SKU uniqueness, Materialized Path category tree |
| **Inventory** | `app.modules.inventory`| `InventoryItem`, `InventoryReservation` | `InventoryService` | `available + reserved == total`, `SELECT ... FOR UPDATE` |
| **Cart** | `app.modules.cart` | `Cart`, `CartItem` | `CartService` | Server-authoritative totals, guest-to-user merge |
| **Checkout** | `app.modules.checkout` | `TaxRule` | `CheckoutService`, `TaxService` | Idempotent order creation, server recalculation of VAT |
| **Orders** | `app.modules.orders` | `Order`, `OrderItem`, `OrderStatusHistory`| `OrderService`, `InvoiceService`| 12-state deterministic FSM, immutable item snapshots |
| **Payments** | `app.modules.payments` | `Payment`, `PaymentWebhookEvent`, `Refund`| `PaymentService` | Gateway strategy, fail-closed mock, webhook deduplication |
| **Wallet** | `app.modules.wallet` | `Wallet`, `WalletTransaction` | `WalletService` | Append-only ledger, row locks, zero negative balance |
| **Discounts** | `app.modules.discounts`| `Discount`, `Coupon`, `CouponRedemption`| `DiscountService` | Single-use concurrency locks, max discount caps |
| **Shipping** | `app.modules.shipping` | `ShippingMethod`, `ShippingRate`, `Shipment`| `ShippingService`| Weight/province matrix, order status validation |
| **Outbox** | `app.modules.automation`| `OutboxMessage` | `OutboxService` | `SKIP LOCKED` worker claim, transactional event dispatch |
| **Search** | `app.modules.search` | *(Elasticsearch index projection)* | `SearchService` | Persian ZWNJ analyzer, edge n-gram autocomplete |
| **Media** | `app.modules.media` | `MediaAsset` | `MediaService` | MIME whitelist, 10MB limit, anti-path traversal |
