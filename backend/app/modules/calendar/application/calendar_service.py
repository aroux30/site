"""Operational calendar: one view over everything already scheduled.

ERP benchmark gap analysis (feature #27 Calendar, P2 — "minimal, no CalDAV").
The platform is full of *scheduled things* — blog/CMS publish windows,
discount windows, scheduled campaigns, timed notices, subscription billing
dates — and each lives in its own admin page. Nobody can answer "what is
happening next week?" without opening five screens.

This module owns no schedule of its own. It is a **read-only aggregator**:
it queries the tables that already hold dates and normalises them into one
timeline. That is deliberate — a calendar that stored its own copy of events
would be a second source of truth for the same facts, and the two would drift.

Design notes
------------
* **Read-only by construction.** No model, no table, no migration. If this
  module is deleted, nothing else changes — which is exactly the property a
  cross-cutting view should have.
* **Every event carries its source.** ``(source_module, event_type, entity_id)``
  lets the UI deep-link back, and lets a reader verify nothing was invented.
* **Window semantics differ per source and are preserved.** A discount is an
  interval (starts→ends); a subscription billing is a point in time. Both are
  represented as a start plus an optional end, so "happening now" is answerable
  for the first and "falls on Tuesday" for the second.
* **Fail-soft per source.** One table being unreachable must not blank the
  whole calendar; that source reports as errored and the rest still render.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: A window wider than this is almost certainly a mistake (a year picker
#: defaulting to 1970, a bad parse) and would scan every table for nothing.
MAX_WINDOW_DAYS = 400


@dataclass
class CalendarEvent:
    """One normalised scheduled thing."""

    source_module: str
    event_type: str
    entity_id: uuid.UUID
    title: str
    start_at: datetime
    end_at: datetime | None = None
    status: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_module": self.source_module,
            "event_type": self.event_type,
            "entity_id": str(self.entity_id),
            "title": self.title,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "status": self.status,
            "detail": self.detail,
        }


def validate_window(
    from_date: datetime | None, to_date: datetime | None, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Normalise a requested window to ``(start, end)``. Pure.

    Defaults to the next 30 days. Refuses an inverted or absurdly wide window
    rather than silently querying a decade of history.
    """
    now = now or datetime.now(UTC)
    start = from_date or now
    end = to_date or (start + timedelta(days=30))

    if end <= start:
        raise ValidationError(
            "بازه زمانی نامعتبر است: تاریخ پایان باید بعد از شروع باشد",
            error_code="INVALID_DATE_WINDOW",
        )
    if (end - start).days > MAX_WINDOW_DAYS:
        raise ValidationError(
            f"بازه زمانی بیش از حد بزرگ است (حداکثر {MAX_WINDOW_DAYS} روز)",
            error_code="WINDOW_TOO_LARGE",
        )
    return start, end


def _overlaps(
    start: datetime, end: datetime | None, window_start: datetime, window_end: datetime
) -> bool:
    """True when [start, end] intersects [window_start, window_end). Pure.

    An event with no end is treated as a point. An event that started before
    the window but has not ended is *inside* it — a four-week discount is
    relevant to next week's view, and a naive ``start >= window_start`` filter
    would hide exactly the long-running things an operator most needs to see.
    """
    if end is None:
        return window_start <= start < window_end
    return start < window_end and end >= window_start


# ── Per-source collectors ───────────────────────────────────────────────────
#
# Each collector is independent and fail-soft. They share one shape:
# (session, window_start, window_end) -> list[CalendarEvent].


async def _collect_cms_pages(
    db: AsyncSession, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """CMS pages with a scheduled publish or unpublish window."""
    from app.modules.content.domain.models import CmsPage

    rows = (
        await db.execute(
            select(CmsPage).where(
                (CmsPage.scheduled_publish_at.is_not(None))
                | (CmsPage.scheduled_unpublish_at.is_not(None)),
                (CmsPage.scheduled_publish_at >= start)
                | (CmsPage.scheduled_unpublish_at >= start),
                (CmsPage.scheduled_publish_at < end)
                | (CmsPage.scheduled_unpublish_at < end),
            )
        )
    ).scalars().all()

    events: list[CalendarEvent] = []
    for page in rows:
        if page.scheduled_publish_at and start <= page.scheduled_publish_at < end:
            events.append(
                CalendarEvent(
                    source_module="content",
                    event_type="cms_publish",
                    entity_id=page.id,
                    title=f"انتشار صفحه: {page.title}",
                    start_at=page.scheduled_publish_at,
                    status=getattr(page.status, "value", str(page.status)),
                    detail={"slug": page.slug},
                )
            )
        if page.scheduled_unpublish_at and start <= page.scheduled_unpublish_at < end:
            events.append(
                CalendarEvent(
                    source_module="content",
                    event_type="cms_unpublish",
                    entity_id=page.id,
                    title=f"پایان انتشار صفحه: {page.title}",
                    start_at=page.scheduled_unpublish_at,
                    status=getattr(page.status, "value", str(page.status)),
                    detail={"slug": page.slug},
                )
            )
    return events


async def _collect_discounts(
    db: AsyncSession, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Discount windows — intervals, so an active one is included."""
    from app.modules.discounts.domain.models import Discount

    rows = (
        await db.execute(
            select(Discount).where(
                Discount.starts_at < end,
                Discount.ends_at >= start,
            )
        )
    ).scalars().all()

    return [
        CalendarEvent(
            source_module="discounts",
            event_type="discount_window",
            entity_id=d.id,
            title=f"تخفیف: {d.name}",
            start_at=d.starts_at,
            end_at=d.ends_at,
            status="active" if getattr(d, "is_active", True) else "inactive",
            detail={
                "code": getattr(d, "code", None),
                "type": getattr(getattr(d, "type", None), "value", None),
            },
        )
        for d in rows
    ]


async def _collect_notices(
    db: AsyncSession, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Timed notices and banners."""
    from app.modules.notifications.domain.notice_models import Notice

    rows = (
        await db.execute(
            select(Notice).where(Notice.start_at < end, Notice.end_at >= start)
        )
    ).scalars().all()

    return [
        CalendarEvent(
            source_module="notifications",
            event_type="notice_window",
            entity_id=n.id,
            title=f"اعلان: {n.title}",
            start_at=n.start_at,
            end_at=n.end_at,
            status="active" if n.is_active else "inactive",
            detail={
                "notice_type": getattr(n.notice_type, "value", str(n.notice_type)),
                "target_page": getattr(n.target_page, "value", str(n.target_page)),
            },
        )
        for n in rows
    ]


async def _collect_campaigns(
    db: AsyncSession, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Scheduled mass-messaging campaigns — points in time."""
    from app.modules.messaging.domain.models import BroadcastCampaign

    rows = (
        await db.execute(
            select(BroadcastCampaign).where(
                BroadcastCampaign.scheduled_at.is_not(None),
                BroadcastCampaign.scheduled_at >= start,
                BroadcastCampaign.scheduled_at < end,
            )
        )
    ).scalars().all()

    return [
        CalendarEvent(
            source_module="messaging",
            event_type="campaign_send",
            entity_id=c.id,
            title=f"کمپین: {c.title}",
            start_at=c.scheduled_at,
            status=getattr(c.status, "value", str(c.status)),
            detail={
                "channel": getattr(c.channel, "value", str(c.channel)),
                "segment": getattr(c.target_segment, "value", str(c.target_segment)),
            },
        )
        for c in rows
        if c.scheduled_at is not None
    ]


async def _collect_subscription_billings(
    db: AsyncSession, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Upcoming recurring-billing dates. Points in time.

    Only active/past-due subscriptions: a cancelled plan's stale
    ``next_billing_at`` is not an upcoming event, and showing it would put a
    charge on the calendar that will never happen.
    """
    from app.modules.subscriptions.domain.models import (
        Subscription,
        SubscriptionStatus,
    )

    rows = (
        await db.execute(
            select(Subscription).where(
                Subscription.status.in_(
                    (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)
                ),
                Subscription.next_billing_at.is_not(None),
                Subscription.next_billing_at >= start,
                Subscription.next_billing_at < end,
            )
        )
    ).scalars().all()

    return [
        CalendarEvent(
            source_module="subscriptions",
            event_type="subscription_billing",
            entity_id=s.id,
            title=f"صورتحساب اشتراک: {s.name}",
            start_at=s.next_billing_at,  # type: ignore[arg-type]
            status=getattr(s.status, "value", str(s.status)),
            detail={"amount_rial": s.total_per_cycle},
        )
        for s in rows
        if s.next_billing_at is not None
    ]


#: Every collector, with its source label for the error report.
_COLLECTORS: list[tuple[str, Any]] = [
    ("content", _collect_cms_pages),
    ("discounts", _collect_discounts),
    ("notifications", _collect_notices),
    ("messaging", _collect_campaigns),
    ("subscriptions", _collect_subscription_billings),
]


async def collect_events(
    db: AsyncSession,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    sources: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate every scheduled thing in the window.

    Returns ``{"events": [...], "window": {...}, "sources": {...}}``. Each
    source reports how many events it contributed or, on failure, the error —
    a broken table must not blank the calendar, but it must also not be
    silently invisible.
    """
    start, end = validate_window(from_date, to_date, now=now)

    wanted = set(sources) if sources else None
    selected = [
        (name, collector)
        for name, collector in _COLLECTORS
        if wanted is None or name in wanted
    ]

    async def _run_one(name: str, collector: Any) -> tuple[str, list[CalendarEvent], str | None]:
        """Collect one source, converting any failure into a reportable error.

        The failure is caught *inside* the gathered task rather than around
        it: ``gather`` without ``return_exceptions`` would let the first
        broken collector cancel its siblings, which is exactly the behaviour
        the per-source error report exists to prevent.
        """
        try:
            return name, await collector(db, start, end), None
        except Exception as exc:  # noqa: BLE001 — one source must not blank the view
            await logger.awarning(
                "calendar_source_failed", source=name, error=str(exc)
            )
            return name, [], str(exc)[:200]

    # The sources are independent reads over the same session, so they run
    # concurrently: five sequential round-trips become one. Read-only, so
    # overlapping them on one connection is safe.
    results = await asyncio.gather(
        *(_run_one(name, collector) for name, collector in selected)
    )

    events: list[CalendarEvent] = []
    source_report: dict[str, Any] = {}
    for name, collected, error in results:
        events.extend(collected)
        if error is None:
            source_report[name] = {"count": len(collected), "ok": True}
        else:
            source_report[name] = {"count": 0, "ok": False, "error": error}

    events.sort(key=lambda e: (e.start_at, e.source_module))

    return {
        "events": [e.to_dict() for e in events],
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "sources": source_report,
        "total": len(events),
    }


def summarize(events: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any]:
    """Counts by source and by day, plus what is active right now. Pure.

    ``now`` is passed in so "active" is computed once against one clock —
    a per-event ``datetime.now()`` would let an event drift between "starts
    in a second" and "active" within a single response.
    """
    now = now or datetime.now(UTC)
    by_source: dict[str, int] = {}
    by_day: dict[str, int] = {}
    active_now = 0

    for event in events:
        source = event.get("source_module", "unknown")
        by_source[source] = by_source.get(source, 0) + 1

        start_raw = event.get("start_at")
        if isinstance(start_raw, str):
            try:
                start = datetime.fromisoformat(start_raw)
            except ValueError:
                continue
        elif isinstance(start_raw, datetime):
            start = start_raw
        else:
            continue

        end_raw = event.get("end_at")
        end: datetime | None = None
        if isinstance(end_raw, str):
            try:
                end = datetime.fromisoformat(end_raw)
            except ValueError:
                end = None
        elif isinstance(end_raw, datetime):
            end = end_raw

        by_day[start.date().isoformat()] = by_day.get(start.date().isoformat(), 0) + 1

        # "Happening now": a point event counts only on its own day; an
        # interval counts across its whole span. Treating them the same would
        # say a campaign from this morning is still running at midnight.
        if end is None:
            if start.date() == now.date():
                active_now += 1
        elif start <= now <= end:
            active_now += 1

    return {
        "total": len(events),
        "active_now": active_now,
        "by_source": by_source,
        "by_day": dict(sorted(by_day.items())),
    }
