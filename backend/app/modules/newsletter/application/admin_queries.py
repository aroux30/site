"""Admin read queries for the newsletter subscriber list.

Same shape as inventory/card_admin_queries.py. All statements are static
SQLAlchemy expressions; the only user-controlled values are the page number
and page size, both bounds-checked at the route.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.newsletter.domain.models import NewsletterSubscriber

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_subscribers(
    db: AsyncSession, *, page: int = 1, page_size: int = 20
) -> tuple[list[NewsletterSubscriber], int, dict[str, int]]:
    """One page of subscribers (newest first) plus per-status totals.

    The status breakdown is one GROUP BY over the whole table, not a query
    per status: the admin page renders the counts beside the list, and the
    list itself is paginated.
    """
    total = (await db.execute(select(func.count(NewsletterSubscriber.email)))).scalar() or 0
    stmt = (
        select(NewsletterSubscriber)
        .order_by(NewsletterSubscriber.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())

    status_counts: dict[str, int] = {}
    for row_status, row_count in (
        await db.execute(
            select(NewsletterSubscriber.status, func.count(NewsletterSubscriber.email))
            .group_by(NewsletterSubscriber.status)
        )
    ).all():
        key = str(getattr(row_status, "value", row_status))
        status_counts[key] = int(row_count)
    return items, int(total), status_counts


async def export_csv(db: AsyncSession) -> str:
    """Every subscriber as CSV, oldest first, with a header row.

    The export is not paginated: it exists for GDPR/data-portability handoffs
    where a partial list would be misleading. Quotes/commas in fields are
    handled by the csv module.
    """
    rows = (
        (await db.execute(
            select(NewsletterSubscriber).order_by(NewsletterSubscriber.created_at.asc())
        ))
        .scalars()
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["email", "status", "source", "created_at"])
    for s in rows:
        writer.writerow([s.email, str(s.status.value), s.source, s.created_at.isoformat()])
    return buffer.getvalue()
