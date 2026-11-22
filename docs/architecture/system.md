# System Architecture Overview

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Network Topology](#network-topology)
3. [Request Flow](#request-flow)
4. [Service Components](#service-components)
5. [Data Flow](#data-flow)
6. [Infrastructure Diagram](#infrastructure-diagram)
7. [Environment Configuration](#environment-configuration)

---

## 1. High-Level Architecture

The platform follows a layered architecture with clear separation between the client-facing tier, application tier, and data tier. All traffic flows through Cloudflare for DDoS protection and edge caching before reaching the application infrastructure.

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                       │
│                         (End Users / Clients)                               │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE / CDN LAYER                               │
│                                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────────────┐  │
│  │ DDoS Shield │  │ Edge Caching │  │ WAF Rules  │  │ SSL Termination   │  │
│  └─────────────┘  └──────────────┘  └────────────┘  └───────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NGINX REVERSE PROXY                                 │
│                                                                             │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐    │
│  │ Load Balancing   │  │ Request Routing  │  │ Gzip/Brotli Compress   │    │
│  │ (Round Robin)    │  │ /api/* → Backend │  │ Static File Serving    │    │
│  │                  │  │ /*    → Frontend │  │ Rate Limiting          │    │
│  └─────────────────┘  └──────────────────┘  └─────────────────────────┘    │
└──────────┬───────────────────────┬──────────────────────────────────────────┘
           │                       │
           ▼                       ▼
┌─────────────────────┐  ┌─────────────────────────────────────────────────┐
│   NEXT.JS FRONTEND  │  │              FASTAPI BACKEND                    │
│                      │  │                                                 │
│  ┌────────────────┐  │  │  ┌──────────┐  ┌────────────┐  ┌───────────┐  │
│  │ App Router     │  │  │  │ REST API │  │ WebSocket  │  │ Admin API │  │
│  │ (SSR / SSG)    │  │  │  │ /api/v1  │  │ /ws        │  │ /admin    │  │
│  ├────────────────┤  │  │  └──────────┘  └────────────┘  └───────────┘  │
│  │ Server         │  │  │                                                 │
│  │ Components     │  │  │  ┌──────────────────────────────────────────┐  │
│  ├────────────────┤  │  │  │         APPLICATION MODULES               │  │
│  │ Client         │  │  │  │                                            │  │
│  │ Components     │  │  │  │  Users │ Products │ Orders │ Payments     │  │
│  ├────────────────┤  │  │  │  Cart  │ Search   │ Wallet │ Shipping     │  │
│  │ API Client     │──┼──▶  │  Media │ Reviews  │ CMS    │ Promotions   │  │
│  │ (TanStack)     │  │  │  │  Notifications │ Inventory │ Analytics    │  │
│  └────────────────┘  │  │  └──────────────────────────────────────────┘  │
│                      │  │                                                 │
│  Port: 3000          │  │  ┌──────────────┐  ┌─────────────────────────┐  │
└─────────────────────┘  │  │ Celery       │  │ Celery Beat            │  │
                          │  │ Workers      │  │ (Periodic Scheduler)   │  │
                          │  └──────────────┘  └─────────────────────────┘  │
                          │                                                 │
                          │  Port: 8000                                     │
                          └──────────┬──────────┬──────────┬───────────────┘
                                     │          │          │
                    ┌────────────────┘          │          └────────────────┐
                    ▼                           ▼                          ▼
┌──────────────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
│      POSTGRESQL 16       │  │       REDIS 7        │  │  ELASTICSEARCH 8    │
│                          │  │                      │  │                     │
│  ┌────────────────────┐  │  │  ┌────────────────┐  │  │  ┌───────────────┐  │
│  │ users schema       │  │  │  │ Session Store  │  │  │  │ products idx  │  │
│  │ products schema    │  │  │  │ Cache Layer    │  │  │  │ categories    │  │
│  │ orders schema      │  │  │  │ Rate Limiting  │  │  │  │ suggestions   │  │
│  │ payments schema    │  │  │  │ Task Broker    │  │  │  │ Persian       │  │
│  │ ... (per module)   │  │  │  │ Pub/Sub        │  │  │  │ Analyzer      │  │
│  └────────────────────┘  │  │  └────────────────┘  │  │  └───────────────┘  │
│                          │  │                      │  │                     │
│  Port: 5432              │  │  Port: 6379          │  │  Port: 9200         │
└──────────────────────────┘  └──────────────────────┘  └─────────────────────┘

                    ┌──────────────────────────────────┐
                    │            MINIO                  │
                    │                                    │
                    │  ┌──────────┐  ┌──────────────┐   │
                    │  │ product- │  │ user-avatars │   │
                    │  │ images   │  │ documents    │   │
                    │  │ cms-     │  │ temp-uploads │   │
                    │  │ assets   │  │              │   │
                    │  └──────────┘  └──────────────┘   │
                    │                                    │
                    │  Port: 9000 (API) / 9001 (Console)│
                    └──────────────────────────────────┘
```

---

## 2. Network Topology

### 2.1 Docker Network Segmentation

The application uses three isolated Docker networks for security:

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Host                          │
│                                                         │
│  ┌─────────────── public-net ──────────────────────┐   │
│  │  nginx ◄──► frontend ◄──► backend               │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │                                   │
│  ┌────────── private-net ──────────────────────────┐   │
│  │  backend ◄──► celery-worker ◄──► celery-beat    │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │                                   │
│  ┌──────────── data-net ───────────────────────────┐   │
│  │  postgres ◄──► redis ◄──► elasticsearch ◄──► minio │ │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

| Network         | Purpose                                    | Accessible By                              |
|-----------------|--------------------------------------------|--------------------------------------------|
| `public-net`    | External traffic routing                   | nginx, frontend, backend                   |
| `private-net`   | Internal application communication         | backend, celery-worker, celery-beat        |
| `data-net`      | Data layer isolation                       | backend, celery-worker, postgres, redis, elasticsearch, minio |

### 2.2 Port Mapping

| Service          | Internal Port | External Port | Exposure      |
|------------------|---------------|---------------|---------------|
| Nginx            | 80 / 443      | 80 / 443      | Public        |
| Next.js Frontend | 3000          | --            | Internal only |
| FastAPI Backend  | 8000          | --            | Internal only |
| PostgreSQL       | 5432          | --            | Internal only |
| Redis            | 6379          | --            | Internal only |
| Elasticsearch    | 9200          | --            | Internal only |
| MinIO API        | 9000          | --            | Internal only |
| MinIO Console    | 9001          | 9001          | Admin only    |
| Prometheus       | 9090          | --            | Internal only |
| Grafana          | 3001          | 3001          | Admin only    |

---

## 3. Request Flow

### 3.1 Typical Page Load (SSR)

```
User Browser
    │
    ├──1──► Cloudflare (DNS + CDN check)
    │           │
    │       Cache HIT? ──► Return cached response
    │           │
    │       Cache MISS
    │           │
    ├──2──► Nginx (reverse proxy)
    │           │
    │       Route: /* → Next.js
    │           │
    ├──3──► Next.js Server (SSR)
    │           │
    │       Server Component renders
    │           │
    │       Needs data? ──► fetch() to FastAPI (localhost:8000)
    │           │                    │
    │           │                    ├──► PostgreSQL (query)
    │           │                    ├──► Redis (cache check)
    │           │                    └──► Return JSON
    │           │
    │       Render HTML + hydration payload
    │           │
    ◄──4──── Return full HTML page
    │
    Browser hydrates React components
```

### 3.2 Typical API Request

```
Client (Browser/Mobile)
    │
    ├──1──► Cloudflare (pass-through for API)
    │
    ├──2──► Nginx
    │           │
    │       Route: /api/* → FastAPI
    │           │
    ├──3──► FastAPI Backend
    │           │
    │       ├── Authentication middleware (JWT validation)
    │       ├── Rate limiting middleware (Redis counter)
    │       ├── Request validation (Pydantic)
    │       │
    │       ├──► Application Layer (use case execution)
    │       │       │
    │       │       ├──► Domain Layer (business logic)
    │       │       │
    │       │       └──► Infrastructure Layer
    │       │               ├──► PostgreSQL (read/write)
    │       │               ├──► Redis (cache read/write)
    │       │               ├──► Elasticsearch (search)
    │       │               └──► MinIO (file operations)
    │       │
    │       ├── Response serialization (Pydantic)
    │       │
    ◄──4──── Return JSON response
```

### 3.3 Background Task Flow

```
API Request (triggers event)
    │
    ├──► Domain Event emitted
    │       │
    │       ├──► Event Handler dispatches Celery task
    │       │
    │       └──► Celery Broker (Redis)
    │               │
    │               ├──► Celery Worker picks up task
    │               │       │
    │               │       ├──► Send email (SMTP)
    │               │       ├──► Process image (Pillow)
    │               │       ├──► Update search index (ES)
    │               │       ├──► Generate report (export)
    │               │       └──► Send SMS notification
    │               │
    │               └──► Result stored in Redis
    │
    └──► Immediate response to client (202 Accepted)
```

---

## 4. Service Components

### 4.1 Nginx (Reverse Proxy)

**Role:** Entry point for all HTTP traffic after Cloudflare.

**Responsibilities:**
- SSL/TLS termination with Let's Encrypt certificates
- Request routing based on URL path
- Load balancing across multiple backend/frontend instances (Phase 2)
- Static file serving and caching
- Gzip/Brotli compression
- Security headers injection
- Request rate limiting (first layer)
- Request/response buffering
- Access logging

### 4.2 Next.js Frontend

**Role:** Server-side rendered React application serving the user interface.

**Responsibilities:**
- Server-Side Rendering (SSR) for SEO-critical pages
- Static Site Generation (SSG) for content pages
- Incremental Static Regeneration (ISR) for product pages
- Client-side routing and navigation
- API communication via TanStack Query
- Authentication state management
- RTL layout and Persian localization

### 4.3 FastAPI Backend

**Role:** Core API server handling all business logic and data operations.

**Responsibilities:**
- RESTful API endpoints (OpenAPI 3.1 documented)
- JWT authentication and RBAC authorization
- Request validation and response serialization
- Business logic orchestration via modular architecture
- Database operations via SQLAlchemy 2.x
- Cache management via Redis
- Search operations via Elasticsearch
- File operations via MinIO (S3 client)
- WebSocket connections for real-time features
- Health check and readiness endpoints

### 4.4 Celery Workers

**Role:** Asynchronous task processing for background operations.

**Responsibilities:**
- Email and SMS notification dispatch
- Image processing and thumbnail generation
- Search index synchronization
- Report generation and export
- Periodic cleanup tasks (expired carts, temp files)
- Payment status polling (for async payment gateways)

### 4.5 PostgreSQL

**Role:** Primary relational database for all persistent data.

**Responsibilities:**
- Transactional data storage with ACID compliance
- Schema-per-module data isolation
- UUID primary key generation
- JSONB storage for flexible attributes
- Full-text search (secondary, for admin queries)
- Data integrity via foreign keys and constraints

### 4.6 Redis

**Role:** In-memory data store for caching, sessions, and message brokering.

**Responsibilities:**
- Application-level caching (product data, category trees)
- Session storage and management
- JWT blacklist (revoked tokens)
- Rate limiting counters
- Celery message broker
- Celery result backend
- Real-time pub/sub for WebSocket events
- Distributed locking for concurrent operations

### 4.7 Elasticsearch

**Role:** Full-text search engine optimized for Persian language content.

**Responsibilities:**
- Product search with Persian analyzer
- Faceted search and filtering
- Autocomplete and search suggestions
- Search analytics and trending queries
- Admin search (orders, users)

### 4.8 MinIO

**Role:** S3-compatible object storage for media and document files.

**Responsibilities:**
- Product image storage and serving
- User avatar management
- Document storage (invoices, exports)
- CMS asset management
- Temporary upload staging
- Pre-signed URL generation for direct uploads

---

## 5. Data Flow

### 5.1 Write Path

```
Client Request
    │
    ▼
FastAPI (validate + authorize)
    │
    ▼
Application Service (orchestrate)
    │
    ├──► Domain Entity (business rules)
    │
    ├──► PostgreSQL (persist)
    │
    ├──► Redis (invalidate cache)
    │
    └──► Domain Event
            │
            ├──► Elasticsearch (async index update)
            ├──► Notification (async dispatch)
            └──► Analytics (async tracking)
```

### 5.2 Read Path

```
Client Request
    │
    ▼
FastAPI (validate + authorize)
    │
    ▼
Application Service
    │
    ├──► Redis (cache check)
    │       │
    │       ├── HIT → Return cached data
    │       │
    │       └── MISS
    │               │
    │               ▼
    │           PostgreSQL (query)
    │               │
    │               ▼
    │           Redis (populate cache)
    │
    └──► Return response
```

---

## 6. Infrastructure Diagram

### 6.1 Monitoring Stack

```
┌────────────────────────────────────────────────────┐
│                 Monitoring Layer                    │
│                                                    │
│  ┌──────────────┐    ┌──────────────┐              │
│  │  Prometheus   │───▶│   Grafana    │              │
│  │  (Metrics)    │    │ (Dashboards) │              │
│  └──────┬───────┘    └──────────────┘              │
│         │                                          │
│         │  Scrapes metrics from:                   │
│         ├──── FastAPI (/metrics)                    │
│         ├──── Nginx (stub_status)                  │
│         ├──── PostgreSQL (pg_exporter)              │
│         ├──── Redis (redis_exporter)                │
│         ├──── Elasticsearch (es_exporter)           │
│         └──── Node (node_exporter)                  │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │              Logging Pipeline                 │  │
│  │                                                │  │
│  │  App Logs ──► Structured JSON ──► Elasticsearch│  │
│  │                      │                         │  │
│  │                      ▼                         │  │
│  │               Kibana Dashboards                │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

---

## 7. Environment Configuration

### 7.1 Environment Variables

All services are configured via environment variables, managed through `.env` files per environment.

| Variable                     | Service    | Description                              |
|------------------------------|-----------|------------------------------------------|
| `DATABASE_URL`               | Backend   | PostgreSQL connection string              |
| `REDIS_URL`                  | Backend   | Redis connection string                   |
| `ELASTICSEARCH_URL`          | Backend   | Elasticsearch connection string           |
| `MINIO_ENDPOINT`             | Backend   | MinIO server endpoint                     |
| `MINIO_ACCESS_KEY`           | Backend   | MinIO access key                          |
| `MINIO_SECRET_KEY`           | Backend   | MinIO secret key                          |
| `JWT_SECRET_KEY`             | Backend   | JWT signing secret                        |
| `JWT_ALGORITHM`              | Backend   | JWT algorithm (RS256)                     |
| `CELERY_BROKER_URL`          | Workers   | Celery broker (Redis) URL                 |
| `CELERY_RESULT_BACKEND`      | Workers   | Celery result backend URL                 |
| `NEXT_PUBLIC_API_URL`        | Frontend  | Public API base URL                       |
| `NEXT_PUBLIC_SITE_URL`       | Frontend  | Public site URL                           |
| `SMTP_HOST`                  | Workers   | Email server host                         |
| `SMS_API_KEY`                | Workers   | SMS provider API key                      |

### 7.2 Health Checks

| Service        | Endpoint              | Expected Response      |
|----------------|------------------------|------------------------|
| FastAPI        | `GET /api/v1/health`  | `{"status": "healthy"}` |
| Next.js        | `GET /api/health`     | `200 OK`                |
| PostgreSQL     | TCP port 5432          | Connection accepted     |
| Redis          | `PING`                 | `PONG`                  |
| Elasticsearch  | `GET /_cluster/health` | `green` or `yellow`     |
| MinIO          | `GET /minio/health/live` | `200 OK`             |

---

*For detailed architecture of individual layers, see:*
- *[Backend Architecture](./backend.md)*
- *[Frontend Architecture](./frontend.md)*
- *[Search Architecture](./search.md)*
- *[Entity Relationship Diagram](./erd.md)*
