"""Entry revisions + scheduling + trash for dynamic content entries.

Mirrors the cms_page_service lifecycle (revisions snapshot on content change,
restore records itself as a new revision, trash-first delete, due-schedule
processor for the Celery beat) so dynamic entries meet the same editorial
standard as pages.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.content.application import builder_service
from app.modules.content.domain.builder import ContentEntry, ContentType
from app.modules.content.domain.entry_extras import ContentEntryRevision
from app.modules.content.domain.models import PageStatus

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _snapshot(entry: ContentEntry, *, created_by: uuid.UUID | None) -> ContentEntryRevision:
    return ContentEntryRevision(
        entry_id=entry.id,
        revision_number=entry.revision_number,
        data=entry.data,
        status=entry.status.value if isinstance(entry.status, PageStatus) else str(entry.status),
        created_by=created_by,
    )


async def create_entry_v2(
    db,
    type_slug: str,
    data: dict[str, Any],
    *,
    status: PageStatus = PageStatus.DRAFT,
    locale: str = "fa",
    scheduled_publish_at: datetime | None = None,
    author_id: uuid.UUID | None = None,
) -> ContentEntry:
    """Create with first revision snapshot and optional schedule."""
    entry = await builder_service.create_entry(
        db, type_slug, data, status=status, locale=locale
    )
    entry.revision_number = 1
    entry.scheduled_publish_at = scheduled_publish_at
    if status == PageStatus.PUBLISHED:
        entry.published_at = datetime.now(UTC)
    db.add(_snapshot(entry, created_by=author_id))
    await db.flush()
    return entry


async def update_entry_v2(
    db,
    entry_id: uuid.UUID,
    data: dict[str, Any],
    *,
    status: PageStatus | None = None,
    scheduled_publish_at: datetime | None = None,
    scheduled_unpublish_at: datetime | None = None,
    editor_id: uuid.UUID | None = None,
) -> ContentEntry:
    entry = await db.get(ContentEntry, entry_id)
    if not entry or entry.deleted_at is not None:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")

    old_status = entry.status
    before_data = dict(entry.data)
    await builder_service.update_entry(db, entry_id, data, status=status)
    if scheduled_publish_at is not None:
        entry.scheduled_publish_at = scheduled_publish_at
    if scheduled_unpublish_at is not None:
        entry.scheduled_unpublish_at = scheduled_unpublish_at
    if entry.status == PageStatus.PUBLISHED and entry.published_at is None:
        entry.published_at = datetime.now(UTC)
    if entry.status == PageStatus.PUBLISHED:
        entry.scheduled_publish_at = None
    elif entry.status == PageStatus.DRAFT:
        entry.scheduled_unpublish_at = None

    if entry.data != before_data:
        entry.revision_number = (entry.revision_number or 1) + 1
        await db.flush()
        db.add(_snapshot(entry, created_by=editor_id))

    await db.flush()
    if entry.status != old_status:
        await _emit(db, "page.published" if entry.status == PageStatus.PUBLISHED else "page.unpublished", entry)
    return entry


async def list_revisions(db, entry_id: uuid.UUID, *, limit: int = 50) -> list[ContentEntryRevision]:
    entry = await db.get(ContentEntry, entry_id)
    if not entry:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")
    stmt = (
        select(ContentEntryRevision)
        .where(ContentEntryRevision.entry_id == entry_id)
        .order_by(ContentEntryRevision.revision_number.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def restore_revision(
    db, entry_id: uuid.UUID, revision_number: int, *, editor_id: uuid.UUID | None = None
) -> ContentEntry:
    entry = await db.get(ContentEntry, entry_id)
    if not entry:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")
    rev = (
        await db.execute(
            select(ContentEntryRevision).where(
                ContentEntryRevision.entry_id == entry_id,
                ContentEntryRevision.revision_number == revision_number,
            )
        )
    ).scalar_one_or_none()
    if not rev:
        raise NotFoundError("ContentEntryRevision", f"Revision {revision_number} not found")

    # Data was validated when written; restoring bypasses re-validation only if
    # the type schema changed since — re-validate against the current schema.
    ct = (
        await db.execute(select(ContentType).where(ContentType.id == entry.content_type_id))
    ).scalar_one()
    entry.data = builder_service.validate_entry_data(ct.fields, dict(rev.data))
    entry.revision_number = (entry.revision_number or 1) + 1
    await db.flush()
    db.add(_snapshot(entry, created_by=editor_id))
    await db.flush()
    logger.info("content_entry_restored", entry_id=str(entry_id), from_rev=revision_number)
    return entry


async def trash_entry(db, entry_id: uuid.UUID) -> None:
    entry = await db.get(ContentEntry, entry_id)
    if not entry:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")
    if entry.deleted_at is None:
        entry.deleted_at = datetime.now(UTC)
        await db.flush()
        logger.info("content_entry_trashed", entry_id=str(entry_id))


async def restore_entry(db, entry_id: uuid.UUID) -> ContentEntry:
    entry = await db.get(ContentEntry, entry_id)
    if not entry or entry.deleted_at is None:
        raise NotFoundError("ContentEntry", f"Trashed entry {entry_id} not found")
    entry.deleted_at = None
    await db.flush()
    return entry


async def hard_delete_entry(db, entry_id: uuid.UUID) -> None:
    entry = await db.get(ContentEntry, entry_id)
    if not entry:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")
    if entry.deleted_at is None:
        raise ValidationError("ورودی ابتدا باید به سطل زباله منتقل شود")
    await db.delete(entry)
    await db.flush()


async def process_scheduled_entries(db) -> dict[str, int]:
    """Publish/unpublish due entries (Celery beat body). Idempotent."""
    now = datetime.now(UTC)
    due_pub = (
        (await db.execute(
            select(ContentEntry).where(
                ContentEntry.deleted_at.is_(None),
                ContentEntry.scheduled_publish_at.is_not(None),
                ContentEntry.scheduled_publish_at <= now,
                ContentEntry.status != PageStatus.PUBLISHED,
            )
        ))
        .scalars()
        .all()
    )
    for entry in due_pub:
        entry.status = PageStatus.PUBLISHED
        entry.published_at = entry.scheduled_publish_at
        entry.scheduled_publish_at = None
        await _emit(db, "page.published", entry)

    due_unpub = (
        (await db.execute(
            select(ContentEntry).where(
                ContentEntry.deleted_at.is_(None),
                ContentEntry.scheduled_unpublish_at.is_not(None),
                ContentEntry.scheduled_unpublish_at <= now,
                ContentEntry.status == PageStatus.PUBLISHED,
            )
        ))
        .scalars()
        .all()
    )
    for entry in due_unpub:
        entry.status = PageStatus.DRAFT
        entry.scheduled_unpublish_at = None

    await db.flush()
    counts = {"published": len(due_pub), "unpublished": len(due_unpub)}
    if counts["published"] or counts["unpublished"]:
        logger.info("content_entries_scheduled_processed", **counts)
    return counts


async def _emit(db, event: str, entry: ContentEntry) -> None:
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type=f"webhook.{event}",
            aggregate_type="content_entry",
            aggregate_id=str(entry.id),
            payload={"id": str(entry.id), "status": str(entry.status)},
        )
    except Exception:  # noqa: BLE001
        logger.warning("entry_webhook_emit_failed", entry_id=str(entry.id))
