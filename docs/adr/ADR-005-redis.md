# ADR-005: Redis as the In-Memory Data Store

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform has several requirements that demand a fast, in-memory data store:

- **Application caching.** Product listings, category trees, and configuration data are read-heavy and change infrequently. Serving these from the primary database on every request wastes resources and increases latency.
- **Celery message broker.** Background task processing (ADR-006) requires a message broker for task queuing.
- **Rate limiting.** API endpoints need rate limiting to prevent abuse, requiring fast atomic counters with TTL support.
- **Session storage.** Temporary session data and OTP codes (ADR-007) need a fast, expirable key-value store.
- **Distributed locking.** Certain operations (inventory reservation, payment processing) require distributed locks to prevent race conditions.

Candidates evaluated included Redis, Memcached, and using PostgreSQL for all caching needs.

Memcached is limited to simple key-value caching without data structures, persistence, or pub/sub — insufficient for our broader requirements.

Using PostgreSQL for caching couples cache load with transactional load and lacks the sub-millisecond latency of an in-memory store.

## Decision

We will use **Redis** as the unified in-memory data store for caching, message brokering, rate limiting, session management, and distributed locking.

### Rationale

1. **Versatile data structures.** Redis supports strings, hashes, lists, sets, sorted sets, streams, and HyperLogLog. This versatility allows a single system to serve multiple use cases: cached objects (strings/hashes), rate limiting counters (strings with INCR and EXPIRE), sorted leaderboards (sorted sets), and pub/sub messaging.

2. **Celery broker compatibility.** Redis is a first-class Celery broker and result backend, providing reliable task queuing with lower operational overhead than RabbitMQ for our scale.

3. **Atomic operations with TTL.** Commands like `INCR`, `SETNX`, and `EXPIRE` are atomic and enable rate limiting and distributed locking patterns without application-level concurrency control.

4. **Sub-millisecond latency.** Redis operates entirely in memory, delivering consistent sub-millisecond response times for cache hits — critical for maintaining low API response latency.

5. **Pub/Sub and Streams.** Redis pub/sub supports real-time event notification for cache invalidation (ADR-013). Redis Streams can serve as a lightweight event log for internal event-driven communication.

6. **Operational simplicity.** A single Redis instance (or Sentinel/Cluster for HA) serves all use cases, reducing the number of infrastructure components to manage.

## Consequences

### Positive

- Single infrastructure component serves caching, brokering, rate limiting, sessions, and locking.
- Sub-millisecond latency for cache hits significantly reduces API response times.
- Atomic operations eliminate race conditions in rate limiting and distributed locking without application-level locking.
- Celery integration is straightforward and well-documented.
- TTL-based expiration provides automatic cleanup for sessions, OTP codes, and temporary data.

### Negative

- Redis is primarily an in-memory store. Data that exceeds available memory is evicted according to the configured policy, which can cause unexpected cache misses.
- Redis is single-threaded for command execution. CPU-intensive Lua scripts or very high command rates on a single instance can become a bottleneck.
- Using Redis for multiple purposes means a Redis failure affects caching, task processing, rate limiting, and sessions simultaneously.

### Mitigations

- We configure appropriate `maxmemory` and eviction policies (`allkeys-lru` for cache databases, `noeviction` for Celery broker databases) using separate Redis logical databases or instances.
- We use Redis Sentinel for automatic failover in production, with a path to Redis Cluster if horizontal scaling becomes necessary.
- We design the application to degrade gracefully when Redis is unavailable: cache misses fall through to the database, rate limiting becomes permissive, and background tasks are retried.
- We monitor Redis memory usage, connection counts, and command latency with alerts for capacity planning.
