"""Audit logging service.

Provides a fire-and-forget helper that writes an :class:`AuditLog` row
for every security-relevant or admin action.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.audit.domain.models import AuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def _ambient_request_id() -> str | None:
    """The current request's correlation id, from the logging context.

    ``RequestIDMiddleware`` binds ``request_id``/``correlation_id`` to
    structlog's contextvars for the whole request; the worker's task-prerun
    hook restores them from the message headers. Reading it here means every
    audit row joins its originating request without touching 40+ call sites —
    until 2026-10-06 the column existed but no caller ever passed it, so
    "which request produced this log?" was unanswerable for all 10k rows.
    """
    try:
        context = structlog.contextvars.get_contextvars()
    except Exception:  # pragma: no cover - defensive
        return None
    request_id = context.get("request_id") or context.get("correlation_id")
    return str(request_id) if request_id else None


def _ambient_ip() -> str | None:
    """The bound request's client IP, if any (see actor_context)."""
    from app.core.security.actor_context import current_ip_address

    try:
        return current_ip_address()
    except Exception:  # pragma: no cover - defensive
        return None


def _ambient_user_agent() -> str | None:
    """The bound request's User-Agent, if any (see actor_context)."""
    from app.core.security.actor_context import current_user_agent

    try:
        return current_user_agent()
    except Exception:  # pragma: no cover - defensive
        return None


def _jsonify(value: Any) -> Any:
    """Convert a value so PostgreSQL's default JSONB serializer accepts it.

    ORM snapshots routinely carry UUID, datetime and Decimal objects; those
    crash ``json.dumps`` at flush time (500 on the whole admin action) even
    though the values themselves are harmless, so they are converted to their
    canonical text forms. Any other unserializable type raises loudly here —
    the audit row joins the caller's transaction, so a genuinely bad value
    fails the whole action rather than silently corrupting the audit trail
    with a lossy ``str()`` stand-in.
    """
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        # NaN/Infinity are not valid JSON; emit null like Python's default
        # encoder does for the DB write, instead of a string "nan" that
        # corrupts numeric data in the trail.
        return None if (value != value or value in (float("inf"), float("-inf"))) else value
    if isinstance(value, (uuid.UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(v) for v in value]
    raise TypeError(
        f"Audit snapshot value of type {type(value).__name__} is not JSON-serializable; "
        "convert it to str/UUID/datetime at the call site"
    )


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
        before=_jsonify(before),
        after=_jsonify(after),
        # An explicit value still wins; otherwise inherit the ambient one so
        # the row carries its request details without any caller work. Until
        # 2026-10-06 only the auth routes forwarded IP/UA — every other
        # writer (CMS, RBAC, settings) recorded nothing, and request_id was
        # empty on all 10k rows because no caller passed it at all.
        ip_address=ip_address or _ambient_ip(),
        user_agent=user_agent or _ambient_user_agent(),
        request_id=request_id or _ambient_request_id(),
        extra_data=_jsonify(extra_data),
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


async def resolve_actor_identities(
    db: AsyncSession,
    actor_ids: Iterable[uuid.UUID | None],
) -> dict[uuid.UUID, dict[str, str | None]]:
    """Batch-resolve actor ids to human identity for display.

    One query for a whole page of rows, never one per row. The display name
    falls back to the profile's first+last name, then the phone — the admin
    reviewer needs *a* recognizable handle, and the phone is the login
    identity every operator already knows.

    Returns ``{actor_id: {"name": ..., "phone": ...}}``; an id with no
    surviving user row (deleted account, ``ondelete=SET NULL``) is simply
    absent, and the caller renders the raw id as before.
    """
    from sqlalchemy import select as _select

    from app.modules.users.domain.models import User, UserProfile

    wanted = {aid for aid in actor_ids if aid is not None}
    if not wanted:
        return {}

    stmt = (
        _select(User.id, User.phone, UserProfile.first_name, UserProfile.last_name, UserProfile.display_name)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(User.id.in_(wanted))
    )
    result: dict[uuid.UUID, dict[str, str | None]] = {}
    for user_id, phone, first_name, last_name, display_name in await db.execute(stmt):
        name = display_name or " ".join(
            part for part in (first_name, last_name) if part
        ) or None
        result[user_id] = {"name": name, "phone": phone}
    return result


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
    # Substring match: operators type a prefix like "cms_page" and expect to
    # see "cms_page.created" too — exact equality returned nothing.
    if action is not None:
        pattern = f"%{action.strip()}%"
        stmt = stmt.where(AuditLog.action.ilike(pattern))
        count_stmt = count_stmt.where(AuditLog.action.ilike(pattern))
    if resource is not None:
        pattern = f"%{resource.strip()}%"
        stmt = stmt.where(AuditLog.resource.ilike(pattern))
        count_stmt = count_stmt.where(AuditLog.resource.ilike(pattern))
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
