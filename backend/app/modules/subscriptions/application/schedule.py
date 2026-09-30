"""Billing-schedule arithmetic — pure functions, no I/O.

Intervals advance from the subscription's anchor date, never from "now": a
monthly plan that first billed on the 31st keeps landing on month-end, and a
billing run that is two days late does not shift every future cycle. This is
the same rule metasfresh's contract schedules and Stripe's billing anchors
use, and it is the difference between "billed on the 1st" and "billed on
whatever day the worker happened to run".
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from app.modules.subscriptions.domain.models import Subscription, SubscriptionInterval

#: Cycle lengths for fixed intervals. Months are handled by calendar
#: arithmetic below, not by a day count — 30-day "months" drift a week/year.
_FIXED_DAYS: dict[SubscriptionInterval, int] = {
    SubscriptionInterval.WEEKLY: 7,
}

#: How far a single advance may push; a guard against a corrupt interval
#: producing an absurd date rather than an exception.
_MAX_ADVANCE_DAYS = 3660


def add_months(anchor: datetime, months: int) -> datetime:
    """Add ``months`` calendar months, clamping the day to month end.

    Jan 31 + 1 month = Feb 28/29 (not Mar 3), which is what a customer who
    subscribed on the 31st expects and what Iranian billing systems do too.
    """
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return anchor.replace(year=year, month=month, day=min(anchor.day, last_day))


def advance(anchor: datetime, subscription: Subscription, cycles: int = 1) -> datetime:
    """Return the billing datetime ``cycles`` intervals after ``anchor``.

    ``cycles`` is applied to the interval as a whole (2 monthly cycles = two
    calendar months), so month-end clamping composes correctly.
    """
    if cycles < 1:
        raise ValueError("cycles must be >= 1")

    interval = subscription.interval
    count = subscription.interval_count * cycles

    if interval in _FIXED_DAYS:
        result = anchor + timedelta(days=_FIXED_DAYS[interval] * count)
    elif interval == SubscriptionInterval.MONTHLY:
        result = add_months(anchor, count)
    elif interval == SubscriptionInterval.QUARTERLY:
        result = add_months(anchor, 3 * count)
    elif interval == SubscriptionInterval.YEARLY:
        result = add_months(anchor, 12 * count)
    elif interval == SubscriptionInterval.CUSTOM_DAYS:
        days = subscription.custom_interval_days
        if not days or days < 1:
            raise ValueError("custom_interval_days must be set for a custom interval")
        result = anchor + timedelta(days=days * count)
    else:  # pragma: no cover - enum is closed
        raise ValueError(f"unsupported interval: {interval}")

    # Guard against an absurd configuration silently scheduling the year 3000.
    if (result - anchor).days > _MAX_ADVANCE_DAYS * cycles:
        raise ValueError("computed next billing date is implausibly far in the future")
    return result


def next_period_index(subscription: Subscription) -> int:
    """The index of the cycle about to be billed (0 for the first charge)."""
    return len(subscription.billings) if subscription.billings else 0


def is_due(subscription: Subscription, now: datetime) -> bool:
    """True when the subscription has a billing date at or before ``now``."""
    return (
        subscription.status.value in ("active", "past_due")
        and subscription.next_billing_at is not None
        and subscription.next_billing_at <= now
    )
