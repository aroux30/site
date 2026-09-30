"""Fiscal period resolution and gapless sequential document numbering.

Fiscal period = Jalali (Shamsi) year of issue, reusing the codebase's
existing ``gregorian_to_jalali`` conversion from the orders invoice renderer
(no new dependency).

Numbering is **gapless per (fiscal_period, doc_type)**: allocation takes a
``SELECT ... FOR UPDATE`` row lock on the ``invoice_sequences`` row and
increments ``last_value`` inside the caller's transaction. The lock is held
until commit, so concurrent posters serialize on the row; a transaction that
rolls back after allocating never publishes its value, and the *next*
allocator re-derives the same value from the committed ``last_value`` — the
committed sequence therefore contains every integer from 1..N with no gaps
(the classic non-transactional-sequence gap problem does not apply because
the counter itself is transactional state, unlike a Postgres ``SEQUENCE``).

The trade-off vs. a dedicated Postgres sequence per period is deliberate:
Postgres sequences are non-transactional (fast, but leave gaps on rollback,
which violates gapless numbering), while a locked counter row serializes
allocation for correctness. Posting volume per fiscal period is far below
the contention threshold where that serialization would matter.

Document number format: ``INV-1404-000123`` / ``CN-1404-000045``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.invoicing.domain.models import InvoiceSequence, InvoiceType
from app.modules.orders.application.invoice_service import gregorian_to_jalali

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_PREFIX_BY_TYPE: dict[InvoiceType, str] = {
    InvoiceType.INVOICE: "INV",
    InvoiceType.CREDIT_NOTE: "CN",
}

_NUMBER_RE = re.compile(r"^(INV|CN)-(\d{4})-(\d{6,})$")


def fiscal_period_for(dt: datetime) -> str:
    """Return the Jalali fiscal year (e.g. ``"1404"``) for a datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    jy, _jm, _jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}"


def format_document_number(doc_type: InvoiceType, fiscal_period: str, value: int) -> str:
    """Render the canonical document number for a sequence value."""
    return f"{_PREFIX_BY_TYPE[doc_type]}-{fiscal_period}-{value:06d}"


def parse_document_number(number: str) -> tuple[InvoiceType, str, int]:
    """Parse ``INV-1404-000123`` into (type, period, value); raises ValueError."""
    m = _NUMBER_RE.match(number.strip())
    if not m:
        raise ValueError(f"Invalid invoice document number: {number!r}")
    prefix, period, value = m.group(1), m.group(2), int(m.group(3))
    doc_type = InvoiceType.INVOICE if prefix == "INV" else InvoiceType.CREDIT_NOTE
    return doc_type, period, value


async def allocate_next_number(
    db: AsyncSession,
    *,
    doc_type: InvoiceType,
    issued_at: datetime,
) -> tuple[str, str]:
    """Atomically allocate the next gapless document number for the period.

    Locks the sequence row ``FOR UPDATE`` (creating it on first use inside
    the same transaction), increments ``last_value``, and returns
    ``(number, fiscal_period)``. Must be called inside the posting
    transaction so the increment and the invoice write commit together.
    """
    period = fiscal_period_for(issued_at)

    stmt = (
        select(InvoiceSequence)
        .where(
            InvoiceSequence.fiscal_period == period,
            InvoiceSequence.doc_type == doc_type,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    seq = result.scalar_one_or_none()

    if seq is None:
        # First document of this period/type. The unique constraint on
        # (fiscal_period, doc_type) makes the concurrent first-insert race a
        # serialization error on one side rather than a duplicate row; that
        # side's transaction retries and takes the lock path above.
        seq = InvoiceSequence(fiscal_period=period, doc_type=doc_type, last_value=0)
        db.add(seq)
        await db.flush()

    seq.last_value += 1
    await db.flush()

    return format_document_number(doc_type, period, seq.last_value), period
