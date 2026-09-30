"""Minimal five-field cron parsing and next-run calculation.

The project ships no cron library (no croniter dependency); saved report
schedules use the standard five-field POSIX layout::

    minute hour day-of-month month day-of-week

Supported field syntax: ``*``, single numbers, ranges (``1-5``),
comma-separated lists (``1,15``) and steps (``*/5``, ``1-30/2``).
Months are 1-12; day-of-week accepts 0-6 (Sunday=0) and 7 (also Sunday) per
Vixie cron. Matching semantics follow the classic rule: when **both** the
day-of-month and day-of-week fields are restricted, a date matches if
*either* matches; otherwise both restricted/effective fields must match.

All times are evaluated against a caller-provided ``aware`` datetime — the
module's callers use Asia/Tehran (matching the Celery timezone).
"""

from __future__ import annotations

from datetime import datetime, timedelta

__all__ = ["CronSpec", "cron_description", "next_run_after", "validate_cron"]

_MIN_LIMIT = (0, 59)
_HOUR_LIMIT = (0, 23)
_DOM_LIMIT = (1, 31)
_MONTH_LIMIT = (1, 12)
_DOW_LIMIT = (0, 7)  # 0 and 7 both mean Sunday


class _FieldError(ValueError):
    pass


def _parse_field(spec: str, limits: tuple[int, int], field_name: str) -> set[int]:
    """Expand one cron field into the set of matching integer values."""
    lo, hi = limits
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise _FieldError(f"بخش خالی در فیلد {field_name}")

        if "/" in part:
            base, step_text = part.split("/", 1)
            if not step_text.isdigit():
                raise _FieldError(f"گام نامعتبر در فیلد {field_name}: {step_text}")
            step = int(step_text)
            if step < 1:
                raise _FieldError(f"گام باید مثبت باشد در فیلد {field_name}")
        else:
            base, step = part, 1

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            if not (start_text.isdigit() and end_text.isdigit()):
                raise _FieldError(f"بازه نامعتبر در فیلد {field_name}: {base}")
            start, end = int(start_text), int(end_text)
        elif base.isdigit():
            start = end = int(base)
        else:
            raise _FieldError(f"مقدار نامعتبر در فیلد {field_name}: {base}")

        if start < lo or end > hi or start > end:
            raise _FieldError(
                f"مقدار فیلد {field_name} خارج از بازه مجاز ({lo}-{hi}): {base}"
            )
        values.update(range(start, end + 1, step))
    return values


class CronSpec:
    """Parsed five-field cron expression."""

    __slots__ = (
        "_dom_restricted",
        "_dow_restricted",
        "day_of_month",
        "day_of_week",
        "expression",
        "hour",
        "minute",
        "month",
    )

    def __init__(self, expression: str) -> None:
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError(
                "زمان‌بندی cron باید دقیقاً ۵ فیلد داشته باشد "
                "(دقیقه ساعت روز-ماه ماه روز-هفته)"
            )
        self.expression = expression
        self.minute = _parse_field(fields[0], _MIN_LIMIT, "دقیقه")
        self.hour = _parse_field(fields[1], _HOUR_LIMIT, "ساعت")
        self.day_of_month = _parse_field(fields[2], _DOM_LIMIT, "روز ماه")
        self.month = _parse_field(fields[3], _MONTH_LIMIT, "ماه")
        # Normalize 7 -> 0 (Sunday) so membership checks have one spelling.
        self.day_of_week = {
            0 if d == 7 else d
            for d in _parse_field(fields[4], _DOW_LIMIT, "روز هفته")
        }
        self._dom_restricted = fields[2] != "*"
        self._dow_restricted = fields[4] != "*"

    def matches(self, moment: datetime) -> bool:
        """True when ``moment`` (truncated to minutes) satisfies the spec."""
        if moment.minute not in self.minute:
            return False
        if moment.hour not in self.hour:
            return False
        if moment.month not in self.month:
            return False
        # Python weekday(): Monday=0 .. Sunday=6; cron uses Sunday=0.
        cron_dow = (moment.weekday() + 1) % 7
        dom_ok = moment.day in self.day_of_month
        dow_ok = cron_dow in self.day_of_week
        if self._dom_restricted and self._dow_restricted:
            return dom_ok or dow_ok
        return dom_ok and dow_ok


def validate_cron(expression: str) -> None:
    """Raise ``ValueError`` (Persian message) when the expression is invalid."""
    CronSpec(expression)


def next_run_after(after: datetime, expression: str, *, horizon_days: int = 366) -> datetime:
    """First strictly-after-``after`` minute matching the cron expression.

    Raises ``ValueError`` for invalid expressions and when no run occurs
    within ``horizon_days`` (e.g. February 30th) so schedules that can never
    fire are rejected up front.

    ``after`` is compared as given; all production callers pass a
    tz-aware Tehran time. A naive timestamp is read as-is rather than
    rejected, because the caller's intent is unambiguous — refusing it would
    trade a quiet-but-correct run for a loud-but-unhelpful error.
    """
    spec = CronSpec(expression)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = candidate + timedelta(days=horizon_days)
    while candidate < deadline:
        if spec.matches(candidate):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError(
        "در بازه یک سال آینده زمانی برای اجرای این زمان‌بندی پیدا نشد؛ عبارت cron را بازبینی کنید"
    )


def cron_description(expression: str) -> str:
    """Tiny human-readable summary for UI tooltips (Persian)."""
    fields = expression.split()
    if len(fields) != 5:
        return expression
    minute, hour, dom, month, dow = fields
    parts = []
    if minute == "*" and hour == "*":
        parts.append("هر دقیقه")
    else:
        parts.append(f"ساعت {hour} و دقیقه {minute}")
    if dom != "*":
        parts.append(f"روز {dom} ماه")
    if month != "*":
        parts.append(f"در ماه {month}")
    if dow != "*":
        parts.append(f"روز هفته {dow}")
    return "، ".join(parts)
