"""Audit-log admin API routes."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.audit.application.audit_service import get_audit_logs, log_action
from app.modules.audit.application.changelog_service import (
    entity_history,
    get_change,
    list_changes,
    tracked_entity_types,
)
from app.modules.audit.application.exception_center_service import exception_center
from app.modules.audit.application.lifecycle_auditor import audit_order_lifecycle
from app.modules.audit.application.reconciliation_service import (
    dismiss_finding,
    list_findings,
    resolve_finding,
    scan,
    summarize_findings,
)
from app.modules.audit.domain.operational_exceptions import (
    ExceptionSeverity,
    ExceptionStatus,
)
from app.modules.audit.domain.reconciliation import (
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.modules.audit.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    EntityChangeListResponse,
    EntityChangeResponse,
    EntityHistoryResponse,
    ExceptionAssignRequest,
    ExceptionResolveRequest,
    OperationalExceptionResponse,
    TrackedEntitySummary,
)
from app.modules.audit.schemas.reconciliation import (
    FindingResolveRequest,
    LifecycleAuditRunResponse,
    ReconciliationFindingListResponse,
    ReconciliationFindingResponse,
    ReconciliationRunResponse,
    ReconciliationSummaryResponse,
)

if TYPE_CHECKING:
    from app.modules.audit.domain.reconciliation import ReconciliationFinding

router = APIRouter()


@router.get(
    "/admin/audit-logs",
    response_model=AuditLogListResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="List audit logs (admin)",
)
async def list_audit_logs(
    actor_id: uuid.UUID | None = Query(None, description="Filter by actor ID"),
    action: str | None = Query(None, description="Filter by action name"),
    resource: str | None = Query(None, description="Filter by resource type"),
    resource_id: uuid.UUID | None = Query(None, description="Filter by resource ID"),
    from_date: datetime | None = Query(None, description="From date (ISO 8601)"),
    to_date: datetime | None = Query(None, description="To date (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Return a paginated list of audit-log entries.

    Requires the ``audit:read`` permission.
    """
    items, total = await get_audit_logs(
        db,
        actor_id=actor_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ══════════════════════════════════════════════════════════════════════════
# Operational Exception Center Admin Endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/admin/exceptions",
    response_model=list[OperationalExceptionResponse],
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="List active operational anomalies (admin Exception Center)",
)
async def list_operational_exceptions(
    severity: str | None = Query(
        None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"
    ),
    status: str | None = Query(
        None, description="Filter by status: OPEN, INVESTIGATING, RESOLVED, DISMISSED"
    ),
) -> list[OperationalExceptionResponse]:
    sev = ExceptionSeverity(severity) if severity in [s.value for s in ExceptionSeverity] else None
    stat = ExceptionStatus(status) if status in [s.value for s in ExceptionStatus] else None
    items = exception_center.list_exceptions(severity=sev, status=stat)
    return [
        OperationalExceptionResponse(
            id=i.id,
            exception_type=i.exception_type.value,
            severity=i.severity.value,
            status=i.status.value,
            entity_type=i.entity_type,
            entity_id=i.entity_id,
            details=i.details,
            created_at=i.created_at,
            owner_id=i.owner_id,
            resolved_at=i.resolved_at,
            resolution_notes=i.resolution_notes,
        )
        for i in items
    ]


@router.patch(
    "/admin/exceptions/{exception_id}/assign",
    response_model=OperationalExceptionResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Assign operational anomaly to an owner (admin)",
)
async def assign_operational_exception(
    exception_id: uuid.UUID,
    body: ExceptionAssignRequest,
) -> OperationalExceptionResponse:
    item = exception_center.assign_owner(exception_id, body.owner_id)
    if not item:
        raise NotFoundError("OperationalException")
    return OperationalExceptionResponse(
        id=item.id,
        exception_type=item.exception_type.value,
        severity=item.severity.value,
        status=item.status.value,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        details=item.details,
        created_at=item.created_at,
        owner_id=item.owner_id,
        resolved_at=item.resolved_at,
        resolution_notes=item.resolution_notes,
    )


@router.patch(
    "/admin/exceptions/{exception_id}/resolve",
    response_model=OperationalExceptionResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Resolve operational anomaly with resolution notes (admin)",
)
async def resolve_operational_exception(
    exception_id: uuid.UUID,
    body: ExceptionResolveRequest,
) -> OperationalExceptionResponse:
    item = exception_center.resolve_exception(exception_id, body.resolution_notes)
    if not item:
        raise NotFoundError("OperationalException")
    return OperationalExceptionResponse(
        id=item.id,
        exception_type=item.exception_type.value,
        severity=item.severity.value,
        status=item.status.value,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        details=item.details,
        created_at=item.created_at,
        owner_id=item.owner_id,
        resolved_at=item.resolved_at,
        resolution_notes=item.resolution_notes,
    )


@router.patch(
    "/admin/exceptions/{exception_id}/dismiss",
    response_model=OperationalExceptionResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Dismiss operational anomaly with a reason (admin)",
)
async def dismiss_operational_exception(
    exception_id: uuid.UUID,
    body: ExceptionResolveRequest,
) -> OperationalExceptionResponse:
    item = exception_center.dismiss_exception(exception_id, body.resolution_notes)
    if not item:
        raise NotFoundError("OperationalException")
    return OperationalExceptionResponse(
        id=item.id,
        exception_type=item.exception_type.value,
        severity=item.severity.value,
        status=item.status.value,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        details=item.details,
        created_at=item.created_at,
        owner_id=item.owner_id,
        resolved_at=item.resolved_at,
        resolution_notes=item.resolution_notes,
    )


# ══════════════════════════════════════════════════════════════════════════
# Payment Reconciliation Admin Endpoints
#
# Durable reconciliation findings produced by the read-only scanner. Reads
# require `audit:read`; running the scanner and changing a finding's lifecycle
# require `audit:write`. None of these endpoints touch the underlying payment,
# order, refund or webhook records — resolution records an operator decision
# and nothing else.
# ══════════════════════════════════════════════════════════════════════════


def _parse_enum[EnumT: enum.Enum](
    raw: str | None, enum_cls: type[EnumT], field: str
) -> EnumT | None:
    """Parse an optional query filter, rejecting unknown values loudly.

    Silently ignoring a typo'd filter would return an unfiltered list that
    looks like a successful, empty-result query — the exact confusion the
    admin screen must not create.
    """
    if raw is None:
        return None
    try:
        return enum_cls(raw)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_cls)
        raise ValidationError(
            detail=f"Invalid {field} filter '{raw}'. Allowed values: {allowed}",
            error_code="INVALID_RECONCILIATION_FILTER",
        ) from exc


def _finding_response(finding: ReconciliationFinding) -> ReconciliationFindingResponse:
    return ReconciliationFindingResponse(
        id=finding.id,
        dedupe_key=finding.dedupe_key,
        finding_type=finding.finding_type.value,
        severity=finding.severity.value,
        status=finding.status.value,
        entity_type=finding.entity_type,
        entity_id=finding.entity_id,
        expected_amount=finding.expected_amount,
        actual_amount=finding.actual_amount,
        details=finding.details,
        first_detected_at=finding.first_detected_at,
        last_detected_at=finding.last_detected_at,
        occurrence_count=finding.occurrence_count,
        resolved_at=finding.resolved_at,
        resolved_by=finding.resolved_by,
        resolution_notes=finding.resolution_notes,
        created_at=finding.created_at,
    )


@router.get(
    "/admin/reconciliation/findings",
    response_model=ReconciliationFindingListResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="List durable reconciliation findings (admin)",
)
async def list_reconciliation_findings(
    status: str | None = Query(
        None, description="Filter by status: OPEN, RESOLVED, DISMISSED"
    ),
    finding_type: str | None = Query(
        None,
        description=(
            "Filter by type: PAYMENT_AMOUNT_MISMATCH, PAYMENT_ORDER_STATUS_MISMATCH, "
            "REFUND_TOTAL_EXCEEDS_PAYMENT, WEBHOOK_UNPROCESSED"
        ),
    ),
    severity: str | None = Query(
        None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> ReconciliationFindingListResponse:
    """Return a paginated list of reconciliation findings.

    Requires the ``audit:read`` permission.
    """
    items, total = await list_findings(
        db,
        status=_parse_enum(status, FindingStatus, "status"),
        finding_type=_parse_enum(finding_type, FindingType, "finding_type"),
        severity=_parse_enum(severity, FindingSeverity, "severity"),
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return ReconciliationFindingListResponse(
        items=[_finding_response(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/admin/reconciliation/summary",
    response_model=ReconciliationSummaryResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="Reconciliation finding counts (admin)",
)
async def reconciliation_summary(
    db: AsyncSession = Depends(get_db),
) -> ReconciliationSummaryResponse:
    """Return finding counts by status, severity and type.

    Requires the ``audit:read`` permission.
    """
    summary = await summarize_findings(db)
    return ReconciliationSummaryResponse(**summary)


@router.post(
    "/admin/reconciliation/run",
    response_model=ReconciliationRunResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Run the read-only reconciliation scanner (admin)",
)
async def run_reconciliation_scan(
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ReconciliationRunResponse:
    """Execute the same read-only scanner the scheduled task runs.

    Requires the ``audit:write`` permission. The run writes reconciliation
    findings and an audit-trail entry for the manual invocation; it reads
    payments, orders, refunds and webhook events without mutating them.
    """
    result = await scan(db)

    await log_action(
        db,
        actor_id=actor_id,
        action="RECONCILIATION_SCAN_RUN",
        resource="reconciliation_finding",
        after={
            "detected": result.detected,
            "created": result.created,
            "updated": result.updated,
            "truncated": result.truncated,
        },
    )

    return ReconciliationRunResponse(
        detected=result.detected,
        created=result.created,
        updated=result.updated,
        truncated=result.truncated,
        scanned_at=datetime.now(UTC),
    )


@router.post(
    "/admin/reconciliation/audit-lifecycle",
    response_model=LifecycleAuditRunResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Run the read-only order lifecycle audit (admin)",
)
async def run_lifecycle_audit(
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> LifecycleAuditRunResponse:
    """Execute the same read-only lifecycle audit the scheduled task runs.

    Requires the ``audit:write`` permission. The audit reads orders, shipments,
    refunds and payments and derives the payment/fulfilment/return axes; every
    statement is a ``SELECT``. Findings are the only writes, plus the
    audit-trail entry recording this manual invocation. No order, shipment,
    refund or payment row is modified.
    """
    result = await audit_order_lifecycle(db)

    await log_action(
        db,
        actor_id=actor_id,
        action="ORDER_LIFECYCLE_AUDIT_RUN",
        resource="reconciliation_finding",
        after={
            "detected": result.detected,
            "created": result.created,
            "updated": result.updated,
            "truncated": result.truncated,
        },
    )

    return LifecycleAuditRunResponse(
        detected=result.detected,
        created=result.created,
        updated=result.updated,
        truncated=result.truncated,
        audited_at=datetime.now(UTC),
    )


@router.patch(
    "/admin/reconciliation/findings/{finding_id}/resolve",
    response_model=ReconciliationFindingResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Resolve a reconciliation finding with operator notes (admin)",
)
async def resolve_reconciliation_finding(
    finding_id: uuid.UUID,
    body: FindingResolveRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ReconciliationFindingResponse:
    """Mark a finding RESOLVED. Requires ``audit:write`` and a non-empty note.

    Only the finding row changes; the referenced financial record is untouched.
    """
    finding = await resolve_finding(
        db,
        finding_id=finding_id,
        notes=body.resolution_notes,
        actor_id=actor_id,
    )
    if finding is None:
        raise NotFoundError("ReconciliationFinding")
    return _finding_response(finding)


@router.patch(
    "/admin/reconciliation/findings/{finding_id}/dismiss",
    response_model=ReconciliationFindingResponse,
    dependencies=[Depends(RequirePermissions("audit:write"))],
    summary="Dismiss a reconciliation finding with a reason (admin)",
)
async def dismiss_reconciliation_finding(
    finding_id: uuid.UUID,
    body: FindingResolveRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ReconciliationFindingResponse:
    """Mark a finding DISMISSED. Requires ``audit:write`` and a non-empty reason.

    Only the finding row changes; the referenced financial record is untouched.
    """
    finding = await dismiss_finding(
        db,
        finding_id=finding_id,
        notes=body.resolution_notes,
        actor_id=actor_id,
    )
    if finding is None:
        raise NotFoundError("ReconciliationFinding")
    return _finding_response(finding)


# ── Field-level change log (ERP feature #9) ──────────────────────────────────
#
# Static paths (``/admin/audit/changes/entities``) are declared BEFORE the
# ``/admin/audit/changes/{change_id}`` parameterized route so FastAPI never
# tries to parse "entities" as a UUID.

_CHANGE_PAGE_SIZE_MAX = 100


@router.get(
    "/admin/audit/changes/entities",
    response_model=list[TrackedEntitySummary],
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="Entity types with captured field-level changes (admin)",
)
async def list_tracked_entities(
    db: AsyncSession = Depends(get_db),
) -> list[TrackedEntitySummary]:
    """Return entity types that have change rows, most-changed first.

    Data-driven: lists what *has been* captured, not what the registry could
    capture — the useful distinction when a product's history is unexpectedly
    empty. Requires ``audit:read``.
    """
    rows = await tracked_entity_types(db)
    return [TrackedEntitySummary(**row) for row in rows]


@router.get(
    "/admin/audit/changes",
    response_model=EntityChangeListResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="List field-level entity changes (admin)",
)
async def list_entity_changes(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity id"),
    actor_id: uuid.UUID | None = Query(None, description="Filter by actor ID"),
    field: str | None = Query(None, description="Only changes touching this field"),
    from_date: datetime | None = Query(None, description="From date (ISO 8601)"),
    to_date: datetime | None = Query(None, description="To date (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=_CHANGE_PAGE_SIZE_MAX, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> EntityChangeListResponse:
    """Paginated field-level change log, newest first. Requires ``audit:read``."""
    items, total = await list_changes(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        field=field,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return EntityChangeListResponse(
        items=[EntityChangeResponse.model_validate(row) for row in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/admin/audit/changes/{change_id}",
    response_model=EntityChangeResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="Get one field-level change row (admin)",
)
async def get_entity_change(
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EntityChangeResponse:
    """One change row by id. Requires ``audit:read``."""
    row = await get_change(db, change_id)
    if row is None:
        raise NotFoundError("EntityChangeLog")
    return EntityChangeResponse.model_validate(row)


@router.get(
    "/admin/audit/entities/{entity_type}/{entity_id}/history",
    response_model=EntityHistoryResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="Per-record change timeline (admin)",
)
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> EntityHistoryResponse:
    """Full change timeline for one record, oldest first. Requires ``audit:read``."""
    rows = await entity_history(db, entity_type=entity_type, entity_id=entity_id)
    return EntityHistoryResponse(
        entity_type=entity_type,
        entity_id=str(entity_id),
        items=[EntityChangeResponse.model_validate(row) for row in rows],
    )
