# ADR-004: PostgreSQL as the Primary Database

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform requires a relational database for transactional data: users, products, orders, payments, inventory, and configuration. The database must provide strong consistency guarantees, support complex queries, handle semi-structured data, and scale to meet growth projections.

Candidates evaluated included PostgreSQL, MySQL/MariaDB, and CockroachDB.

MySQL lacks native JSONB support with indexing, has weaker support for advanced data types, and its default transaction isolation level (REPEATABLE READ with snapshot isolation) behaves differently from SQL standards in subtle ways.

CockroachDB offers distributed SQL but adds significant operational complexity that is unnecessary at our current scale and conflicts with the modular monolith approach (ADR-003).

## Decision

We will use **PostgreSQL** as the primary relational database for all transactional data.

### Rationale

1. **ACID compliance.** PostgreSQL provides full ACID transaction support with configurable isolation levels. This is essential for e-commerce operations where financial transactions, inventory updates, and order state changes must be consistent.

2. **JSONB support.** PostgreSQL's JSONB column type with GIN indexing allows us to store semi-structured data (product attributes, variant specifications, configuration) alongside relational data without sacrificing query performance. This eliminates the need for a separate document store for flexible product attributes.

3. **Rich extension ecosystem.** Extensions such as `pg_trgm` (trigram similarity for fuzzy search), `uuid-ossp` (UUID generation), `pgcrypto` (cryptographic functions), and `hstore` provide capabilities that would otherwise require external services.

4. **Maturity and reliability.** PostgreSQL has over 35 years of active development, extensive documentation, proven production reliability, and a large community. It is a conservative, low-risk choice for the data layer.

5. **Advanced features.** Window functions, CTEs (Common Table Expressions), materialized views, partial indexes, and expression indexes support complex reporting and query optimization patterns common in e-commerce.

6. **Async driver support.** The `asyncpg` driver provides high-performance asynchronous access, aligning with the async-first approach of FastAPI (ADR-001).

## Consequences

### Positive

- Strong consistency guarantees for all transactional operations.
- JSONB eliminates the need for a separate document database for semi-structured product data.
- Mature tooling for backups, replication, monitoring, and migration (Alembic for schema migrations).
- Excellent support for complex queries needed for reporting, analytics, and admin dashboards.
- Large talent pool and community support reduce hiring and troubleshooting risk.

### Negative

- Single-node PostgreSQL has vertical scaling limits. At very high write volumes, sharding or read replicas become necessary.
- JSONB queries, while powerful, can become complex and are less type-safe than relational columns. Overuse of JSONB can undermine the benefits of a relational schema.
- PostgreSQL's full-text search, while functional, is insufficient for our Persian language requirements (see ADR-002).

### Mitigations

- We use read replicas for scaling read-heavy workloads (reporting, product listings) and connection pooling (PgBouncer) to manage connection overhead.
- We establish guidelines for when to use JSONB versus relational columns: JSONB is reserved for genuinely variable-structure data (e.g., product attributes that differ by category), while core entity fields use typed columns.
- We use Alembic for all schema migrations with a review process that includes query plan analysis for new indexes and schema changes.
- Full-text search is delegated entirely to Elasticsearch (ADR-002), keeping PostgreSQL focused on transactional workloads.
