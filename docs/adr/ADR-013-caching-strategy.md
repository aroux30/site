# ADR-013: Redis Caching with Event-Based Invalidation

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform serves read-heavy workloads: product listings, category trees, homepage content, and configuration data are read orders of magnitude more frequently than they are written. Serving these directly from PostgreSQL on every request wastes database resources and increases response latency.

A caching layer in Redis (ADR-005) can absorb the majority of read traffic. However, caching introduces the fundamental challenge of cache invalidation — ensuring that cached data reflects the current state of the source of truth.

Common invalidation strategies:

1. **TTL-only.** Cached data expires after a fixed duration. Simple but allows stale data to be served until expiration.
2. **Write-through.** Every database write simultaneously updates the cache. Consistent but couples write paths to cache availability and increases write latency.
3. **Event-based invalidation.** Domain events trigger targeted cache invalidation. The next read repopulates the cache from the database (cache-aside pattern).

## Decision

We will implement **Redis caching with event-based invalidation** using the cache-aside pattern, supplemented by TTL as a safety net.

### Architecture

```
[Read Path]
  Client → API → Check Redis Cache
                    ├── Cache HIT → Return cached data
                    └── Cache MISS → Query PostgreSQL → Store in Redis → Return data

[Write Path]
  Client → API → Write to PostgreSQL → Emit Domain Event
                                              │
                                              ▼
                                    Invalidate Redis Cache Keys
```

### Caching Policies

| Data Type | TTL | Invalidation Trigger | Cache Key Pattern |
|-----------|-----|---------------------|-------------------|
| Product detail | 30 min | ProductUpdated, ProductDeleted | `product:{id}` |
| Product listing (paginated) | 15 min | Any ProductUpdated in category | `products:cat:{id}:page:{n}` |
| Category tree | 60 min | CategoryUpdated, CategoryCreated | `categories:tree` |
| Site configuration | 120 min | ConfigUpdated | `config:{key}` |
| User profile | 30 min | UserUpdated | `user:{id}:profile` |

### Invalidation Rules

1. **Targeted invalidation.** Domain events carry the entity ID, allowing precise cache key deletion rather than full cache flushes.
2. **Pattern-based invalidation.** For list caches that depend on a category, a `SCAN`-based pattern delete removes all matching keys (e.g., `products:cat:123:*`).
3. **TTL safety net.** All cached entries have a TTL as a backstop. Even if an invalidation event is missed, stale data self-corrects within the TTL window.
4. **No cache warming.** After invalidation, caches are repopulated lazily on the next read. This avoids thundering herd problems for data that may not be immediately re-requested.

### Serialization

- Cached data is serialized as JSON using `orjson` for performance.
- Cache values include a schema version field to handle format changes during deployments. Cached data with an outdated schema version is treated as a cache miss.

## Consequences

### Positive

- Database read load is reduced significantly for frequently accessed, rarely changing data.
- Event-based invalidation keeps cached data fresh without waiting for TTL expiration.
- TTL safety net ensures bounded staleness even if invalidation events are lost.
- Cache-aside pattern keeps the cache layer non-critical — cache failures degrade to direct database reads, not errors.
- Schema versioning prevents stale serialization formats from causing deserialization errors after deployments.

### Negative

- Cache invalidation logic must be maintained alongside write operations. Missing an invalidation event leads to stale data until TTL expiration.
- Pattern-based invalidation using `SCAN` is O(N) and should be used sparingly on large keyspaces.
- Thundering herd can occur when a popular cache key expires or is invalidated and many concurrent requests simultaneously hit the database.

### Mitigations

- Invalidation events are emitted from the service layer alongside domain events (ADR-009), ensuring a single code path handles both Elasticsearch indexing and cache invalidation.
- We limit pattern-based invalidation to low-cardinality keyspaces (e.g., product listing pages per category). For high-cardinality scenarios, we use explicit key tracking with Redis sets.
- For high-traffic cache keys (e.g., homepage data), we implement probabilistic early expiration: cache entries are refreshed by a background task shortly before TTL expiration, preventing simultaneous cache misses.
- We monitor cache hit rates, miss rates, and invalidation frequency per key pattern to identify optimization opportunities.
