"""Audit logging service.

Provides a fire-and-forget helper that writes an :class:`AuditLog` row
for every security-relevant or admin action.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.audit.domain.models import AuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


async def log_action(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    action: str,
    resource: str,
    resource_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist an audit-log entry.

    This function is intentionally not transactional on its own – it
    participates in the caller's session so that the audit row is
    committed together with the business operation.
    """
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        extra_data=extra_data,
    )
    db.add(entry)
    await db.flush()

    await logger.ainfo(
        "audit_log_created",
        audit_id=str(entry.id),
        actor_id=str(actor_id) if actor_id else None,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
    )
    return entry


async def get_audit_logs(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    resource: str | None = None,
    resource_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuditLog], int]:
    """Query audit logs with optional filters and pagination.

    Returns a tuple of ``(items, total_count)``.
    """
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource is not None:
        stmt = stmt.where(AuditLog.resource == resource)
        count_stmt = count_stmt.where(AuditLog.resource == resource)
    if resource_id is not None:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
        count_stmt = count_stmt.where(AuditLog.resource_id == resource_id)
    if from_date is not None:
        stmt = stmt.where(AuditLog.created_at >= from_date)
        count_stmt = count_stmt.where(AuditLog.created_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(AuditLog.created_at <= to_date)
        count_stmt = count_stmt.where(AuditLog.created_at <= to_date)

    # Total count
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginated results
    offset = (page - 1) * page_size
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total
