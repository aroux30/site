"""Revisions and scheduled publishing for custom post type entries.

The parity gap this closes: an operator filling in a `product` or a
`testimonial` through the blog admin's content-types tab had no revision
history and could not date an entry forward. The other content-entry system
(`cms_content_entries`) has both — this is the copy, not a new idea.

Two decisions worth stating:

* **Whole-state snapshots, not diffs.** The fields are operator-defined JSON with
  no stable schema, so a delta cannot be applied back without knowing what
  changed in the shape since. Restoring means writing the stored object over.
* **A snapshot is taken before the write, not after.** Restoring "revision 1"
  has to mean the state before the second save, so the row that is about to be
  overwritten is what is recorded. Recording after would make the newest
  revision indistinguishable from the current row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blog.domain.custom_post_types import (
    CustomPostEntry,
    CustomPostEntryRevision,
    CustomPostTypeStatus,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: How many revisions to keep per entry. Bounded because the snapshot is the
#: whole JSON object, and an entry edited a hundred times would otherwise grow a
#: hundred copies of itself. WordPress keeps the same idea and calls it
#: `WP_POST_REVISIONS`.
DEFAULT_REVISION_LIMIT = 20


async def _snapshot(
    db: AsyncSession,
    entry: CustomPostEntry,
    *,
    created_by: uuid.UUID | None,
    limit: int = DEFAULT_REVISION_LIMIT,
) -> CustomPostEntryRevision | None:
    """Record ``entry``'s current state, then trim to ``limit``.

    Called *before* a write. Trimming keeps the newest ``limit - 1`` plus the one
    about to be written, so the oldest revision is the state before the oldest
    surviving edit — which is what makes it worth restoring.
    """
    newest = (await db.execute(
        select(func.max(CustomPostEntryRevision.revision_number))
        .where(CustomPostEntryRevision.entry_id == entry.id)
    )).scalar_one()

    revision = CustomPostEntryRevision(
        entry_id=entry.id,
        fields=dict(entry.fields) if entry.fields else None,
        title=entry.title,
        excerpt=entry.excerpt,
        revision_number=(newest or 0) + 1,
        created_by_id=created_by,
    )
    db.add(revision)

    if limit and limit > 0:
        # Everything above the window goes, oldest first. `limit` is not
        # decremented: the row just added is inside the window by construction,
        # since the max was taken before it existed.
        keep_from = (newest or 0) + 1 - (limit - 1)
        await db.execute(
            CustomPostEntryRevision.__table__.delete().where(
                (CustomPostEntryRevision.entry_id == entry.id)
                & (CustomPostEntryRevision.revision_number < keep_from)
            )
        )
    return revision


async def update_entry(
    db: AsyncSession,
    entry: CustomPostEntry,
    *,
    changes: dict[str, Any],
    actor_id: uuid.UUID | None = None,
    snapshot: bool = True,
) -> CustomPostEntry:
    """Apply ``changes`` to an entry, keeping the previous state first.

    The snapshot is skipped on the very first write, when there is no previous
    state worth having and a revision numbered 1 that matches the entry is
    noise an operator has to scroll past.
    """
    if snapshot and entry.revision_count:
        revision = await _snapshot(db, entry, created_by=actor_id)
        if revision is not None:
            entry.revision_count = revision.revision_number
    elif snapshot:
        # The first edit. No earlier state to keep, but the entry is *from now
        # on* something worth snapshotting before the next write, so the
        # counter moves. Reading it from this column alone is what made the
        # first and second edits both skip the snapshot — the counter only moved
        # as a side effect of a snapshot that had been skipped, so it could
        # never leave zero and revisions were never taken at all.
        entry.revision_count = 1
    for key, value in changes.items():
        setattr(entry, key, value)
    await db.flush()
    return entry


async def list_revisions(
    db: AsyncSession,
    entry_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[CustomPostEntryRevision]:
    """Newest first — the order an operator reads them in."""
    rows = (await db.execute(
        select(CustomPostEntryRevision)
        .where(CustomPostEntryRevision.entry_id == entry_id)
        .order_by(CustomPostEntryRevision.revision_number.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def restore_revision(
    db: AsyncSession,
    entry_id: uuid.UUID,
    revision_number: int,
    *,
    actor_id: uuid.UUID | None = None,
) -> CustomPostEntry:
    """Write a stored revision back over the entry.

    The current state is snapshotted first, so restoring is itself undoable —
    an operator who restores the wrong revision gets back to where they were by
    restoring again, rather than having lost the state they mis-restored over.
    """
    entry = await db.get(CustomPostEntry, entry_id)
    if entry is None:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("CustomPostEntry", f"ورودی {entry_id} یافت نشد")

    revision = (await db.execute(
        select(CustomPostEntryRevision).where(
            CustomPostEntryRevision.entry_id == entry_id,
            CustomPostEntryRevision.revision_number == revision_number,
        )
    )).scalars().first()
    if revision is None:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError(
            "CustomPostEntryRevision", f"نسخه {revision_number} یافت نشد"
        )

    await _snapshot(db, entry, created_by=actor_id)

    entry.title = revision.title or entry.title
    entry.excerpt = revision.excerpt
    entry.fields = dict(revision.fields) if revision.fields else entry.fields
    await db.flush()
    logger.info(
        "custom_post_entry_revision_restored",
        entry_id=str(entry_id),
        revision_number=revision_number,
    )
    return entry


async def publish_scheduled(db: AsyncSession) -> dict[str, int]:
    """Move entries whose scheduled time has arrived into `published`.

    Idempotent, and it clears the schedule column as it goes — so a run that
    crashes halfway does not republish on the next tick, and a row cannot be
    picked up twice by two workers.

    A scheduled time in the future is left alone, which is what makes a
    mistakenly past date recoverable: the operator can set it forward again.
    """
    now = datetime.now(UTC)
    due = (await db.execute(
        select(CustomPostEntry).where(
            CustomPostEntry.status == CustomPostTypeStatus.DRAFT,
            CustomPostEntry.scheduled_publish_at.is_not(None),
            CustomPostEntry.scheduled_publish_at <= now,
        )
    )).scalars().all()

    for entry in due:
        entry.status = CustomPostTypeStatus.PUBLISHED
        # published_at falls back to when it actually went live, not to when it
        # was scheduled to — an entry that ran three days late should not
        # appear three days old in the archive.
        entry.published_at = entry.published_at or entry.scheduled_publish_at or now
        entry.scheduled_publish_at = None

    await db.commit()
    if due:
        logger.info("custom_post_entries_published", count=len(due))
    return {"published": len(due)}