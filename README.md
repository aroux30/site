# Iranian Enterprise E-Commerce Platform

A modern, enterprise-grade e-commerce platform built for the Iranian market with full Persian language support, Jalali calendar integration, and Iranian payment gateway compatibility.

---

## Overview

This platform is designed as a **Modular Monolith** following **Clean Architecture** principles, providing a scalable foundation that can evolve from a single-instance deployment to a distributed multi-service architecture as business demands grow.

### Key Features

- **Full Persian/RTL Support** -- Native right-to-left layout, Persian number formatting, Jalali calendar
- **Iranian Payment Gateways** -- Integration with Zarinpal, IDPay, NowPayments (Crypto/USDT), and Card-to-Card bank transfers
- **Advanced Product Search** -- Elasticsearch-powered search with custom Persian analyzer, synonym expansion, and faceted filtering
- **Digital Wallet** -- User wallet system for balance-based payments and cashback
- **Modular Architecture** -- 35 independent business modules with clean boundaries
- **170+ REST API Endpoints** -- Fully documented with OpenAPI/Swagger
- **128+ Automated Tests** -- Unit and integration tests with 100% pass rate
- **HttpOnly Secure Cookie Auth** -- XSS-resistant JWT authentication with refresh token rotation
- **Performance Optimized** -- P95 API response time target under 300ms

---

## Tech Stack

### Backend

| Component         | Technology                  |
|-------------------|-----------------------------|
| Language          | Python 3.12+                |
| Web Framework     | FastAPI                     |
| ORM               | SQLAlchemy 2.x (async)      |
| Validation        | Pydantic v2                 |
| Task Queue        | Celery 5.x                  |
| Migrations        | Alembic                     |
| Testing           | pytest + httpx              |

### Frontend

| Component         | Technology                  |
|-------------------|-----------------------------|
| Framework         | Next.js 15.5 (App Router)   |
| Language          | TypeScript 5.x              |
| Styling           | Tailwind CSS 3.x            |
| UI Components     | shadcn/ui                   |
| Client State      | Zustand                     |
| Server State      | TanStack Query v5           |
| Forms             | React Hook Form + Zod       |
| Testing           | Vitest + Playwright         |

### Infrastructure

| Component         | Technology                  |
|-------------------|-----------------------------|
| Database          | PostgreSQL 16               |
| Cache             | Redis 7                     |
| Search Engine     | Elasticsearch 8             |
| Object Storage    | MinIO (S3-compatible)       |
| Reverse Proxy     | Nginx                       |
| CDN               | Cloudflare                  |
| Containerization  | Docker + Docker Compose     |
| CI/CD             | GitHub Actions              |
| Monitoring        | Prometheus + Grafana        |

---

## Architecture

```
Internet → Cloudflare/CDN → Nginx → ┬→ Next.js (Frontend)
                                     └→ FastAPI (Backend) → ┬→ PostgreSQL
                                                            ├→ Redis
                                                            ├→ Elasticsearch
                                                            └→ MinIO
```

The backend is organized into 35 business modules, each following Clean Architecture with four layers:

- **API Layer** -- FastAPI routes, Pydantic schemas, dependency injection
- **Application Layer** -- Use cases, services, commands, queries
- **Domain Layer** -- Entities, value objects, business rules (zero external dependencies)
- **Infrastructure Layer** -- SQLAlchemy models, repository implementations, external service clients

For detailed architecture documentation, see the [docs/architecture/](docs/architecture/) directory.

---

## Getting Started

### Prerequisites

- **Docker** 24+ and **Docker Compose** v2
- **Node.js** 20+ (for local frontend development)
- **Python** 3.12+ (for local backend development)
- **Git**

### Quick Start (Docker Compose)

1. **Clone the repository:**

    ```bash
    git clone https://github.com/aroux30/site.git
    cd site
    ```

2. **Copy environment files:**

    ```bash
    cp backend/.env.example backend/.env
    cp frontend/.env.example frontend/.env
    ```

3. **Configure environment variables:**

    Edit `backend/.env` and set the required values:

    ```env
    DATABASE_URL=postgresql+asyncpg://ecommerce:change_me_in_production@postgres:5432/ecommerce
    REDIS_URL=redis://:change_me_in_production@redis:6379/0
    ELASTICSEARCH_URL=http://elasticsearch:9200
    MINIO_ENDPOINT=minio:9000
    MINIO_ACCESS_KEY=minioadmin
    MINIO_SECRET_KEY=change_me_in_production
    JWT_SECRET_KEY=your-secret-key-change-in-production
    ```

4. **Start all services:**

    ```bash
    docker compose up -d
    ```

5. **Run database migrations:**

    ```bash
    docker compose exec backend alembic upgrade head
    ```

6. **Seed initial data (optional):**

    ```bash
    docker compose exec backend python scripts/seed.py
    ```

7. **Access the application:**

    | Service            | URL                          |
    |--------------------|------------------------------|
    | Storefront         | http://localhost              |
    | API Documentation  | http://localhost/docs         |
    | MinIO Console      | http://localhost:9001         |
    | Grafana Dashboard  | http://localhost:3005         |

### Local Development (Without Docker)

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
celery -A app.worker.celery_app worker --loglevel=info

# Start Celery beat (separate terminal)
celery -A app.worker.celery_app beat --loglevel=info
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

---

## Development Guide

### Code Style

#### Backend (Python)

- **Formatter:** Ruff (format)
- **Linter:** Ruff (lint)
- **Type Checker:** mypy (strict mode)
- **Line Length:** 100 characters
- **Import Style:** absolute imports from `app.*`

```bash
# Format code
ruff format .

# Lint code
ruff check . --fix

# Type check
mypy app/
```

#### Frontend (TypeScript)

- **Formatter:** Prettier
- **Linter:** ESLint (with Next.js config)
- **Type Checker:** TypeScript strict mode
- **Line Length:** 100 characters

```bash
# Format code
pnpm format

# Lint code
pnpm lint

# Type check
pnpm type-check
```

### Running Tests

#### Backend

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific module tests
pytest tests/unit/modules/products/

# Run integration tests
pytest tests/integration/ -m integration
```

#### Frontend

```bash
# Run unit tests
pnpm test

# Run with coverage
pnpm test:coverage

# Run E2E tests
pnpm test:e2e

# Run E2E tests with UI
pnpm test:e2e:ui
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description_of_change"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration status
alembic current
```

### Search Index Management

```bash
# Full reindex of all products
docker compose exec backend python scripts/reindex_search.py

# Reindex specific index
docker compose exec backend python scripts/reindex_search.py --index products
```

### Module Scaffolding

```bash
# Generate a new module with all layers
python scripts/generate_module.py module_name
```

---

## API Documentation

The API documentation is auto-generated from FastAPI and available at:

- **Swagger UI:** `/api/docs`
- **ReDoc:** `/api/redoc`
- **OpenAPI JSON:** `/api/openapi.json`

### API Versioning

All API endpoints are prefixed with `/api/v1/`. When breaking changes are introduced, a new version (`/api/v2/`) will be created alongside the existing version with a documented deprecation timeline.

### Authentication

The API uses JWT Bearer tokens for authentication:

```bash
# Login
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Authenticated request
curl http://localhost/api/v1/users/me \
  -H "Authorization: Bearer <access_token>"
```

---

## Deployment

### Production Deployment

1. **Prepare production environment variables** with strong secrets and production database credentials.

2. **Configure SSL/TLS** via Nginx with Let's Encrypt:

    ```bash
    certbot --nginx -d yourdomain.com -d www.yourdomain.com
    ```

3. **Deploy with Docker Compose:**

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    ```

4. **Set up monitoring:**

    - Prometheus scrapes metrics from all services
    - Grafana dashboards for system and business metrics
    - Configure alerting rules for critical thresholds

### Environment Matrix

| Environment | Database        | Redis    | Elasticsearch | Purpose            |
|-------------|-----------------|----------|---------------|---------------------|
| Local       | Docker PostgreSQL| Docker Redis | Docker ES   | Developer workstation |
| Staging     | Managed PostgreSQL| Managed Redis | Docker ES | Pre-production testing |
| Production  | Managed PostgreSQL| Managed Redis | Managed ES | Live environment    |

### Backup Strategy

- **Database:** Automated daily backups with 30-day retention via `pg_dump`
- **Object Storage:** MinIO bucket replication or backup to secondary storage
- **Elasticsearch:** Snapshot API with daily snapshots to MinIO
- **Configuration:** All configuration in version control

---

## Documentation

| Document                                                | Description                                  |
|---------------------------------------------------------|----------------------------------------------|
| [Architecture Audit](docs/ARCHITECTURE_AUDIT.md)       | Architecture audit and decision log          |
| [System Architecture](docs/architecture/system.md)     | High-level system overview and diagrams      |
| [Backend Architecture](docs/architecture/backend.md)   | Backend module and layer architecture        |
| [Frontend Architecture](docs/architecture/frontend.md) | Frontend component and state architecture    |
| [Search Architecture](docs/architecture/search.md)     | Elasticsearch and Persian search design      |
| [ERD](docs/architecture/erd.md)                        | Complete entity relationship diagrams        |

---

## Contributing

1. Create a feature branch from `develop`: `git checkout -b feature/your-feature`
2. Follow the coding standards and conventions documented above
3. Write tests for all new functionality
4. Ensure all tests pass: `pytest` and `pnpm test`
5. Ensure linting passes: `ruff check .` and `pnpm lint`
6. Submit a pull request with a clear description of changes
7. Code review is required from at least one team member

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(products): add bulk import endpoint
fix(orders): correct tax calculation for discounted items
docs(architecture): update ERD with wallet module
refactor(users): extract password validation to value object
test(payments): add integration tests for Zarinpal gateway
```

---

## License

This project is proprietary software. All rights reserved.

---

*Built with care for the Iranian e-commerce ecosystem.*
