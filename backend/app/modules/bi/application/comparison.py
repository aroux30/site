"""Period-over-period comparison for report results.

ERP benchmark gap analysis (feature #15 BI/dashboards, P1). The reporting
layer already answers "what were sales in this window"; it cannot answer
"…and how does that compare to last month", which is the question a dashboard
actually exists to answer.

This module holds only the arithmetic. It is pure on purpose: percentage
change is where the classic reporting bugs live (division by zero, sign
flips on refund months, comparing a partial period against a full one), and
none of them need a database to reproduce.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any

from app.core.exceptions.handlers import ValidationError


class ComparisonMode(str, Enum):
    """How the previous window is derived."""

    #: Same length, immediately before: [1 Sep–30 Sep] vs [2 Aug–31 Aug].
    PREVIOUS_PERIOD = "previous_period"
    #: The same window one year earlier: catches seasonality.
    SAME_PERIOD_LAST_YEAR = "same_period_last_year"


#: A percentage change larger than this is reported as capped with a flag
#: rather than as a number. A month with 100 Rial of sales followed by
#: 1,000,000 is a +999,900% "growth" that means nothing and wrecks an
#: axis scale; the raw values are still returned.
MAX_MEANINGFUL_CHANGE_PCT = 99_900.0


def previous_window(
    date_from: date, date_to: date, mode: ComparisonMode
) -> tuple[date, date]:
    """The window to compare against. Pure.

    Both windows are inclusive of their endpoints, matching the report API's
    own ``from``/``to`` semantics — a half-open comparison against a closed
    report would be off by exactly one day, every time.
    """
    if date_to < date_from:
        raise ValidationError(
            "بازه تاریخی نامعتبر است", error_code="INVALID_DATE_RANGE"
        )

    if mode == ComparisonMode.PREVIOUS_PERIOD:
        span_days = (date_to - date_from).days + 1
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=span_days - 1)
        return prev_from, prev_to

    if mode == ComparisonMode.SAME_PERIOD_LAST_YEAR:
        # 29 Feb has no counterpart in a non-leap year; clamp to the 28th
        # rather than raising, because "last year" is still a meaningful
        # question when this year is a leap year.
        try:
            prev_from = date_from.replace(year=date_from.year - 1)
        except ValueError:
            prev_from = date_from.replace(year=date_from.year - 1, day=28)
        try:
            prev_to = date_to.replace(year=date_to.year - 1)
        except ValueError:
            prev_to = date_to.replace(year=date_to.year - 1, day=28)
        return prev_from, prev_to

    raise ValidationError(
        f"حالت مقایسه نامعتبر است: {mode}", error_code="INVALID_COMPARISON_MODE"
    )


@dataclass(frozen=True)
class MetricDelta:
    """One metric's current value, prior value, and the change between them."""

    key: str
    current: int
    previous: int
    change_abs: int
    change_pct: float | None
    direction: str  # up | down | flat
    pct_capped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "current": self.current,
            "previous": self.previous,
            "change_abs": self.change_abs,
            "change_pct": self.change_pct,
            "direction": self.direction,
            "pct_capped": self.pct_capped,
        }


def compute_delta(key: str, current: int, previous: int) -> MetricDelta:
    """Percent change for one metric. Pure.

    The zero-previous case is the one that matters: a percentage against zero
    is undefined, not infinite, and not 100%. It is reported as ``None`` with
    the absolute change still present, so the UI can say "new this period"
    instead of printing a number that would be a lie.
    """
    change_abs = current - previous

    if previous == 0:
        change_pct: float | None = None
        capped = False
    else:
        change_pct = (change_abs / abs(previous)) * 100
        capped = abs(change_pct) > MAX_MEANINGFUL_CHANGE_PCT
        if capped:
            change_pct = (
                MAX_MEANINGFUL_CHANGE_PCT
                if change_pct > 0
                else -MAX_MEANINGFUL_CHANGE_PCT
            )

    if change_abs > 0:
        direction = "up"
    elif change_abs < 0:
        direction = "down"
    else:
        direction = "flat"

    return MetricDelta(
        key=key,
        current=current,
        previous=previous,
        change_abs=change_abs,
        change_pct=change_pct,
        direction=direction,
        pct_capped=capped,
    )


def compare_totals(
    current: dict[str, Any],
    previous: dict[str, Any],
    *,
    metrics: list[str] | None = None,
) -> list[MetricDelta]:
    """Compare two reports' totals dicts, metric by metric. Pure.

    Only *numeric* entries are compared: a totals dict also carries labels
    and identifiers, and "the vendor name changed by 300%" is noise. Metrics
    are taken from the union of both sides so a metric that appeared or
    disappeared between periods is still surfaced — usually the most
    interesting row on the page.
    """
    keys = metrics if metrics is not None else sorted(set(current) | set(previous))

    deltas: list[MetricDelta] = []
    for key in keys:
        cur_raw = current.get(key)
        prev_raw = previous.get(key)
        # A non-numeric totals entry is a label or id, not a metric.
        if cur_raw is not None and not isinstance(cur_raw, int | float):
            continue
        if prev_raw is not None and not isinstance(prev_raw, int | float):
            continue
        if isinstance(cur_raw, bool) or isinstance(prev_raw, bool):
            continue
        deltas.append(
            compute_delta(key, int(cur_raw or 0), int(prev_raw or 0))
        )
    return deltas


def compare_rows(
    current_rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]],
    *,
    key_field: str,
    metrics: list[str],
) -> list[dict[str, Any]]:
    """Group-level comparison, matched on ``key_field``. Pure.

    Rows that exist in only one period are included with a zero on the missing
    side: a category that sold nothing last month and 500 items this month is
    a finding, and dropping it (the easy inner-join behaviour) hides exactly
    the rows worth seeing.
    """
    def as_int(value: Any) -> int:
        """Numeric -> int; anything else (a label in a metric column) -> 0."""
        if isinstance(value, bool):  # bool is an int subclass; never a metric
            return 0
        if isinstance(value, int | float):
            return int(value)
        return 0

    prev_by_key = {str(r.get(key_field)): r for r in previous_rows}
    seen: set[str] = set()
    compared: list[dict[str, Any]] = []

    for row in current_rows:
        label = str(row.get(key_field))
        seen.add(label)
        prior = prev_by_key.get(label, {})
        entry: dict[str, Any] = {key_field: row.get(key_field)}
        for metric in metrics:
            delta = compute_delta(
                metric, as_int(row.get(metric)), as_int(prior.get(metric))
            )
            entry[metric] = delta.to_dict()
        compared.append(entry)

    # Groups that only exist in the prior period — a category that stopped
    # selling entirely.
    for label, prior in prev_by_key.items():
        if label in seen:
            continue
        entry = {key_field: prior.get(key_field)}
        for metric in metrics:
            entry[metric] = compute_delta(metric, 0, as_int(prior.get(metric))).to_dict()
        compared.append(entry)

    return compared