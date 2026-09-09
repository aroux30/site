# Backend Architecture

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Clean Architecture Layers](#clean-architecture-layers)
4. [Module Architecture](#module-architecture)
5. [Module Catalog](#module-catalog)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [API Design](#api-design)
8. [Database Strategy](#database-strategy)
9. [Authentication and Authorization](#authentication-and-authorization)
10. [Error Handling](#error-handling)
11. [Testing Strategy](#testing-strategy)
12. [Configuration Management](#configuration-management)

---

## 1. Overview

The backend is built with **FastAPI** following a **Modular Monolith** architecture with **Clean Architecture** (Onion Architecture) principles. Each business domain is encapsulated in its own module with clearly defined boundaries, enabling independent development, testing, and potential future extraction into microservices.

### Key Principles

- **Separation of Concerns:** Each layer has a single, well-defined responsibility.
- **Dependency Inversion:** High-level modules do not depend on low-level modules; both depend on abstractions.
- **Domain-Centric Design:** Business logic resides in the domain layer with zero framework dependencies.
- **Explicit Module Boundaries:** Modules communicate through defined interfaces, never through direct database access.
- **Testability:** Every layer can be tested in isolation through dependency injection.

---

## 2. Project Structure

```
backend/
├── alembic/                          # Database migration configuration
│   ├── versions/                     # Migration scripts
│   └── env.py                        # Alembic environment setup
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI application factory
│   ├── config.py                     # Application configuration (Pydantic Settings)
│   ├── dependencies.py               # Global dependency injection
│   │
│   ├── core/                         # Shared kernel (cross-cutting)
│   │   ├── __init__.py
│   │   ├── database.py               # SQLAlchemy engine & session factory
│   │   ├── redis.py                  # Redis client configuration
│   │   ├── elasticsearch.py          # Elasticsearch client
│   │   ├── minio_client.py           # MinIO/S3 client
│   │   ├── security.py               # JWT, hashing utilities
│   │   ├── events.py                 # Domain event bus
│   │   ├── exceptions.py             # Base exception classes
│   │   ├── middleware.py              # Global middleware
│   │   ├── pagination.py             # Pagination utilities
│   │   ├── base_repository.py        # Abstract repository base
│   │   ├── base_entity.py            # Base entity with UUID, timestamps
│   │   └── types.py                  # Shared type definitions
│   │
│   ├── modules/                      # Business modules
│   │   ├── users/                    # User management module
│   │   │   ├── __init__.py
│   │   │   ├── api/                  # API Layer
│   │   │   │   ├── __init__.py
│   │   │   │   ├── routes.py         # FastAPI router definitions
│   │   │   │   ├── schemas.py        # Pydantic request/response models
│   │   │   │   └── dependencies.py   # Module-specific DI
│   │   │   ├── application/          # Application Layer
│   │   │   │   ├── __init__.py
│   │   │   │   ├── services.py       # Application services (use cases)
│   │   │   │   ├── commands.py       # Command objects
│   │   │   │   ├── queries.py        # Query objects
│   │   │   │   └── dto.py            # Data transfer objects
│   │   │   ├── domain/               # Domain Layer
│   │   │   │   ├── __init__.py
│   │   │   │   ├── entities.py       # Domain entities
│   │   │   │   ├── value_objects.py   # Value objects
│   │   │   │   ├── events.py         # Domain events
│   │   │   │   ├── exceptions.py     # Domain exceptions
│   │   │   │   ├── services.py       # Domain services
│   │   │   │   └── interfaces.py     # Repository interfaces (ports)
│   │   │   └── infrastructure/       # Infrastructure Layer
│   │   │       ├── __init__.py
│   │   │       ├── models.py         # SQLAlchemy ORM models
│   │   │       ├── repository.py     # Repository implementation
│   │   │       └── mappers.py        # Entity <-> ORM model mappers
│   │   │
│   │   ├── products/                 # Product catalog module
│   │   ├── orders/                   # Order management module
│   │   ├── payments/                 # Payment processing module
│   │   ├── wallet/                   # Wallet management module
│   │   ├── cart/                     # Shopping cart module
│   │   ├── inventory/                # Inventory management module
│   │   ├── shipping/                 # Shipping module
│   │   ├── search/                   # Search module
│   │   ├── notifications/            # Notification module
│   │   ├── media/                    # Media/file management module
│   │   ├── reviews/                  # Reviews and ratings module
│   │   ├── promotions/               # Promotions and discounts module
│   │   ├── cms/                      # Content management module
│   │   ├── analytics/                # Analytics module
│   │   └── admin/                    # Admin panel module
│   │
│   └── tasks/                        # Celery task definitions
│       ├── __init__.py
│       ├── celery_app.py             # Celery application factory
│       ├── email_tasks.py            # Email dispatch tasks
│       ├── search_tasks.py           # Search index sync tasks
│       ├── image_tasks.py            # Image processing tasks
│       └── cleanup_tasks.py          # Periodic cleanup tasks
│
├── tests/                            # Test suite
│   ├── conftest.py                   # Global test fixtures
│   ├── unit/                         # Unit tests (per module)
│   ├── integration/                  # Integration tests
│   └── e2e/                          # End-to-end API tests
│
├── scripts/                          # Utility scripts
│   ├── seed_data.py                  # Database seeding
│   ├── reindex_search.py             # Elasticsearch reindex
│   └── generate_module.py            # Module scaffolding generator
│
├── pyproject.toml                    # Project dependencies (Poetry/uv)
├── Dockerfile                        # Container build
├── .env.example                      # Environment variable template
└── alembic.ini                       # Alembic configuration
```

---

## 3. Clean Architecture Layers

### Layer Diagram

```
            ┌───────────────────────────────────────────┐
            │              API Layer                     │
            │    FastAPI Routes, Pydantic Schemas,       │
            │    Dependency Injection, Middleware         │
            │                                            │
            │    Dependencies: FastAPI, Pydantic          │
            ├───────────────────────────────────────────┤
            │          Application Layer                 │
            │    Use Cases, Services, Commands,          │
            │    Queries, DTOs, Event Handlers            │
            │                                            │
            │    Dependencies: Domain interfaces         │
            ├───────────────────────────────────────────┤
            │            Domain Layer                    │
            │    Entities, Value Objects, Domain          │
            │    Services, Events, Repository             │
            │    Interfaces (Ports)                       │
            │                                            │
            │    Dependencies: NONE (pure Python)        │
            ├───────────────────────────────────────────┤
            │         Infrastructure Layer               │
            │    SQLAlchemy Models, Repository            │
            │    Implementations, External Service        │
            │    Clients, ORM Mappers                     │
            │                                            │
            │    Dependencies: SQLAlchemy, Redis,         │
            │    Elasticsearch, MinIO SDK                 │
            └───────────────────────────────────────────┘
```

### 3.1 API Layer

The outermost layer that handles HTTP concerns.

**Responsibilities:**
- Define FastAPI route handlers (endpoints)
- Validate incoming requests via Pydantic schemas
- Serialize outgoing responses
- Handle HTTP-specific concerns (status codes, headers)
- Dependency injection configuration
- Request/response middleware

**Key Rules:**
- No business logic in route handlers
- Route handlers delegate to application services
- One router per module, mounted on the main application
- Pydantic schemas are separate from domain entities

```python
# Example: app/modules/products/api/routes.py

from fastapi import APIRouter, Depends, status
from .schemas import ProductCreateRequest, ProductResponse, ProductListResponse
from .dependencies import get_product_service
from ..application.services import ProductService

router = APIRouter(prefix="/products", tags=["Products"])

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    request: ProductCreateRequest,
    service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    product = await service.create_product(request.to_command())
    return ProductResponse.from_entity(product)
```

### 3.2 Application Layer

Orchestrates use cases by coordinating domain objects and infrastructure.

**Responsibilities:**
- Implement use cases (application services)
- Coordinate domain entities and services
- Manage transactions
- Dispatch domain events
- Transform data between layers (DTOs)

**Key Rules:**
- Contains no business rules (those belong in the domain)
- Depends on domain interfaces, not implementations
- One service class per module (or split by read/write if complex)

```python
# Example: app/modules/products/application/services.py

from ..domain.entities import Product
from ..domain.interfaces import ProductRepository
from ..domain.events import ProductCreated
from app.core.events import EventBus

class ProductService:
    def __init__(
        self,
        repository: ProductRepository,
        event_bus: EventBus,
    ):
        self._repository = repository
        self._event_bus = event_bus

    async def create_product(self, command: CreateProductCommand) -> Product:
        product = Product.create(
            name=command.name,
            slug=command.slug,
            price=command.price,
            category_id=command.category_id,
        )
        await self._repository.save(product)
        await self._event_bus.publish(ProductCreated(product_id=product.id))
        return product
```

### 3.3 Domain Layer

The core of the application containing all business logic.

**Responsibilities:**
- Define domain entities with business rules
- Define value objects for type-safe domain concepts
- Define domain services for cross-entity logic
- Define repository interfaces (ports)
- Define domain events
- Define domain-specific exceptions

**Key Rules:**
- **Zero external dependencies** (no FastAPI, SQLAlchemy, etc.)
- Pure Python classes only
- Entities enforce their own invariants
- Rich domain model (logic lives in entities, not services)

```python
# Example: app/modules/products/domain/entities.py

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime
from .value_objects import Money, Slug
from .exceptions import InvalidProductError

@dataclass
class Product:
    id: UUID
    name: str
    slug: Slug
    price: Money
    category_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, name: str, slug: str, price: Decimal, category_id: UUID) -> "Product":
        if price <= 0:
            raise InvalidProductError("Price must be positive")
        if not name.strip():
            raise InvalidProductError("Product name is required")

        return cls(
            id=uuid4(),
            name=name.strip(),
            slug=Slug(slug),
            price=Money(amount=price, currency="IRR"),
            category_id=category_id,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
```

### 3.4 Infrastructure Layer

Implements the interfaces defined in the domain layer.

**Responsibilities:**
- SQLAlchemy ORM model definitions
- Repository implementations (adapters)
- External service integrations (payment gateways, SMS providers)
- Entity-to-ORM model mapping
- Database query optimization

**Key Rules:**
- Implements domain interfaces (repository pattern)
- Maps between domain entities and ORM models
- Handles database-specific concerns (transactions, queries)
- External service clients wrapped in adapters

```python
# Example: app/modules/products/infrastructure/repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..domain.entities import Product
from ..domain.interfaces import ProductRepository
from .models import ProductModel
from .mappers import ProductMapper

class SQLAlchemyProductRepository(ProductRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, product: Product) -> None:
        model = ProductMapper.to_model(product)
        self._session.add(model)
        await self._session.flush()

    async def find_by_id(self, product_id: UUID) -> Product | None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.id == product_id)
        )
        model = result.scalar_one_or_none()
        return ProductMapper.to_entity(model) if model else None
```

---

## 4. Module Architecture

### 4.1 Module Structure Template

Every module follows an identical internal structure:

```
module_name/
├── __init__.py               # Module registration
├── api/                      # API Layer
│   ├── __init__.py
│   ├── routes.py             # FastAPI router
│   ├── schemas.py            # Pydantic models (request/response)
│   └── dependencies.py       # Module DI container
├── application/              # Application Layer
│   ├── __init__.py
│   ├── services.py           # Use case orchestration
│   ├── commands.py           # Write operation commands
│   ├── queries.py            # Read operation queries
│   └── dto.py                # Internal data transfer objects
├── domain/                   # Domain Layer
│   ├── __init__.py
│   ├── entities.py           # Domain entities
│   ├── value_objects.py       # Value objects
│   ├── events.py             # Domain events
│   ├── exceptions.py         # Domain exceptions
│   ├── services.py           # Domain services
│   └── interfaces.py         # Port interfaces (abstract repos)
└── infrastructure/           # Infrastructure Layer
    ├── __init__.py
    ├── models.py             # SQLAlchemy ORM models
    ├── repository.py         # Repository implementation
    └── mappers.py            # Entity ↔ Model mappers
```

### 4.2 Module Registration

Modules are registered in the main application factory:

```python
# app/main.py

from fastapi import FastAPI
from app.modules.users.api.routes import router as users_router
from app.modules.products.api.routes import router as products_router
from app.modules.orders.api.routes import router as orders_router
# ... other module routers

def create_app() -> FastAPI:
    app = FastAPI(
        title="Iranian E-Commerce Platform",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Register module routers
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(products_router, prefix="/api/v1")
    app.include_router(orders_router, prefix="/api/v1")
    # ... register all modules

    # Register middleware
    register_middleware(app)

    # Register event handlers
    register_event_handlers(app)

    return app
```

### 4.3 Inter-Module Communication

Modules communicate through two mechanisms:

**1. Service Interfaces (Synchronous)**

```python
# Module A needs data from Module B
# Module A depends on Module B's service interface, not its implementation

class OrderService:
    def __init__(
        self,
        order_repo: OrderRepository,
        product_service: ProductServiceInterface,  # Interface from products module
        inventory_service: InventoryServiceInterface,  # Interface from inventory module
    ):
        ...
```

**2. Domain Events (Asynchronous)**

```python
# Module A publishes an event; Module B handles it without direct coupling

# In orders module:
await event_bus.publish(OrderPlaced(order_id=order.id, items=order.items))

# In inventory module (event handler):
@event_handler(OrderPlaced)
async def handle_order_placed(event: OrderPlaced):
    await inventory_service.reserve_stock(event.items)

# In notifications module (event handler):
@event_handler(OrderPlaced)
async def send_order_confirmation(event: OrderPlaced):
    await notification_service.send_order_email(event.order_id)
```

---

## 5. Module Catalog

### 5.1 Users Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `users`                                                      |
| **Description** | Handles user registration, authentication, profile management, and role-based access control. |
| **Entities**    | `User`, `Role`, `Permission`, `UserSession`, `Address`       |
| **Key Features**| JWT authentication, refresh token rotation, password reset, email verification, MFA (TOTP), social login, address book management. |
| **Events**      | `UserRegistered`, `UserVerified`, `PasswordChanged`, `UserDeactivated` |
| **Dependencies**| None (root module)                                           |

### 5.2 Products Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `products`                                                   |
| **Description** | Manages the complete product catalog including categories, attributes, variants, and pricing. |
| **Entities**    | `Product`, `Category`, `ProductVariant`, `ProductAttribute`, `ProductImage`, `Brand` |
| **Key Features**| Hierarchical categories, dynamic attributes (JSONB), variant management (size/color), multi-image gallery, SEO metadata, bulk import/export. |
| **Events**      | `ProductCreated`, `ProductUpdated`, `ProductDeleted`, `PriceChanged`, `CategoryUpdated` |
| **Dependencies**| `media` (image storage)                                      |

### 5.3 Inventory Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `inventory`                                                  |
| **Description** | Tracks product stock levels, manages reservations, and handles warehouse operations. |
| **Entities**    | `StockItem`, `StockReservation`, `StockMovement`, `Warehouse` |
| **Key Features**| Real-time stock tracking, reservation system (soft locks during checkout), stock movement history, low-stock alerts, multi-warehouse support. |
| **Events**      | `StockUpdated`, `StockReserved`, `StockReleased`, `LowStockAlert` |
| **Dependencies**| `products` (product reference)                               |

### 5.4 Orders Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `orders`                                                     |
| **Description** | Manages the complete order lifecycle from placement to fulfillment and returns. |
| **Entities**    | `Order`, `OrderItem`, `OrderStatusHistory`, `ReturnRequest`  |
| **Key Features**| Order state machine (pending -> confirmed -> processing -> shipped -> delivered -> completed), order splitting, return/refund workflow, order notes, admin order management. |
| **Events**      | `OrderPlaced`, `OrderConfirmed`, `OrderShipped`, `OrderDelivered`, `OrderCancelled`, `ReturnRequested` |
| **Dependencies**| `users`, `products`, `inventory`, `payments`, `shipping`     |

**Order State Machine:**

```
                    ┌──────────┐
                    │ PENDING  │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐
        │CONFIRMED │ │CANCELLED │
        └────┬─────┘ └──────────┘
             │
             ▼
        ┌──────────┐
        │PROCESSING│
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │ SHIPPED  │
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │DELIVERED │
        └────┬─────┘
             │
       ┌─────┼──────┐
       ▼            ▼
┌──────────┐  ┌──────────┐
│COMPLETED │  │ RETURNED │
└──────────┘  └──────────┘
```

### 5.5 Payments Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `payments`                                                   |
| **Description** | Processes payments through multiple Iranian payment gateways and manages transaction records. |
| **Entities**    | `Payment`, `PaymentTransaction`, `PaymentGateway`, `Refund`  |
| **Key Features**| Multi-gateway support (Zarinpal, Mellat, Saman, etc.), payment verification, refund processing, transaction logging, reconciliation reports. |
| **Events**      | `PaymentInitiated`, `PaymentCompleted`, `PaymentFailed`, `RefundProcessed` |
| **Dependencies**| `orders`, `wallet`                                           |

### 5.6 Wallet Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `wallet`                                                     |
| **Description** | Manages user digital wallets for balance-based payments and cashback rewards. |
| **Entities**    | `Wallet`, `WalletTransaction`, `WalletTransfer`              |
| **Key Features**| Credit/debit operations, transaction history, balance inquiry, wallet-to-wallet transfer, cashback crediting, withdrawal requests. |
| **Events**      | `WalletCredited`, `WalletDebited`, `WalletTransferCompleted` |
| **Dependencies**| `users`                                                      |

### 5.7 Cart Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `cart`                                                       |
| **Description** | Manages shopping carts for both authenticated and guest users. |
| **Entities**    | `Cart`, `CartItem`                                           |
| **Key Features**| Persistent carts (Redis-backed for guests, DB for authenticated), cart merging on login, price recalculation, stock validation at checkout, coupon application. |
| **Events**      | `CartUpdated`, `CartAbandoned`, `CartCheckedOut`             |
| **Dependencies**| `products`, `inventory`, `promotions`                        |

### 5.8 Shipping Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `shipping`                                                   |
| **Description** | Integrates with shipping providers, calculates rates, and tracks deliveries. |
| **Entities**    | `ShippingMethod`, `ShippingRate`, `Shipment`, `ShippingZone` |
| **Key Features**| Multiple shipping providers (Post, Tipax, etc.), rate calculation based on weight/zone, shipment tracking integration, delivery time estimation, free shipping rules. |
| **Events**      | `ShipmentCreated`, `ShipmentStatusUpdated`, `ShipmentDelivered` |
| **Dependencies**| `orders`                                                     |

### 5.9 Search Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | N/A (Elasticsearch-backed)                                   |
| **Description** | Provides full-text search with Persian language support, faceted filtering, and autocomplete. |
| **Entities**    | `SearchIndex`, `SearchSuggestion`                            |
| **Key Features**| Persian text analysis and normalization, synonym expansion, faceted search (category, brand, price range, attributes), autocomplete suggestions, search analytics, relevance tuning. |
| **Events**      | `SearchQueryExecuted`, `SearchIndexUpdated`                  |
| **Dependencies**| `products`, `categories`                                     |

See [Search Architecture](./search.md) for detailed documentation.

### 5.10 Notifications Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `notifications`                                              |
| **Description** | Dispatches notifications across multiple channels (email, SMS, push). |
| **Entities**    | `Notification`, `NotificationTemplate`, `NotificationLog`    |
| **Key Features**| Template-based notifications, multi-channel dispatch (email via SMTP, SMS via Kavenegar/etc.), notification preferences per user, delivery tracking, retry mechanism for failed deliveries. |
| **Events**      | `NotificationSent`, `NotificationFailed`                     |
| **Dependencies**| `users`                                                      |

### 5.11 Media Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `media`                                                      |
| **Description** | Handles file uploads, image processing, and object storage management via MinIO. |
| **Entities**    | `MediaFile`, `ImageVariant`                                  |
| **Key Features**| Direct upload via pre-signed URLs, automatic thumbnail generation (multiple sizes), image optimization (WebP conversion), file type validation, virus scanning (optional), CDN URL generation. |
| **Events**      | `FileUploaded`, `ImageProcessed`, `FileDeleted`              |
| **Dependencies**| None (utility module)                                        |

### 5.12 Reviews Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `reviews`                                                    |
| **Description** | Manages product reviews, ratings, and moderation workflow. |
| **Entities**    | `Review`, `ReviewVote`, `ReviewReport`                       |
| **Key Features**| Star rating (1-5), text reviews with pros/cons, verified purchase badge, review voting (helpful/not helpful), admin moderation queue, average rating calculation, review statistics. |
| **Events**      | `ReviewSubmitted`, `ReviewApproved`, `ReviewRejected`        |
| **Dependencies**| `users`, `products`, `orders` (purchase verification)        |

### 5.13 Promotions Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `promotions`                                                 |
| **Description** | Manages discount campaigns, coupon codes, and promotional pricing. |
| **Entities**    | `Coupon`, `Discount`, `Campaign`, `CouponUsage`             |
| **Key Features**| Percentage and fixed-amount discounts, coupon code generation and validation, usage limits (per-user, total), date-based campaigns, category/product-specific discounts, minimum order amount requirements, stackable vs. exclusive promotions. |
| **Events**      | `CouponApplied`, `CouponExpired`, `CampaignStarted`, `CampaignEnded` |
| **Dependencies**| `products`, `orders`                                         |

### 5.14 CMS Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `cms`                                                        |
| **Description** | Manages static content pages, banners, and configurable storefront elements. |
| **Entities**    | `Page`, `Banner`, `MenuItem`, `FAQ`, `Slider`                |
| **Key Features**| Rich text page editor, banner management with scheduling, navigation menu builder, FAQ management, slider/carousel management, SEO metadata for all content. |
| **Events**      | `PagePublished`, `BannerActivated`                           |
| **Dependencies**| `media` (content images)                                     |

### 5.15 Analytics Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | `analytics`                                                  |
| **Description** | Collects and aggregates business metrics for dashboards and reporting. |
| **Entities**    | `PageView`, `SalesMetric`, `UserActivity`, `Report`          |
| **Key Features**| Real-time dashboard (orders, revenue, visitors), sales reports (daily/weekly/monthly), product performance analytics, user behavior tracking, export to CSV/Excel, conversion funnel analysis. |
| **Events**      | Listens to events from all other modules                      |
| **Dependencies**| All modules (read-only event consumer)                        |

### 5.16 Admin Module

| Attribute       | Value                                                       |
|-----------------|-------------------------------------------------------------|
| **Schema**      | N/A (uses other module schemas)                              |
| **Description** | Provides admin-specific API endpoints for the administration panel. |
| **Entities**    | `AdminAction`, `SystemSetting`                               |
| **Key Features**| Admin authentication with elevated permissions, system configuration management, audit log viewer, bulk operations API, data export endpoints, system health dashboard. |
| **Events**      | `AdminActionPerformed`, `SettingUpdated`                      |
| **Dependencies**| All modules (administrative access)                           |

---

## 6. Cross-Cutting Concerns

### 6.1 Dependency Injection

FastAPI's built-in `Depends` system is used for dependency injection throughout:

```python
# app/modules/products/api/dependencies.py

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.events import get_event_bus
from ..application.services import ProductService
from ..infrastructure.repository import SQLAlchemyProductRepository

async def get_product_service(
    session: AsyncSession = Depends(get_session),
    event_bus: EventBus = Depends(get_event_bus),
) -> ProductService:
    repository = SQLAlchemyProductRepository(session)
    return ProductService(repository=repository, event_bus=event_bus)
```

### 6.2 Middleware Stack

```python
# Middleware execution order (outermost to innermost):

1. CORSMiddleware          # CORS headers
2. TrustedHostMiddleware    # Host header validation
3. RequestIDMiddleware      # Attach unique request ID
4. LoggingMiddleware        # Request/response logging
5. RateLimitMiddleware      # Rate limiting (Redis-backed)
6. AuthenticationMiddleware # JWT token validation
7. DatabaseSessionMiddleware # SQLAlchemy session lifecycle
```

### 6.3 Domain Event Bus

```python
# app/core/events.py

class EventBus:
    """In-process domain event dispatcher."""

    _handlers: dict[type[DomainEvent], list[EventHandler]] = {}

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler):
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent):
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}", exc_info=True)
```

### 6.4 Logging

All logging uses Python's `structlog` for structured JSON output:

```json
{
    "timestamp": "2026-09-09T10:30:00.000Z",
    "level": "info",
    "logger": "app.modules.orders.application.services",
    "request_id": "req_abc123",
    "user_id": "usr_def456",
    "message": "Order placed successfully",
    "order_id": "ord_ghi789",
    "total_amount": 1500000,
    "duration_ms": 45
}
```

---

## 7. API Design

### 7.1 URL Convention

```
/api/v1/{module}/{resource}
/api/v1/{module}/{resource}/{id}
/api/v1/{module}/{resource}/{id}/{sub-resource}
```

### 7.2 Standard Endpoints per Resource

| Method   | Endpoint                    | Description                 |
|----------|-----------------------------|-----------------------------|
| `GET`    | `/api/v1/products`          | List with pagination        |
| `POST`   | `/api/v1/products`          | Create new resource         |
| `GET`    | `/api/v1/products/{id}`     | Get by ID                   |
| `PUT`    | `/api/v1/products/{id}`     | Full update                 |
| `PATCH`  | `/api/v1/products/{id}`     | Partial update              |
| `DELETE` | `/api/v1/products/{id}`     | Soft delete                 |

### 7.3 Response Envelope

```json
{
    "success": true,
    "data": { ... },
    "meta": {
        "request_id": "req_abc123",
        "timestamp": "2026-09-09T10:30:00.000Z"
    }
}
```

### 7.4 Paginated Response

```json
{
    "success": true,
    "data": [ ... ],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total_items": 150,
        "total_pages": 8,
        "has_next": true,
        "has_previous": false
    },
    "meta": { ... }
}
```

### 7.5 Error Response

```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "details": [
            {
                "field": "price",
                "message": "Price must be a positive number"
            }
        ]
    },
    "meta": {
        "request_id": "req_abc123",
        "timestamp": "2026-09-09T10:30:00.000Z"
    }
}
```

---

## 8. Database Strategy

### 8.1 Schema Isolation

Each module owns its database schema:

```sql
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS products;
CREATE SCHEMA IF NOT EXISTS orders;
CREATE SCHEMA IF NOT EXISTS payments;
CREATE SCHEMA IF NOT EXISTS wallet;
CREATE SCHEMA IF NOT EXISTS cart;
CREATE SCHEMA IF NOT EXISTS inventory;
CREATE SCHEMA IF NOT EXISTS shipping;
CREATE SCHEMA IF NOT EXISTS notifications;
CREATE SCHEMA IF NOT EXISTS media;
CREATE SCHEMA IF NOT EXISTS reviews;
CREATE SCHEMA IF NOT EXISTS promotions;
CREATE SCHEMA IF NOT EXISTS cms;
CREATE SCHEMA IF NOT EXISTS analytics;
```

### 8.2 Base Entity

All entities share a common base:

```python
# app/core/base_entity.py

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

### 8.3 Migration Strategy

- **Tool:** Alembic with async support.
- **Naming:** `{timestamp}_{module}_{description}.py` (e.g., `20260909_products_add_brand_column.py`).
- **Policy:** One migration per schema change, never modify existing migrations.
- **Review:** All migrations require code review before merging.

---

## 9. Authentication and Authorization

### 9.1 JWT Token Flow

```
1. User logs in with credentials
2. Backend validates credentials
3. Backend issues:
   - Access Token (JWT, 15 min expiry, in response body)
   - Refresh Token (opaque, 7 day expiry, in HttpOnly cookie)
4. Client sends Access Token in Authorization header
5. On expiry, client uses Refresh Token to get new Access Token
6. On logout, Refresh Token is revoked (Redis blacklist)
```

### 9.2 RBAC Model

```
Roles:
├── SUPER_ADMIN    (full system access)
├── ADMIN          (administrative operations)
├── SELLER         (product and order management)
├── CUSTOMER       (shopping and account operations)
└── GUEST          (browsing and search only)

Permissions:
├── products:read, products:write, products:delete
├── orders:read, orders:write, orders:manage
├── users:read, users:write, users:manage
├── payments:read, payments:manage
├── analytics:read
└── system:configure
```

### 9.3 Permission Decorator

```python
from app.core.security import require_permission

@router.delete("/products/{product_id}")
@require_permission("products:delete")
async def delete_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    await service.delete_product(product_id)
    return {"success": True}
```

---

## 10. Error Handling

### 10.1 Exception Hierarchy

```
AppException (base)
├── DomainException
│   ├── EntityNotFoundError
│   ├── BusinessRuleViolationError
│   ├── InvalidOperationError
│   └── DuplicateEntityError
├── ApplicationException
│   ├── AuthenticationError
│   ├── AuthorizationError
│   ├── ValidationError
│   └── RateLimitExceededError
└── InfrastructureException
    ├── DatabaseError
    ├── ExternalServiceError
    ├── CacheError
    └── StorageError
```

### 10.2 Global Exception Handler

```python
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
            "meta": {
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        },
    )
```

---

## 11. Testing Strategy

### 11.1 Test Pyramid

```
       ┌─────────┐
       │  E2E    │  ~10% - Full API flow tests
       ├─────────┤
       │ Integr. │  ~30% - Module integration, DB tests
       ├─────────┤
       │  Unit   │  ~60% - Domain logic, pure functions
       └─────────┘
```

### 11.2 Test Categories

| Category        | Scope                              | Tools                       | Database |
|-----------------|------------------------------------|-----------------------------|----------|
| **Unit**        | Domain entities, value objects      | pytest, unittest.mock       | None     |
| **Integration** | Repository, service with DB        | pytest, testcontainers      | TestDB   |
| **E2E**         | Full HTTP request/response          | pytest, httpx, AsyncClient  | TestDB   |

### 11.3 Coverage Target

- **Overall:** Minimum 80% line coverage.
- **Domain Layer:** Minimum 95% coverage.
- **Application Layer:** Minimum 85% coverage.
- **API Layer:** Minimum 75% coverage (E2E tests).

---

## 12. Configuration Management

### 12.1 Pydantic Settings

```python
# app/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Iranian E-Commerce Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    class Config:
        env_file = ".env"
        case_sensitive = True
```

---

*For related documentation, see:*
- *[System Architecture](./system.md)*
- *[Frontend Architecture](./frontend.md)*
- *[Search Architecture](./search.md)*
- *[Entity Relationship Diagram](./erd.md)*
