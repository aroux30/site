"""Audit-log admin API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.audit.application.audit_service import get_audit_logs
from app.modules.audit.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter()


@router.get(
    "/admin/audit-logs",
    response_model=AuditLogListResponse,
    dependencies=[Depends(RequirePermissions("audit:read"))],
    summary="List audit logs (admin)",
)
async def list_audit_logs(
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor ID"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    resource: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[uuid.UUID] = Query(None, description="Filter by resource ID"),
    from_date: Optional[datetime] = Query(None, description="From date (ISO 8601)"),
    to_date: Optional[datetime] = Query(None, description="To date (ISO 8601)"),
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
