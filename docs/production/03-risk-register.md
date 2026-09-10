# 03 — PRODUCTION RISK REGISTER & EXCEPTION MATRIX
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Standard:** Production Certification & Hardening Master v8  
**Date:** 2026-09-11  
**Status:** Monitored & Managed  

---

## 1. Production Risk Register

| Risk ID | Category | Description & Impact | Severity | Current Status | Mitigation / Resolution Strategy | Owner | Timeline |
|---|---|---|:---:|:---:|---|---|:---:|
| **RSK-SEC-001** | Security | Production secret leakage or weak placeholder JWT key | **P0** | **RESOLVED** | `settings.py` model_validator fails fast on startup if `JWT_SECRET_KEY` contains placeholders or is <24 chars | SecOps | Immediate |
| **RSK-CON-001** | Concurrency | Race condition causing inventory overselling under flash sales | **P0** | **RESOLVED** | PostgreSQL `SELECT ... FOR UPDATE` row locks in `reserve_stock`; validated by 100-txn concurrent test | Backend Lead | Immediate |
| **RSK-FIN-001** | Financial | Double-spending of digital wallet balances via parallel requests | **P0** | **RESOLVED** | Explicit wallet row-level locking + immutable ledger append; validated by concurrent debit test | FinOps | Immediate |
| **RSK-FIN-002** | Financial | Coupon usage count exceeded due to concurrent redemption | **P0** | **RESOLVED** | `apply_discount` locks coupon row with `FOR UPDATE` and verifies limits atomically before incrementing | FinOps | Immediate |
| **RSK-REL-001** | Reliability | Silent router loading failures causing partial API outages | **P0** | **RESOLVED** | Replaced silent pass block in `_include_routers` with fail-fast `RuntimeError` and comprehensive logging | Platform Lead| Immediate |
| **RSK-OPS-001** | Operational | Celery worker and beat containers inheriting HTTP 8000 healthcheck | **P1** | **RESOLVED** | Docker healthchecks updated to native `celery status` and process verification | DevOps / SRE | Immediate |
| **RSK-OPS-002** | Operational | Dual-write inconsistency between DB and Elasticsearch / Notifications | **P1** | **RESOLVED** | Transactional Outbox pattern implemented via `outbox_messages` table drained by Celery workers | Distributed Systems | In Progress |
| **RSK-SEC-002** | Security | Fallback to mock payment provider in live production environment | **P0** | **RESOLVED** | `provider_factory.py` raises `ValueError` if mock provider is requested under `ENVIRONMENT=production` | Security Lead| Immediate |
| **RSK-PAY-001** | Payments | Webhook replay attacks or duplicate callbacks causing duplicate captures | **P0** | **RESOLVED** | `payment_webhook_events` table enforces unique constraint on `(provider, event_id)` with row-level locks | Payments Lead| Immediate |
| **RSK-SEC-003** | Security | IDOR on payment inspection or card receipt submission | **P1** | **RESOLVED** | Injected order ownership validation on `get_payment` and `submit_card_receipt` | SecOps | Immediate |
| **RSK-EXT-001** | Operational | Third-party Iranian payment gateway latency and callback timeouts | **P1** | **MONITORED** | Asynchronous payment verification, 15-minute callback TTL, state machine transitions, timeout handling | Payments Lead| Active |
| **RSK-MED-001** | Media | Malicious file upload via unvalidated multipart payloads | **P2** | **MITIGATED** | Strict MIME type validation, file size caps, random UUID filenames, and MinIO storage isolation | Security Lead| Phase 13 |

---

## 2. Operational Exception Center (Failure Matrix)

| Exception Code | Severity | Trigger Condition | System Behavior & Action | Owner | SLA / Resolution Path |
|---|:---:|---|---|---|---|
| `PAYMENT_MISMATCH` | **P0** | Gateway callback amount differs from recorded order total | Reject verification, freeze transaction, alert FinOps, write audit log | FinOps Lead | Immediate halt; manual review |
| `PAYMENT_TIMEOUT` | **P1** | Customer fails to complete gateway redirect within 15 mins | Auto-expire payment intent, release inventory reservations, mark order canceled | Worker Engine | Automatic 15-minute cleanup job |
| `DUPLICATE_PAYMENT` | **P0** | Same gateway transaction ID received more than once | Idempotent response; prevent duplicate ledger credit or order confirmation | FinOps Lead | Reject duplicate; record duplicate event |
| `INVENTORY_CONFLICT` | **P1** | Two customers claim the last stock item concurrently | Row-lock serializes requests; 1st succeeds, 2nd receives 409 Conflict with Persian error | Inventory Lead | Immediate rejection (zero overselling) |
| `INVENTORY_NEGATIVE`| **P0** | Stock calculation attempts to decrease below zero | Invariant check raises `ValidationError`; transaction rolled back | Backend Lead | Database constraint violation prevention |
| `REFUND_FAILURE` | **P1** | Payment gateway rejects automated refund request | Log error, queue for administrative retry in ERP Approvals queue | FinOps Lead | Admin review within 4 hours |
| `SHIPPING_FAILURE` | **P2** | Third-party courier API times out or rejects tracking request | Mark shipment `PENDING_RETRY`; dispatch via outbox worker retry | Logistics Lead | Auto-retry with exponential backoff |
| `DUPLICATE_SHIPMENT`| **P1** | Redundant fulfillment dispatch attempt for confirmed order | Check `order.status`; reject dispatch if already `SHIPPED` | Logistics Lead | Idempotency guard on shipment creation |
| `SEARCH_INDEX_FAIL` | **P2** | Elasticsearch node temporarily unresponsive during catalog update | Store update in transactional outbox; worker retries up to 5 times | Search SRE | Background retry queue; zero data loss |
| `WEBHOOK_REPLAY` | **P1** | Incoming webhook payload with previously processed idempotency key | Acknowledge receipt with HTTP 200 without executing duplicate business logic | SecOps Lead | Strict idempotency deduplication |
