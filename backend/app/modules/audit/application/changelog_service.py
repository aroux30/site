"""Query service for the field-level change log (ERP feature #9).

Reads :class:`~app.modules.audit.domain.entity_changelog.EntityChangeLog`
rows written by the capture hook in ``application.change_tracking``. The
service is read-only: capture is the hook's job, this module only answers
"what changed, when, and by whom".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.modules.audit.domain.entity_changelog import EntityChangeLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_changes(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    field: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[EntityChangeLog], int]:
    """Paginated change-log query, newest first.

    ``field`` filters rows that contain that field anywhere in the diff
    (JSONB containment), which is how "who touched price?" is answered.
    """
    stmt = select(EntityChangeLog)
    count_stmt = select(func.count()).select_from(EntityChangeLog)

    conditions = []
    if entity_type:
        conditions.append(EntityChangeLog.entity_type == entity_type)
    if entity_id:
        conditions.append(EntityChangeLog.entity_id == str(entity_id))
    if actor_id:
        conditions.append(EntityChangeLog.actor_id == actor_id)
    if field:
        # JSONB containment: `changed_fields @> '[{"field": "<name>"}]'`
        conditions.append(
            EntityChangeLog.changed_fields.contains([{"field": field}])
        )
    if from_date:
        conditions.append(EntityChangeLog.occurred_at >= from_date)
    if to_date:
        conditions.append(EntityChangeLog.occurred_at <= to_date)

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = (
        stmt.order_by(EntityChangeLog.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), int(total)


async def get_change(db: AsyncSession, change_id: uuid.UUID) -> EntityChangeLog | None:
    """One change row by id, or ``None``."""
    return (
        await db.execute(
            select(EntityChangeLog).where(EntityChangeLog.id == change_id)
        )
    ).scalar_one_or_none()


async def entity_history(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 200,
) -> list[EntityChangeLog]:
    """Full per-record timeline, oldest first (reads like a story)."""
    rows = (
        await db.execute(
            select(EntityChangeLog)
            .where(
                EntityChangeLog.entity_type == entity_type,
                EntityChangeLog.entity_id == str(entity_id),
            )
            .order_by(EntityChangeLog.occurred_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def tracked_entity_types(db: AsyncSession) -> list[dict[str, Any]]:
    """Entity types that actually have change rows, with their row counts.

    Driven by data rather than the registry: the registry lists what *could*
    be tracked; this lists what *has been* — the useful distinction when an
    operator wonders why a product's history is empty.
    """
    rows = (
        await db.execute(
            select(
                EntityChangeLog.entity_type,
                func.count().label("row_count"),
                func.max(EntityChangeLog.occurred_at).label("last_change_at"),
            )
            .group_by(EntityChangeLog.entity_type)
            .order_by(func.count().desc())
        )
    ).all()
    return [
        {
            "entity_type": r.entity_type,
            "row_count": int(r.row_count),
            "last_change_at": r.last_change_at,
        }
        for r in rows
    ]
