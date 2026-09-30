# ADR-009: Search Architecture — PostgreSQL as Source of Truth, Elasticsearch as Search Projection

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform uses PostgreSQL as the primary database (ADR-004) and Elasticsearch as the search engine (ADR-002). This dual-store architecture requires a clear strategy for data ownership, synchronization, and consistency guarantees.

Key questions:

- Which system is authoritative for product data?
- How is data synchronized between PostgreSQL and Elasticsearch?
- What consistency guarantees does the search index provide?
- How are synchronization failures detected and recovered?

Approaches evaluated:

1. **Dual write** — the application writes to both PostgreSQL and Elasticsearch in the same request. This is simple but introduces data inconsistency if either write fails and adds latency to every write operation.
2. **Change Data Capture (CDC)** — tools like Debezium capture database changes from the PostgreSQL WAL and stream them to Elasticsearch. This provides reliable synchronization but introduces significant infrastructure complexity (Kafka, Debezium, connectors).
3. **Event-driven sync** — application-level domain events trigger asynchronous Elasticsearch index updates via background tasks. This balances reliability with operational simplicity.

## Decision

We will use **PostgreSQL as the single source of truth** for all data and **Elasticsearch as a read-only search projection**, synchronized through **application-level domain events** processed by Celery background tasks.

### Architecture

```
[Write Operation]
       │
       ▼
  PostgreSQL (source of truth)
       │
       ├── Domain Event emitted (e.g., ProductUpdated)
       │
       ▼
  Celery Task Queue (Redis broker)
       │
       ▼
  Elasticsearch Index Writer
       │
       ▼
  Elasticsearch (search projection)
```

### Synchronization Rules

1. **All writes go to PostgreSQL.** No business data is written directly to Elasticsearch.
2. **Domain events trigger indexing.** When a product, category, or other searchable entity is created, updated, or deleted, a domain event is emitted that enqueues a Celery task to update the corresponding Elasticsearch document.
3. **Idempotent index operations.** Elasticsearch index operations use the entity's primary key as the document ID, making re-indexing idempotent and safe to retry.
4. **Full re-index capability.** A management command can rebuild any Elasticsearch index from scratch using PostgreSQL data. This serves as the recovery mechanism for any synchronization drift.
5. **Eventual consistency.** The search index is eventually consistent with the database. Under normal operation, the lag is under 5 seconds. The application accepts that search results may briefly lag behind the latest database state.

## Consequences

### Positive

- Single source of truth in PostgreSQL eliminates data ownership ambiguity.
- No distributed transaction coordination between PostgreSQL and Elasticsearch.
- Celery-based sync leverages existing infrastructure (ADR-005, ADR-006) without introducing new components like Kafka or Debezium.
- Idempotent operations and full re-index capability provide robust recovery from any synchronization failure.
- Search index can be rebuilt from scratch at any time without data loss.

### Negative

- Eventual consistency means search results may not reflect the very latest changes. Users who create or update a product may not immediately see it in search results.
- Application code must emit domain events for every write operation that affects searchable data. Missing an event leads to stale search results.
- Celery task failures (e.g., Elasticsearch is temporarily down) must be handled with retries and monitoring.
- Full re-index of a large catalog is a resource-intensive operation that may impact Elasticsearch performance during execution.

### Mitigations

- We implement a periodic reconciliation job that compares PostgreSQL record counts and timestamps with Elasticsearch documents, detecting and correcting any drift.
- Domain events are emitted through a centralized service layer, reducing the risk of missed events. Code review checklists include verification that searchable entity writes emit appropriate events.
- Celery tasks for indexing use exponential backoff retry with a dead-letter queue. Failed tasks trigger alerts for manual investigation.
- Full re-index uses bulk API with rate limiting to control Elasticsearch load, and can be run against a new index alias-switched atomically upon completion (zero-downtime re-indexing).
