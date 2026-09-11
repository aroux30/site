"""Audit-log admin API routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions
from app.modules.audit.application.audit_service import get_audit_logs
from app.modules.audit.application.exception_center_service import exception_center
from app.modules.audit.domain.operational_exceptions import (
    ExceptionSeverity,
    ExceptionStatus,
)
from app.modules.audit.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    ExceptionAssignRequest,
    ExceptionResolveRequest,
    OperationalExceptionResponse,
)

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
