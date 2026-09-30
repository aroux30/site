# Clean-room operational capability and reconciliation contract

## Purpose and provenance

This design is an independent implementation for the local Iranian ecommerce platform. It adopts only general operational patterns identified during a review of an external public repository whose source has no declared reuse license. No external source code, schemas, tests, interface copy, assets, or provider adapters may be copied into this codebase.

The platform remains a FastAPI/SQLAlchemy backend with a Next.js frontend. PostgreSQL remains authoritative; all financial values remain integer Iranian rials; payment idempotency and atomic wallet mutations remain unchanged.

## Capability registry

The new `integrations` bounded context owns a backend-generated registry of customer-facing and operational integrations. It reports a conservative, secret-free capability record:

- `id`: stable namespaced identifier, such as `payment.zarinpal`.
- `category`: `payment`, `shipping`, `messaging`, `search`, `storage`, or `identity`.
- `display_name`: safe operator/customer label.
- `status`: `LIVE`, `BETA`, `MOCK`, `DISABLED`, `DEGRADED`, or `MAINTENANCE`.
- `configured`, `customer_visible`, and `available_to_customers` boolean indicators.
- `reason_code`: stable non-secret explanation, such as `not_configured`, `feature_disabled`, or `manual_approval`.
- `updated_at`: registry generation time.

Endpoints:

- `GET /api/v1/integrations/capabilities` returns only customer-safe records.
- `GET /api/v1/integrations/admin/capabilities` requires the existing `settings:read` permission and returns operator-safe records without credentials, merchant IDs, API URLs, tokens, stack traces, or raw environment values.

Status must be conservative. An external provider with configuration present but no verified runtime health must not be labelled `LIVE`; use `BETA` or `DEGRADED` with a reason code. The registry is informational in this release: it must not change checkout authorization, provider selection, payment verification, order transitions, refunds, or wallet mutations.

## Reconciliation findings

The audit bounded context owns durable, deduplicated reconciliation findings and a scheduled read-only scanner. Finding storage is additive and must be migrated through Alembic; it is not a replacement for audit logs or the current in-memory operational exception center.

Each finding records a unique dedupe key, finding type, severity, lifecycle status, entity reference, optional expected/actual integer-rial amounts, safe JSON details, first/last detection timestamps, occurrence count, and resolution metadata.

Initial detector set is restricted to conditions provable from existing local models:

1. payment amount differs from its authoritative order total;
2. a completed payment has an order in an incompatible unpaid state;
3. successful refunds for one payment exceed the payment amount;
4. a webhook event remains unprocessed beyond a documented grace period.

The scanner may read business records and write only reconciliation-finding rows and audit trail entries. It must never call a gateway, retry a callback, capture/refund/charge money, create a wallet transaction, alter payment/order/refund rows, alter inventory, or invoke an external provider.

Endpoints:

- `GET /api/v1/audit/admin/reconciliation/findings` requires `audit:read`.
- `GET /api/v1/audit/admin/reconciliation/summary` requires `audit:read`.
- `POST /api/v1/audit/admin/reconciliation/run` requires `audit:write` and executes the same read-only scanner.
- resolution or dismissal endpoints require `audit:write`, persist nonempty operator notes, and never change the underlying financial record.

A Celery Beat task may run the scanner on a conservative schedule. The Celery task must be registered through the existing `application.tasks` discovery convention and be idempotent under at-least-once execution.

## Frontend requirements

Admin screens must use the new backend contracts, remain Persian RTL, work at mobile and desktop breakpoints, have keyboard-accessible controls, and clearly distinguish unavailable data from empty data. They must not create sample financial findings or claim an external integration is live based only on a locally entered key.

The admin settings and exception-center surfaces should link to or consume the new data where relevant. Existing payment and configuration forms remain functional; no client-side capability value is treated as an authority for financial behavior.

## Verification boundaries

- Test every capability status rule and ensure public output excludes sensitive values.
- Test reconciliation detector deduplication, lifecycle actions, permission checks, and the invariant that financial entities are not mutated.
- Test router registration and Celery Beat task registration.
- Type-check and test all frontend changes.
- Run focused backend unit tests plus the existing worker-registration regression test before integration.
