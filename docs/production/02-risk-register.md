# 02 — RISK REGISTER & MITIGATION AUDIT
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-10  

---

| Risk ID | Category | Description | Inherent Severity | Mitigation Implemented | Residual Risk | Status |
|---|---|---|:---:|---|:---:|:---:|
| **RSK-001** | Financial | Floating-point rounding errors in pricing or cart calculations | HIGH | 100% integer arithmetic in Rials (`BigInteger`). Conversion to Toman only at display boundary. | NONE | ✅ MITIGATED |
| **RSK-002** | Inventory | Overselling products under concurrent high-volume traffic | CRITICAL | Row-level locking (`SELECT ... FOR UPDATE`) in `inventory_service.py`. Verified by 100 concurrent buyer test. | NONE | ✅ MITIGATED |
| **RSK-003** | Financial | Double-spending of digital wallet balances | CRITICAL | `with_for_update()` applied on Wallet row before debit; ledger verification prevents negative balances. | NONE | ✅ MITIGATED |
| **RSK-004** | Security | Token theft via Cross-Site Scripting (XSS) | HIGH | Access and refresh tokens stored exclusively in `HttpOnly Secure SameSite=Lax` cookies. JavaScript has no access. | LOW | ✅ MITIGATED |
| **RSK-005** | Reliability | Silent failure during router loading on startup | HIGH | Replaced `except: pass` with fail-fast `raise RuntimeError(...)`. Startup halts immediately on router defect. | NONE | ✅ MITIGATED |
| **RSK-006** | Data Integrity | Dual-write inconsistency between PostgreSQL and Elasticsearch | MEDIUM | Transactional Outbox pattern (`outbox_messages`) ensures database commits before Celery worker syncs search index. | LOW | ✅ MITIGATED |
| **RSK-007** | Payment | Duplicate payment processing on network retry | HIGH | `Idempotency-Key` unique constraint on payments and orders deduplicates replayed webhooks and requests. | NONE | ✅ MITIGATED |
| **RSK-008** | Security | Path traversal and malicious file upload via media endpoint | HIGH | `_sanitize_filename` strips traversal characters; MIME whitelist enforced; file size capped at 10MB. | LOW | ✅ MITIGATED |
| **RSK-009** | Performance | Heavy client-side JavaScript on mobile devices causing LCP degradation | MEDIUM | Rearchitected homepage to Server Component Shell with deferred Client Islands. Bundle reduced by 83%. | LOW | ✅ MITIGATED |
| **RSK-010** | Operational | Server host resource exhaustion (3.7 GB RAM VPS) | MEDIUM | Redis memory capped; Elasticsearch JVM constrained to 256MB; n8n container excluded to preserve memory. | MEDIUM | ⚠️ MONITORED |
