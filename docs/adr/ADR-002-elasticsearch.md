# ADR-002: Elasticsearch as the Search Engine

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform requires full-text search capabilities across product catalogs, categories, and content. A significant portion of the content is in Persian (Farsi), which presents specific linguistic challenges: right-to-left text, zero-width non-joiners (ZWNJ), character normalization (e.g., ی vs. ي, ک vs. ك), and the absence of reliable word boundary detection without specialized tokenizers.

Additionally, the platform needs faceted search (filtering by category, price range, brand, availability), autocomplete/suggest functionality, relevance tuning, and the ability to scale search independently of the primary database.

Candidates evaluated included PostgreSQL full-text search, Elasticsearch, Meilisearch, and Typesense.

PostgreSQL full-text search handles basic scenarios but lacks mature Persian language support, offers limited faceted search capabilities, and couples search load with transactional database load.

Meilisearch and Typesense are simpler to operate but offer less control over analyzers, tokenizers, and relevance tuning for Persian text.

## Decision

We will use **Elasticsearch** as the dedicated search engine for all full-text search, faceted filtering, and autocomplete functionality.

### Rationale

1. **Persian text analysis.** Elasticsearch provides configurable analysis chains with ICU plugins, custom character filters for Arabic/Persian normalization, and the ability to build tailored analyzers that handle ZWNJ, character variants, and Persian-specific stop words.

2. **Faceted search.** Elasticsearch aggregations natively support faceted navigation — a core requirement for e-commerce product filtering by category, price range, brand, color, size, and other attributes.

3. **Relevance tuning.** The query DSL supports boosting, function scoring, decay functions, and custom similarity models. This enables fine-tuned ranking that accounts for business rules (e.g., boosting in-stock items, promoted products, or higher-rated sellers).

4. **Autocomplete and suggestions.** Completion suggesters, edge n-gram tokenizers, and phrase suggesters provide responsive search-as-you-type experiences critical for e-commerce conversion.

5. **Scalability.** Elasticsearch scales horizontally through sharding and replication. Search indexing and query load are fully decoupled from the primary PostgreSQL database, allowing independent scaling.

6. **Ecosystem maturity.** Elasticsearch has extensive documentation, a large community, proven production track record at scale, and robust client libraries for Python (`elasticsearch-py`, `elasticsearch-dsl`).

## Consequences

### Positive

- Accurate, high-quality Persian full-text search with proper linguistic handling.
- Rich faceted navigation that meets e-commerce UX expectations.
- Search performance is decoupled from database performance; each can be scaled independently.
- Flexible relevance tuning enables business-driven search ranking.
- Near-real-time indexing supports rapid catalog updates.

### Negative

- Introduces an additional infrastructure component that must be deployed, monitored, and maintained.
- Data must be synchronized between PostgreSQL (source of truth) and Elasticsearch (search projection). This introduces eventual consistency and requires a reliable sync mechanism (see ADR-009).
- Elasticsearch clusters require non-trivial memory and storage resources. JVM tuning and shard management add operational complexity.
- The query DSL has a steep learning curve compared to SQL.

### Mitigations

- We implement event-driven synchronization from PostgreSQL to Elasticsearch (see ADR-009) to keep indices current with minimal lag.
- We use Docker Compose with Elasticsearch for local development and managed Elasticsearch services in production to reduce operational burden.
- We build a search abstraction layer that encapsulates Elasticsearch query construction, making it easier to maintain and test.
- We configure monitoring and alerting for index health, query latency, and sync lag.
