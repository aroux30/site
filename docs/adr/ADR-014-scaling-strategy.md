# ADR-014: Horizontal Scaling Strategy Without Microservices

**Date:** 2026-09-09

**Status:** Accepted

## Context

The modular monolith architecture (ADR-003) provides significant simplicity benefits but raises questions about how the platform scales as traffic and data volumes grow. A common criticism of monolithic architectures is that they cannot scale horizontally — this is a misconception. A stateless monolith can scale horizontally just as effectively as microservices for the majority of scaling challenges.

The platform must have a clear scaling roadmap that addresses:

- Increasing HTTP request volume.
- Growing database read and write load.
- Expanding background task workloads.
- Search index performance under larger catalogs.
- File storage growth.

## Decision

We will scale the platform **horizontally at the infrastructure layer** without decomposing the modular monolith into microservices, following a phased approach based on observed bottlenecks.

### Scaling Phases

#### Phase 1: Vertical Scaling (Current)

**Trigger:** Initial launch through moderate traffic.

- Single application server running multiple Uvicorn workers behind a reverse proxy (Nginx).
- Single PostgreSQL instance with connection pooling (PgBouncer).
- Single Redis instance.
- Single Elasticsearch node.
- Celery workers co-located on the application server.

**Capacity:** Sufficient for thousands of concurrent users and hundreds of requests per second.

#### Phase 2: Horizontal Application Scaling

**Trigger:** Application server CPU or memory becomes the bottleneck.

- Deploy multiple application server instances behind a load balancer.
- The application is stateless (JWT authentication, no server-side sessions) and can scale to N instances.
- Celery workers are deployed on dedicated machines, separated from web workers.
- Redis is promoted to a dedicated instance (or Sentinel pair for HA).

**Prerequisites:**
- All application state must be externalized (database, Redis, S3). No local filesystem dependencies.
- Health check endpoints for load balancer probing.
- Centralized logging and request tracing across instances.

#### Phase 3: Database Read Scaling

**Trigger:** PostgreSQL read queries become the bottleneck despite caching (ADR-013).

- Introduce PostgreSQL read replicas for read-heavy queries (product listings, search, reporting).
- Application routes read queries to replicas via a connection router.
- Write queries continue to target the primary instance.
- Replication lag is acceptable for read-heavy workloads (eventual consistency for reads).

**Prerequisites:**
- Query classification (read vs. write) in the data access layer.
- Monitoring of replication lag to ensure it stays within acceptable bounds.

#### Phase 4: Search and Cache Scaling

**Trigger:** Elasticsearch or Redis becomes the bottleneck.

- Elasticsearch scales from a single node to a multi-node cluster with dedicated master, data, and coordinating nodes.
- Redis scales from a single instance to Redis Cluster for horizontal sharding.
- These are infrastructure changes that require no application code modifications.

#### Phase 5: Selective Service Extraction

**Trigger:** A specific module has fundamentally different scaling requirements or deployment cadence that cannot be addressed by horizontal scaling of the monolith.

- Extract the specific module into an independent service.
- Module boundaries (ADR-003) are already in place, making extraction a bounded effort.
- This is an escape hatch, not a default strategy. Most platforms never reach this phase.

### What We Do NOT Do

- We do not preemptively split the monolith into microservices "in case we need to scale."
- We do not introduce Kubernetes, service mesh, or container orchestration until the deployment model demands it.
- We do not add distributed tracing, circuit breakers, or service discovery until there are multiple independently deployed services.

## Consequences

### Positive

- Scaling is applied incrementally based on measured bottlenecks, not speculative future needs.
- Each phase builds on the previous one without requiring architectural rewrites.
- The team avoids the operational complexity of microservices, Kubernetes, and distributed systems until genuinely justified.
- Infrastructure costs are proportional to actual load, not inflated by premature architectural complexity.
- The stateless application design (JWT, externalized state) enables horizontal scaling at any time without code changes.

### Negative

- All modules scale together even if only one module is under load. This wastes resources compared to independent service scaling.
- Vertical scaling limits (single PostgreSQL writer) will eventually be reached for write-heavy workloads.
- The team must resist the temptation to over-engineer early, which requires discipline and clear criteria for when to move to the next phase.

### Mitigations

- We establish quantitative triggers for each scaling phase (e.g., "move to Phase 2 when p99 response time exceeds 500ms at the application layer"), ensuring scaling decisions are data-driven.
- For the PostgreSQL write bottleneck, table partitioning, write batching, and connection pooling can defer Phase 5 significantly.
- We maintain architecture fitness functions (automated tests) that verify the application remains stateless and horizontally scalable as new features are added.
- Regular load testing validates that the current phase can handle projected traffic for the next 6-12 months.
