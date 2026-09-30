"""Gapless sequential journal numbering, per Jalali fiscal period.

Reuses the fiscal-period resolution and the locked-counter protocol of the
invoicing module (``fiscal_period_for`` + ``SELECT ... FOR UPDATE`` on the
counter row) so both fiscal ledgers of the platform behave identically:

- one ``journal_sequences`` row per Jalali year holds ``last_value``;
- allocation locks that row inside the posting transaction, so concurrent
  posters serialize and a rolled-back allocation never burns a number;
- the committed sequence therefore contains every integer 1..N with no gaps.

Document number format: ``JE-1404-000123``.
"""

from __future__ import annotations

import re
from datetime import datetime as _dt
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.accounting.domain.models import JournalSequence
from app.modules.invoicing.application.numbering import fiscal_period_for  # re-exported below

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

JOURNAL_PREFIX = "JE"

_NUMBER_RE = re.compile(r"^JE-(\d{4})-(\d{6,})$")

__all__ = [
    "JOURNAL_PREFIX",
    "allocate_next_journal_number",
    "fiscal_period_for",
    "format_journal_number",
    "parse_journal_number",
]


def format_journal_number(fiscal_period: str, value: int) -> str:
    """Render ``JE-1404-000123`` for a sequence value."""
    return f"{JOURNAL_PREFIX}-{fiscal_period}-{value:06d}"


def parse_journal_number(number: str) -> tuple[str, int]:
    """Parse ``JE-1404-000123`` into (period, value); raises ValueError."""
    m = _NUMBER_RE.match(number.strip())
    if not m:
        raise ValueError(f"Invalid journal entry number: {number!r}")
    return m.group(1), int(m.group(2))


async def allocate_next_journal_number(
    db: "AsyncSession", *, fiscal_period: str
) -> tuple[str, str]:
    """Atomically allocate the next gapless number for the period.

    Locks the ``journal_sequences`` row ``FOR UPDATE`` (creating it on first
    use inside the same transaction) and returns ``(number, period)``. Must be
    called inside the posting transaction so the increment commits with the
    entry write.
    """
    stmt = (
        select(JournalSequence)
        .where(JournalSequence.fiscal_period == fiscal_period)
        .with_for_update()
    )
    seq = (await db.execute(stmt)).scalar_one_or_none()

    if seq is None:
        # First entry of this period: the unique constraint on fiscal_period
        # turns the concurrent first-insert race into a serialization error on
        # one side rather than a duplicate row; that side retries.
        seq = JournalSequence(fiscal_period=fiscal_period, last_value=0)
        db.add(seq)
        await db.flush()

    seq.last_value += 1
    await db.flush()

    return format_journal_number(fiscal_period, seq.last_value), fiscal_period


def fiscal_period_of(dt: _dt) -> str:
    """Jalali fiscal year of a datetime (thin alias for readability here)."""
    return fiscal_period_for(dt)
