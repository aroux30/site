"""Rate-update history readers: the paginated list query and the CSV export.

Kept out of the routes module so the query and the export share one filter
builder — the referrals history pattern (``reward_history.py``), including
the 50k export cap and the reporting module's formula-injection-hardened CSV
builder (the project's single CSV convention).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import String as SAString
from sqlalchemy import cast

from app.modules.currency.domain.models import UsdPriceUpdate

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

#: Hard cap on exported rows — the same ceiling the reward-history export uses.
_EXPORT_MAX_ROWS = 50_000


def _build_where(
    *,
    status: str | None,
    q: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list[Any]:
    where: list[Any] = []
    if status:
        where.append(UsdPriceUpdate.status == status)
    if date_from is not None:
        where.append(UsdPriceUpdate.created_at >= date_from)
    if date_to is not None:
        # Inclusive end date: everything before the NEXT day starts.
        where.append(UsdPriceUpdate.created_at < date_to + timedelta(days=1))
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append(cast(UsdPriceUpdate.details, SAString).ilike(like))
    return where


async def build_rate_history_csv(
    db: AsyncSession,
    *,
    status: str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> bytes:
    """The filtered history as CSV bytes (UTF-8 BOM, injection-hardened)."""
    from sqlalchemy import select

    from app.modules.reporting.application.csv_builder import build_csv_bytes

    where = _build_where(status=status, q=q, date_from=date_from, date_to=date_to)
    rows = list(
        (
            await db.execute(
                select(UsdPriceUpdate)
                .where(*where)
                .order_by(UsdPriceUpdate.created_at.desc(), UsdPriceUpdate.id.desc())
                .limit(_EXPORT_MAX_ROWS)
            )
        )
        .scalars()
        .all()
    )

    header = [
        "تاریخ",
        "نرخ (ریال)",
        "منبع نرخ",
        "تعداد تغییر",
        "نوع اجرا",
        "وضعیت",
        "خطا",
        "جزئیات تغییرات",
    ]
    body = []
    for row in rows:
        changed = (row.details or {}).get("changed") or []
        detail_text = "; ".join(
            f"{c.get('sku', '?')}: {c.get('old_price', '?')}→{c.get('new_price', '?')}"
            for c in changed[:50]
        )
        if len(changed) > 50:
            detail_text += f" … (+{len(changed) - 50})"
        body.append(
            [
                row.created_at.isoformat() if row.created_at else "",
                row.rate_rial,
                row.rate_source,
                row.updated_count,
                "زمان‌بندی‌شده" if row.scheduled else "دستی",
                "موفق" if row.status == "success" else "ناموفق",
                row.error or "",
                detail_text,
            ]
        )
    return build_csv_bytes(header, body)


__all__ = ["build_rate_history_csv"]
