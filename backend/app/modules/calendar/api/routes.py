"""Calendar API: the aggregated operations view.

Read-only. There is no create/update/delete here by design — every event this
module reports is owned by another module, and editing it from a calendar
would mean two write paths to the same fact (see the module docstring in
``calendar_service``). Deep links in the UI take the operator to the owning
screen to make a change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.calendar.application import calendar_service as svc

router = APIRouter()
_ADMIN = "/admin"


@router.get(
    _ADMIN,
    dependencies=[Depends(RequirePermissions("calendar:read"))],
    summary="Aggregated scheduled events (admin)",
)
async def list_calendar_events(
    db: AsyncSession = Depends(get_db),
    from_date: datetime | None = Query(None, description="ISO 8601 — default: now"),
    to_date: datetime | None = Query(
        None, description="ISO 8601 — default: 30 days after from"
    ),
    sources: list[str] | None = Query(
        None,
        description="Limit to these source modules (content, discounts, notifications, messaging, subscriptions)",
    ),
) -> dict[str, Any]:
    """Everything scheduled in the window, from every owning module.

    Requires ``calendar:read``. The response carries a per-source count (or
    that source's error) so a partially-broken view is visibly partial rather
    than quietly empty.
    """
    return await svc.collect_events(
        db, from_date=from_date, to_date=to_date, sources=sources
    )


@router.get(
    f"{_ADMIN}/summary",
    dependencies=[Depends(RequirePermissions("calendar:read"))],
    summary="Calendar summary counts (admin)",
)
async def calendar_summary(
    db: AsyncSession = Depends(get_db),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
) -> dict[str, Any]:
    """Counts by source and by day, plus what is happening right now."""
    result = await svc.collect_events(db, from_date=from_date, to_date=to_date)
    return svc.summarize(result["events"])


@router.get(
    f"{_ADMIN}/sources",
    dependencies=[Depends(RequirePermissions("calendar:read"))],
    summary="Which modules contribute to the calendar (admin)",
)
async def calendar_sources() -> dict[str, Any]:
    """The source list, so the UI does not hard-code module names."""
    return {
        "sources": [
            {"module": "content", "label": "انتشار محتوا (صفحات و نوشته‌ها)"},
            {"module": "discounts", "label": "بازه‌های تخفیف"},
            {"module": "notifications", "label": "اعلان‌های زمان‌دار"},
            {"module": "messaging", "label": "کمپین‌های پیامکی"},
            {"module": "subscriptions", "label": "صورتحساب اشتراک‌ها"},
        ]
    }


__all__ = ["router"]
