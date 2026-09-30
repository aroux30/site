"""Slug-change history: the record that keeps old public URLs resolvable.

A slug is part of a public URL. Renaming a page or a post therefore breaks
every inbound link to the old one, and nothing in the storefront can tell the
two cases apart: ``/about-us`` after a rename and ``/about-us`` after a delete
both 404. This module is the join that makes the difference visible.

It owns three things and nothing else:

* :func:`record_slug_change` — the only writer. Called from the two slug-change
  points (``cms_page_service.update_page`` and ``blog_service.update_post``),
  and only when the slug actually changed, so the initial create is not a
  "change from empty".
* :func:`resolve_slug_redirect` — reads the newest history row for an old slug
  and returns the live resource it now belongs to, or ``None``. The storefront
  routes call this *after* the live lookup misses, so it is a fallback, not a
  second source of truth.
* The resource-type constants. They are plain strings, not an enum, because
  they are shared with the comment-target discriminator in
  ``blog/domain/models.py`` and stored as raw strings in the column.

Writes are deliberately not wrapped in a broad ``try/except``. Unlike the
audit log — which is a side channel that must never break a content edit — a
missing history row is a real, unrecoverable loss of the old URL, and quietly
swallowing the failure is how this table became a dead table in the first
place. The caller's transaction is the unit of atomicity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.modules.blog.domain.wp_parity_models import SlugHistory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Mirrors COMMENT_RESOURCE_* in blog/domain/models.py, which is the other
# polymorphic-resource discriminator in the blog module and the reason these
# values are strings rather than an enum.
SLUG_RESOURCE_BLOG_POST = "blog_post"
SLUG_RESOURCE_CMS_PAGE = "cms_page"


@dataclass(frozen=True)
class SlugRedirect:
    """An old slug and the current slug of the resource it now answers for."""

    resource_type: str
    resource_id: uuid.UUID
    old_slug: str
    new_slug: str


async def record_slug_change(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: uuid.UUID,
    old_slug: str,
    new_slug: str,
) -> SlugHistory | None:
    """Append a history row for one rename. No-op when the slug did not change.

    Returns ``None`` for a no-op rather than raising, so the call sites read as
    the plain "did it change?" guard they are, and cannot forget the check.
    """
    if not old_slug or not new_slug or old_slug == new_slug:
        return None
    row = SlugHistory(
        resource_type=resource_type,
        resource_id=resource_id,
        old_slug=old_slug,
        new_slug=new_slug,
    )
    db.add(row)
    await db.flush()
    logger.info(
        "slug_history_recorded",
        resource_type=resource_type,
        resource_id=str(resource_id),
        old_slug=old_slug,
        new_slug=new_slug,
    )
    return row


async def resolve_slug_redirect(
    db: AsyncSession, slug: str, *, resource_type: str | None = None
) -> SlugRedirect | None:
    """Find the current slug for *slug* if it was renamed.

    Rows accumulate, so a page renamed ``a`` → ``b`` → ``c`` leaves both
    ``a→b`` and ``b→c``. Only the newest ``created_at`` is returned: it is the
    one whose ``new_slug`` is the resource's current slug, and an older row's
    target may itself have been renamed since.

    The chain is not followed. If ``a`` was renamed to ``b`` and ``b`` was later
    given a fresh page, the live lookup resolves ``b`` first and this fallback
    is never reached for it — so the target slug is by construction the one the
    caller did not find a live resource for. The caller still verifies the
    resource is live before redirecting; history is a hint about what changed,
    not proof that it exists.
    """
    if not slug:
        return None
    stmt = select(SlugHistory).where(SlugHistory.old_slug == slug)
    if resource_type is not None:
        stmt = stmt.where(SlugHistory.resource_type == resource_type)
    stmt = stmt.order_by(SlugHistory.created_at.desc()).limit(1)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return SlugRedirect(
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        old_slug=row.old_slug,
        new_slug=row.new_slug,
    )
