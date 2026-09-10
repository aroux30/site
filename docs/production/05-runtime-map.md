# 05 — RUNTIME TOPOLOGY & INFRASTRUCTURE MAP
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Standard:** Production Certification, Verification & Hardening Master v4  
**Date:** 2026-09-10  
**Host Environment:** Ubuntu 22.04 LTS (`91.107.144.136`)  

---

## 1. Network Topology & Container Map

All 11 platform services communicate over the private Docker bridge network `app-network`. Only Nginx (`:80`), Prometheus (`:9090`), and Grafana (`:3005`) expose host ports. Internal services (PostgreSQL, Redis, Elasticsearch, MinIO) are isolated from external traffic.

```
Internet / Client Requests
           ↓
[ecommerce-nginx] (Host Port 80, HTTP/2, Rate Limiting, Security Headers)
     ├── /api/*          ──> [ecommerce-backend:8000]
     ├── /media/*        ──> [ecommerce-minio:9000] (Internal)
     ├── /healthz        ──> [ecommerce-backend:8000/healthz]
     ├── /readyz         ──> [ecommerce-backend:8000/readyz]
     ├── /deep-health    ──> [ecommerce-backend:8000/deep-health]
     └── /* (Frontend)   ──> [ecommerce-frontend:3000]
```

---

## 2. Docker Container Inventory & Health Specifications

| Container Name | Base Image | Ports Mapped | Genuine Healthcheck Specification | Health Status |
|---|---|---|---|:---:|
| `ecommerce-nginx` | `nginx:1.27-alpine` | `0.0.0.0:80->80` | `wget -qO- http://127.0.0.1/healthz \|\| exit 1` | **healthy** |
| `ecommerce-backend`| Custom Python 3.12 | `8000/tcp` (Internal) | `curl -f http://localhost:8000/healthz \|\| exit 1` | **healthy** |
| `ecommerce-worker` | Custom Python 3.12 | `8000/tcp` (Internal) | `celery -A app.worker.celery_app status` | **healthy** |
| `ecommerce-beat` | Custom Python 3.12 | `8000/tcp` (Internal) | Native Python `/proc` scheduler process inspection | **healthy** |
| `ecommerce-frontend`| Node.js 20 Alpine | `3000/tcp` (Internal) | Next.js HTTP server listener check | **running** |
| `ecommerce-postgres`| `postgres:16-alpine` | `5432/tcp` (Internal) | `pg_isready -U ecommerce -d ecommerce` | **healthy** |
| `ecommerce-redis` | `redis:7-alpine` | `6379/tcp` (Internal) | `redis-cli -a $REDIS_PASSWORD ping` | **healthy** |
| `ecommerce-elasticsearch`| `elasticsearch:8.15.0`| `9200/tcp` (Internal)| `curl -s http://localhost:9200/_cluster/health` | **healthy** |
| `ecommerce-minio` | `minio/minio:latest`| `9000, 9001/tcp` | `mc ready local` | **healthy** |
| `ecommerce-prometheus`| `prom/prometheus:latest`| `0.0.0.0:9090->9090` | Prometheus internal HTTP health endpoint | **running** |
| `ecommerce-grafana` | `grafana/grafana:11.1`| `0.0.0.0:3005->3000` | Grafana `/api/health` probe | **running** |

---

## 3. Co-Located Host Workloads Isolation

To ensure absolute operational continuity, all existing host projects run in dedicated namespaces with zero port overlap:

| Co-Located Project | Type / Role | Host Port | Database Connection | Operational Status |
|---|---|:---:|---|:---:|
| **Real Estate Platform** | Next.js Frontend | `:3001` | Host PostgreSQL `real_estate_db` | **HTTP 200 OK** |
| **Razer Gold Telegram Bot**| Python Daemon + Web | `:8080` | Dedicated `razer-db-1` on port `5433` | **HTTP 200 OK** |
| **SEO Platform** | Next.js + FastAPI | `:3002`, `:8002` | Isolated `seo-postgres-1` on port `5435` | **HTTP 200 OK** |
| **VPN Service Bot** | Telegram VPN Bot | `:8003` | Isolated `vpn-db-1` on port `5434` | **HTTP 200 OK** |
