"""404 Monitor — record and review not-found hits (Rank Math parity).

Every 404 the storefront answers is recorded here, one row per distinct
path with a hit counter. The operator opens the SEO → 404 panel, sees what
is broken, and turns a path into a redirect with one click.

Design choices, each of which a naive version gets wrong:

* **Counter, not log.** A dead URL hit a thousand times is one row with
  ``hit_count=1000``. A log would bury the signal under its own volume and
  grow without bound.

* **Bounded writes.** Recording is best-effort and never raises: a 404
  being answered must not become a 500 because the monitor failed. The
  storefront route calls ``record_miss`` in a try/except.

* **Bots are recorded too.** Googlebot hitting a stale URL is exactly the
  signal an operator wants (it means the sitemap or an old link points at
  nothing), so the user agent is stored, not filtered. A separate
  ``bots_only`` flag is deliberately NOT offered — the panel shows the
  agent so the operator can tell.

* **No path explosion.** The path is capped at 500 chars and query strings
  are stripped by the caller (the route records ``request.url.path``): a
  scanner hammering ``/?random=1..9999`` must not create a row per variant.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.modules.seo.domain.models import Seo404Log

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: A path is capped at the column width; anything longer is a probe, not a
#: page, and PostgreSQL would reject the row outright.
MAX_PATH = 500
MAX_REFERRER = 500
MAX_UA = 300


async def record_miss(
    db: Any,
    path: str,
    *,
    referrer: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Upsert one 404 hit. Never raises — the caller is answering a request.

    The upsert is atomic (``ON CONFLICT DO UPDATE``), so two concurrent hits
    to the same new path cannot race into a unique violation.
    """
    try:
        now = datetime.now(UTC)
        stmt = pg_insert(Seo404Log).values(
            id=uuid.uuid4(),
            path=(path or "/")[:MAX_PATH],
            referrer=(referrer or None) and referrer[:MAX_REFERRER],
            user_agent=(user_agent or None) and user_agent[:MAX_UA],
            hit_count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Seo404Log.path],
            set_={
                "hit_count": Seo404Log.hit_count + 1,
                "last_seen_at": now,
                # The latest referrer/agent replace the old ones: "how did
                # the most recent visitor get here" is the useful question.
                "referrer": stmt.excluded.referrer,
                "user_agent": stmt.excluded.user_agent,
            },
        )
        await db.execute(stmt)
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — monitoring must not break serving
        logger.warning("seo_404_record_failed", path=path[:200], error=str(exc)[:200])
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass


async def list_misses(
    db: Any,
    *,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[Seo404Log], int]:
    """Most-hit first, then most-recent — the order an operator triages in."""
    stmt = select(Seo404Log)
    if search:
        stmt = stmt.where(Seo404Log.path.ilike(f"%{search.strip()}%"))
    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Seo404Log.hit_count.desc(), Seo404Log.last_seen_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(rows), int(total)


async def delete_miss(db: Any, miss_id: uuid.UUID) -> None:
    await db.execute(delete(Seo404Log).where(Seo404Log.id == miss_id))
    await db.commit()


async def clear_all(db: Any) -> int:
    """Empty the monitor. Returns the number of rows removed."""
    result = await db.execute(delete(Seo404Log))
    await db.commit()
    return int(result.rowcount or 0)


async def summary(db: Any) -> dict[str, int]:
    """Counts for the SEO dashboard: total distinct paths, hits, last 7 days."""
    from datetime import timedelta

    week_ago = datetime.now(UTC) - timedelta(days=7)
    total_paths = (
        await db.execute(select(func.count()).select_from(Seo404Log))
    ).scalar_one()
    total_hits = (
        await db.execute(select(func.coalesce(func.sum(Seo404Log.hit_count), 0)))
    ).scalar_one()
    recent = (
        await db.execute(
            select(func.count())
            .select_from(Seo404Log)
            .where(Seo404Log.last_seen_at >= week_ago)
        )
    ).scalar_one()
    return {
        "distinct_paths": int(total_paths),
        "total_hits": int(total_hits),
        "paths_last_7_days": int(recent),
    }
