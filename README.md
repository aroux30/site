# Iranian Enterprise E-Commerce Platform

A modern, enterprise-grade e-commerce platform built for the Iranian market with full Persian language support, Jalali calendar integration, and Iranian payment gateway compatibility.

---

## Overview

This platform is designed as a **Modular Monolith** following **Clean Architecture** principles, providing a scalable foundation that can evolve from a single-instance deployment to a distributed multi-service architecture as business demands grow.

### Key Features

- **Full Persian/RTL Support** -- Native right-to-left layout, Persian number formatting, Jalali calendar
- **Iranian Payment Gateways** -- Integration with Zarinpal, IDPay, NowPayments (Crypto/USDT), and Card-to-Card bank transfers
- **Advanced Product Search** -- Elasticsearch-powered search with custom Persian analyzer and faceted filtering. A Postgres `ILIKE` path backs the storefront search page, and the weighting profile is shared by both product query builders. (Synonym expansion is *not* implemented.)
- **Digital Wallet** -- User wallet system for balance-based payments and cashback
- **Modular Architecture** -- 44 independent business modules with clean boundaries
- **631 REST API Endpoints** -- 559 router + 109 admin-router routes, fully documented with OpenAPI/Swagger
- **Automated Tests** -- Backend pytest suite (1057 tests passing) plus a frontend Vitest suite (35 tests passing); Playwright E2E specs are configured but not yet run in CI. Both suites run in `.github/workflows/ci.yml` alongside the invariant gates (`secret-scan`, `money-invariants`, `env-contract`, `schema-drift`).
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
| Object Storage    | Local volume (`uploads_data`) |
| Reverse Proxy     | Nginx                       |
| CDN               | Cloudflare                  |
| Containerization  | Docker + Docker Compose     |
| Monitoring        | `/metrics` exposed; collector not deployed |

---

## Architecture

```
Internet → Cloudflare/CDN → Nginx → ┬→ Next.js (Frontend)
                                     └→ FastAPI (Backend) → ┬→ PostgreSQL
                                                            ├→ Redis
                                                            ├→ Elasticsearch
                                                            └→ Local uploads volume
```

The backend is organized into 44 business modules, each following Clean Architecture with four layers:

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

### Quick Start (Docker Compose)

1. **Enter the project folder:**

    ```bash
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
    | Metrics (Prometheus format) | http://localhost/metrics |

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

### Knowledge Graph (graphify) — refresh after every edit

This repo has a [graphify](https://github.com/Graphify-Labs/graphify) knowledge graph at `graphify-out/`. If you are an AI assistant working in this repo, **run this after any edit that adds, removes, or renames a file, function, class, or module** — do not wait to be asked:

```bash
graphify update .
```

It costs $0, needs no API key, and takes ~22 seconds on this project. Run it once at the end of a task rather than after every file save.

Notes specific to this repo:

- It re-parses ~312 files every run whether or not they changed, so it is only loosely incremental — don't chain it into a fast edit loop.
- It indexes the project's markdown docs as well as code (~800 of the 8k nodes come from `README.md`, `FINAL_REPORT_FA.md`, `docs/architecture/*`), so doc edits count too.
- `No code-graph topology changes detected` means nothing structural changed. That is not an error.
- After a refactor that removes a lot of code the rebuild may be smaller and get rejected — re-run with `graphify update . --force`.
- Only `--force` and `--no-cluster` are valid for `update`. `--no-viz` belongs to `cluster-only` and will error here.

Full rebuild from scratch:

```bash
graphify extract . --code-only && graphify cluster-only . --no-label
```

Open `graphify-out/graph.html` in a browser for the interactive graph. New dependencies or build output should be added to `.graphifyignore`.

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
npm run format

# Lint code
npm run lint

# Type check
npm run type-check
```

### Running Tests

#### Backend

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific module tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/
```

#### Frontend

```bash
# Run unit tests (Vitest, jsdom) -- 35 tests across 5 files
npm test

# Watch mode
npm run test:watch

# Run with coverage (v8, scoped to the tested domain-logic modules)
npm run test:coverage

# Run E2E tests (Playwright) -- requires browsers, installed once:
#   npx playwright install --with-deps chromium
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui
```

The Vitest suite covers the highest-risk pure logic: money/pricing tiers, payment
routing, PII masking, RMA return rules, Iranian commerce validators (Shetab card
Luhn, national ID, mobile, postal code), dynamic field validation, bulk-import
validation, and JSON-LD escaping. The Playwright specs exercise the storefront
chrome (header, footer, listing and login pages) and skip data-dependent
assertions when the backend API is not running.

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

Backups are driven by `scripts/backup.sh` (PostgreSQL `pg_dump` + MinIO `mc
mirror`, checksummed, optionally AES-256 encrypted). Retention defaults to the
last 7 backups, configurable with `--retain`. Scheduling, encryption, RPO/RTO
and the restore-verification record are documented in
[`docs/runbooks/BACKUP_RESTORE.md`](docs/runbooks/BACKUP_RESTORE.md).

- **Database:** `pg_dump` into `backups/app_db_<timestamp>.sql.gz` with a
  `.sha256` sidecar. Schedule via `scripts/cron.d/ecommerce-backup` or the
  systemd units in `scripts/systemd/`.
- **Object Storage:** MinIO bucket mirrored to a `.tar.gz` (off-host copies are
  an operator responsibility — not automated).
- **Elasticsearch:** `_snapshot` API when reachable; it is a derived index and
  is skippable (rebuildable from PostgreSQL).
- **Verification:** `scripts/verify_backup.sh` restores into a throwaway
  database and drops it — run and record it, because an unverified backup is
  not proof. **No restore has been verified in this repository's environment yet.**
- **Configuration:** All configuration in version control (except `.env`).

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

## Development & Quality Standards

1. Develop directly within the local project directory
2. Follow the coding standards and conventions documented above
3. Write tests for all new functionality
4. Ensure all tests pass: `pytest` and `npm test`
5. Ensure linting passes: `ruff check .` and `npm run lint`

---

## License

This project is proprietary software. All rights reserved.

---

*Built with care for the Iranian e-commerce ecosystem.*
