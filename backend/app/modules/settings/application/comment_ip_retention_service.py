"""Reduce stored comment IPs to their network, on a schedule.

P0 "حریم خصوصی: نگه‌داشت IP دیدگاه". An IP address on a comment is personal data
under Article 4(1) and this project stored it in full, indefinitely, on a table
the whole storefront can read — and nothing shortened it. The erasure path masks
an address only for the one subject who asked; every other comment keeps its
exact IP forever.

This module is the time-based half: whatever the age of the comment, the address
is reduced to its network. It runs on a beat entry rather than on write,
deliberately — a comment's address is useful at moderation time (who is spamming)
and useless afterwards, and the same masking therefore serves both the retention
requirement and the anti-abuse signal WordPress keeps.

Why on a schedule and not on write: comments are written on the request path.
Masking there adds parsing to every submission for no benefit, because the
moderator looking at a fresh comment is exactly the reader who still needs the
address. Age-based masking has no such reader.

Idempotency is the load-bearing property. ``ip_is_masked`` rejects a value that
is already a network, so a retry after a partial run cannot rewrite the same row
forever, and a second run over the same data selects nothing. Without that
filter this job would report work forever and the daily count would be a lie.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.ip_anonymize import anonymize_ip, ip_is_masked

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: How long a full address is kept. The GDPR text names no number for this, so
#: this is the store's own choice, and the shortest window that still does the
#: job the address was stored for: a moderation backlog, which is measured in
#: hours, not months. Raise it in ``privacy.ip_retention_days`` if an operator
#: needs longer for dispute handling.
DEFAULT_IP_RETENTION_DAYS = 30


class CommentIpRetentionService:
    """Mask comment IPs older than the retention window."""

    @staticmethod
    async def mask_expired_ips(
        db: AsyncSession,
        *,
        retention_days: int | None = None,
        now: datetime | None = None,
    ) -> int:
        """Mask every unmasked comment IP past the retention window.

        Returns the number of rows rewritten. Rows already masked, and rows with
        no address at all, are excluded by the query rather than by a Python
        filter, so a run over a large table does not load every address into
        memory to discover most of them need nothing.
        """
        days = retention_days if retention_days is not None else await _retention_days(db)
        cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
        masked = await mask_ips_older_than(db, cutoff=cutoff)
        logger.info(
            "comment_ips_masked",
            masked=masked,
            retention_days=days,
            cutoff=cutoff.isoformat(),
        )
        return masked


async def mask_ips_older_than(db: AsyncSession, *, cutoff: datetime) -> int:
    """Rewrite ``author_ip`` on comments older than ``cutoff`` to its network.

    Batched, and each batch committed on its own: one malformed row would
    otherwise poison the whole transaction and cost the run every other address
    it had not yet reached. The same reason the per-item savepoint is here and
    not in the caller — a bulk UPDATE that fails once is retried by the beat and
    re-does the work it already did.

    ``ip_is_masked`` is applied in Python rather than SQL because "is this
    already a network" is a parse-and-compare, not an expression the database can
    evaluate. It is only reached for rows the age filter selected, which is why
    the age filter goes in SQL.

    The loop advances by ``id`` rather than re-reading from the oldest row. Rows
    that are already masked are skipped in Python but are *not* excluded from the
    query, so a query that always returned the same first batch would spin
    forever on them — a job that never finishes, rather than one that does no
    work. Cursor paging is what makes "no rows changed" mean "nothing left".
    """
    from app.modules.blog.domain.models import BlogComment

    total = 0
    cursor: uuid.UUID | None = None
    while True:
        page = (
            await db.execute(
                select(BlogComment.id, BlogComment.author_ip)
                .where(
                    BlogComment.author_ip.is_not(None),
                    BlogComment.author_ip != "",
                    BlogComment.created_at < cutoff,
                )
                .order_by(BlogComment.id)
                .limit(_BATCH_SIZE)
            )
        ).all()
        if cursor is not None:
            page = [r for r in page if r[0] > cursor]
        if not page:
            return total
        cursor = page[-1][0]

        for row_id, raw in page:
            if not raw or ip_is_masked(raw):
                continue
            masked = anonymize_ip(raw)
            if masked == raw:
                continue
            async with db.begin_nested():
                await db.execute(
                    update(BlogComment)
                    .where(BlogComment.id == row_id)
                    .values(author_ip=masked)
                    .execution_options(synchronize_session=False)
                )
            total += 1

        await db.commit()


_BATCH_SIZE = 500


async def _retention_days(db: AsyncSession) -> int:
    """The configured window, or the default when the option is absent.

    Read from ``site_options`` rather than the environment so an operator can
    change it in the panel like every other site setting, and clamped to a
    non-negative integer: a malformed option must not produce a negative
    timedelta, which would select comments from the future and mask them all.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = await SiteOptionsService.get(db, "privacy.ip_retention_days")
    if raw is None or not str(raw).strip():
        return DEFAULT_IP_RETENTION_DAYS
    try:
        days = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("privacy_ip_retention_days_invalid", value=str(raw)[:60])
        return DEFAULT_IP_RETENTION_DAYS
    if days < 0:
        logger.warning("privacy_ip_retention_days_negative", value=days)
        return DEFAULT_IP_RETENTION_DAYS
    return days
