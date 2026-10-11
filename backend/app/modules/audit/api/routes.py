"""Audit-log admin API routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions
from app.modules.audit.application.audit_service import (
    get_audit_logs,
    resolve_actor_identities,
)
from app.modules.audit.application.changelog_service import (
    entity_history,
    get_change,
    list_changes,
    tracked_entity_types,
)
from app.modules.audit.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    EntityChangeListResponse,
    EntityChangeResponse,
    EntityHistoryResponse,
    TrackedEntitySummary,
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
    # Resolve actor names for the whole page in one query: a reviewer must
    # read "مریم احمدی" rather than "کاربر عامل: 5ae8aeaa-…".
    identities = await resolve_actor_identities(db, (i.actor_id for i in items))
    responses = []
    for item in items:
        resp = AuditLogResponse.model_validate(item)
        identity = identities.get(item.actor_id) if item.actor_id else None
        if identity:
            resp.actor_name = identity["name"]
            resp.actor_phone = identity["phone"]
        responses.append(resp)
    return AuditLogListResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


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
    identities = await resolve_actor_identities(db, (row.actor_id for row in items))
    responses = []
    for row in items:
        resp = EntityChangeResponse.model_validate(row)
        identity = identities.get(row.actor_id) if row.actor_id else None
        if identity:
            resp.actor_name = identity["name"]
            resp.actor_phone = identity["phone"]
        responses.append(resp)
    return EntityChangeListResponse(
        items=responses,
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
    resp = EntityChangeResponse.model_validate(row)
    if row.actor_id:
        identities = await resolve_actor_identities(db, [row.actor_id])
        identity = identities.get(row.actor_id)
        if identity:
            resp.actor_name = identity["name"]
            resp.actor_phone = identity["phone"]
    return resp


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
    identities = await resolve_actor_identities(db, (row.actor_id for row in rows))
    responses = []
    for row in rows:
        resp = EntityChangeResponse.model_validate(row)
        identity = identities.get(row.actor_id) if row.actor_id else None
        if identity:
            resp.actor_name = identity["name"]
            resp.actor_phone = identity["phone"]
        responses.append(resp)
    return EntityHistoryResponse(
        entity_type=entity_type,
        entity_id=str(entity_id),
        items=responses,
    )
