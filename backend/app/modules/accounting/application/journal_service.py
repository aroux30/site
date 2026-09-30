"""Journal application service: draft → post → reverse, plus period close.

Lifecycle (mirrors the fiscal-invoice lifecycle deliberately):

- :func:`create_entry` — build a draft entry from ``LineSpec`` rules, resolving
  account codes to ids and *rejecting* any unbalanced body. Idempotent per
  ``(source_type, source_id, entry_type)``.
- :func:`post_entry` — allocate the gapless ``JE-<period>-NNNNNN`` number,
  resolve the Jalali period, chain the tamper-evident hash, mark posted.
- :func:`reverse_entry` — post a new mirrored entry, leave the original
  untouched, and flip the original's status to ``reversed``. Reversal into a
  **closed** period is rejected: the correcting entry posts into the current
  period with a reference to the original.
- Period close (:func:`close_period`) records a snapshot and locks the period;
  any later mutation of an entry inside it raises.

Posting is always **best-effort from the caller's point of view**: the
event-driven path (``application/events.py``) lets failures propagate so the
outbox retry owns recovery, exactly like the credit-note listener.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Sequence

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.accounting.application.hashing import (
    GENESIS_HASH,
    compute_entry_hash,
    verify_entry,
)
from app.modules.accounting.application.numbering import fiscal_period_for
from app.modules.accounting.application.numbering import (
    allocate_next_journal_number as _allocate_number,
)
from app.modules.accounting.application.posting_rules import LineSpec, RuleError
from app.modules.accounting.domain.models import (
    JOURNAL_TRANSITIONS,
    Account,
    AccountingPeriod,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    JournalSourceType,
    PeriodStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Account resolution
# ---------------------------------------------------------------------------


async def resolve_accounts(
    db: "AsyncSession", codes: Sequence[str]
) -> dict[str, Account]:
    """Resolve account codes to active ``Account`` rows (one round trip).

    Raises ``ValidationError`` when a code is unknown or the account is
    inactive — a posting rule pointing at a deactivated account is a
    configuration error the operator must see, not a silent skip.
    """
    wanted = list(dict.fromkeys(codes))
    if not wanted:
        return {}
    stmt = select(Account).where(Account.code.in_(wanted))
    rows = list((await db.execute(stmt)).scalars().all())
    by_code = {acc.code: acc for acc in rows}

    missing = [code for code in wanted if code not in by_code]
    if missing:
        raise ValidationError(
            detail=(
                "کدینگ حساب یافت نشد؛ ابتدا جدول حسابها را مقداردهی کنید: "
                + "، ".join(missing)
            ),
            error_code="ACCOUNT_NOT_FOUND",
        )
    inactive = [code for code in wanted if not by_code[code].is_active]
    if inactive:
        raise ValidationError(
            detail="حسابهای غیرفعال قابل استفاده در سند نیستند: " + "، ".join(inactive),
            error_code="ACCOUNT_INACTIVE",
        )
    return by_code


# ---------------------------------------------------------------------------
# Balance guard
# ---------------------------------------------------------------------------


def ensure_balanced(lines: list[LineSpec] | list[JournalLine]) -> tuple[int, int]:
    """Reject an unbalanced or one-sided-missing line body.

    Returns ``(debit_total, credit_total)`` when the body is valid. This is the
    single enforcement point for the double-entry invariant; the DB check
    constraints are the second line of defence.
    """
    if not lines:
        raise ValidationError(
            detail="سند حسابداری باید حداقل دو ردیف داشته باشد",
            error_code="ENTRY_EMPTY",
        )
    debit = 0
    credit = 0
    for line in lines:
        d = int(getattr(line, "debit_rial", 0) or 0)
        c = int(getattr(line, "credit_rial", 0) or 0)
        if d < 0 or c < 0:
            raise ValidationError(
                detail="مبالغ بدهکار و بستانکار نمیتوانند منفی باشند",
                error_code="NEGATIVE_AMOUNT",
            )
        if (d > 0) == (c > 0):
            raise ValidationError(
                detail="هر ردیف سند باید دقیقاً یک طرف بدهکار یا بستانکار داشته باشد",
                error_code="LINE_NOT_ONE_SIDED",
            )
        debit += d
        credit += c

    if debit != credit:
        raise ValidationError(
            detail=f"سند تراز نیست: جمع بدهکار {debit} و جمع بستانکار {credit}",
            error_code="ENTRY_NOT_BALANCED",
        )
    return debit, credit


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def _idempotency_key(
    source_type: JournalSourceType | str, source_id: str | uuid.UUID, entry_type: str
) -> str:
    st = source_type.value if isinstance(source_type, JournalSourceType) else str(source_type)
    return f"journal:{st}:{source_id}:{entry_type}"


async def find_entry_by_source(
    db: "AsyncSession",
    *,
    source_type: JournalSourceType | str,
    source_id: str | uuid.UUID,
    entry_type: str,
) -> JournalEntry | None:
    """Idempotency lookup for the ``(source_type, source_id, entry_type)`` triple."""
    st = source_type if isinstance(source_type, JournalSourceType) else JournalSourceType(source_type)
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .where(
            JournalEntry.source_type == st,
            JournalEntry.source_id == str(source_id),
            JournalEntry.entry_type == entry_type,
        )
    )
    return (await db.execute(stmt)).scalars().first()


async def create_entry(
    db: "AsyncSession",
    *,
    source_type: JournalSourceType,
    source_id: str | uuid.UUID | None,
    entry_type: str,
    description: str,
    line_specs: list[LineSpec],
    entry_date: datetime | None = None,
    status: JournalEntryStatus = JournalEntryStatus.DRAFT,
    reversal_of_id: uuid.UUID | None = None,
    reversal_reason: str | None = None,
    created_by: uuid.UUID | None = None,
    fiscal_period_override: str | None = None,
) -> tuple[JournalEntry, bool]:
    """Create a journal entry (draft or straight-to-posted). Idempotent per source.

    Returns ``(entry, created)``. A repeat call for the same
    ``(source_type, source_id, entry_type)`` returns the existing entry with
    ``created=False`` — this is what makes outbox redelivery safe. The
    uniqueness also holds at the DB level via ``uq_journal_entries_source``.
    """
    if source_id is not None:
        existing = await find_entry_by_source(
            db, source_type=source_type, source_id=source_id, entry_type=entry_type
        )
        if existing is not None:
            return existing, False

    ensure_balanced(line_specs)
    accounts = await resolve_accounts(db, [spec.account_code for spec in line_specs])

    now = entry_date or datetime.now(UTC)
    entry = JournalEntry(
        entry_date=now,
        source_type=source_type,
        source_id=str(source_id) if source_id is not None else None,
        entry_type=entry_type,
        description=description,
        status=JournalEntryStatus.DRAFT,
        reversal_of_id=reversal_of_id,
        reversal_reason=reversal_reason,
        idempotency_key=(
            _idempotency_key(source_type, source_id, entry_type)
            if source_id is not None
            else None
        ),
        created_by=created_by,
    )
    db.add(entry)
    await db.flush()

    for position, spec in enumerate(line_specs, start=1):
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=accounts[spec.account_code].id,
                position=position,
                debit_rial=int(spec.debit_rial),
                credit_rial=int(spec.credit_rial),
                description=spec.description,
            )
        )
    await db.flush()
    await db.refresh(entry, attribute_names=["lines"])

    if status is JournalEntryStatus.POSTED:
        entry = await post_entry(
            db,
            entry_id=entry.id,
            actor_id=created_by,
            fiscal_period_override=fiscal_period_override,
        )
        if fiscal_period_override:
            entry.fiscal_period = fiscal_period_override
            await db.flush()

    await logger.ainfo(
        "journal_entry_created",
        entry_id=str(entry.id),
        entry_type=entry_type,
        source_type=source_type.value,
        source_id=str(source_id) if source_id is not None else None,
        status=entry.status.value,
    )
    return entry, True


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------


def _ensure_transition(entry: JournalEntry, target: JournalEntryStatus) -> None:
    if target not in JOURNAL_TRANSITIONS.get(entry.status, frozenset()):
        raise ConflictError(
            detail=(
                f"تغییر وضعیت سند از «{entry.status.value}» به «{target.value}» مجاز نیست."
            ),
            error_code="INVALID_JOURNAL_TRANSITION",
        )


async def get_period(
    db: "AsyncSession", fiscal_period: str, *, for_update: bool = False
) -> AccountingPeriod | None:
    stmt = select(AccountingPeriod).where(AccountingPeriod.fiscal_period == fiscal_period)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def ensure_period_open(db: "AsyncSession", fiscal_period: str) -> None:
    """Reject any write into a closed fiscal period (immutability guard)."""
    period = await get_period(db, fiscal_period, for_update=True)
    if period is not None and period.status == PeriodStatus.CLOSED:
        raise ConflictError(
            detail=(
                f"دوره مالی {fiscal_period} بسته شده است و ثبت یا تغییر سند در آن مجاز نیست؛ "
                "سند اصلاحی باید در دوره جاری با ارجاع به سند اصلی ثبت شود."
            ),
            error_code="PERIOD_CLOSED",
        )


_PERIOD_LOOKAHEAD = 20


async def _first_open_period(db: "AsyncSession", *, from_period: str) -> str:
    """The first period at or after ``from_period`` that is not closed.

    Periods are Jalali *years* labelled ``"1404"``, so the walk is arithmetical
    over the label. A period with no row yet counts as open (nothing has
    closed it). Raises when the whole lookahead window is closed.
    """
    try:
        start = int(from_period)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValidationError(
            detail=f"برچسب دوره مالی نامعتبر است: {from_period}",
            error_code="INVALID_PERIOD_LABEL",
        ) from exc

    for offset in range(_PERIOD_LOOKAHEAD + 1):
        candidate = f"{start + offset:04d}"
        row = await get_period(db, candidate)
        if row is None or row.status == PeriodStatus.OPEN:
            return candidate

    raise ConflictError(
        detail="هیچ دوره مالی بازی برای ثبت سند اصلاحی یافت نشد.",
        error_code="NO_OPEN_PERIOD",
    )


async def _latest_posted_hash(db: "AsyncSession", *, fiscal_period: str) -> str:
    stmt = (
        select(JournalEntry.hash)
        .where(
            JournalEntry.fiscal_period == fiscal_period,
            JournalEntry.hash.is_not(None),
            JournalEntry.status.in_(
                [JournalEntryStatus.POSTED, JournalEntryStatus.REVERSED]
            ),
        )
        .order_by(JournalEntry.posted_at.desc(), JournalEntry.created_at.desc())
        .limit(1)
    )
    latest = (await db.execute(stmt)).scalar_one_or_none()
    return latest or GENESIS_HASH


async def post_entry(
    db: "AsyncSession",
    *,
    entry_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    fiscal_period_override: str | None = None,
) -> JournalEntry:
    """Post a draft: allocate number, chain hash, lock the period check.

    ``fiscal_period_override`` forces the entry into a specific period — used
    by reversal to move a correction out of a closed period. It must name a
    period that is still open (the guard below enforces it).
    """
    entry = await db.get(JournalEntry, entry_id, with_for_update=True)
    if entry is None:
        raise NotFoundError("JournalEntry")
    _ensure_transition(entry, JournalEntryStatus.POSTED)

    now = entry.entry_date or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    period = fiscal_period_override or fiscal_period_for(now)

    # Closed-period guard: no *new* posting into a locked period.
    await ensure_period_open(db, period)

    await db.refresh(entry, attribute_names=["lines"])
    debit, credit = ensure_balanced(list(entry.lines))
    if debit == 0:
        raise ValidationError(
            detail="سند با مبلغ صفر قابل ثبت نیست", error_code="ENTRY_ZERO_AMOUNT"
        )

    number, period = await _allocate_number(db, fiscal_period=period)
    previous_hash = await _latest_posted_hash(db, fiscal_period=period)

    entry.status = JournalEntryStatus.POSTED
    entry.number = number
    entry.fiscal_period = period
    entry.posted_at = now
    entry.previous_hash = previous_hash
    entry.hash = compute_entry_hash(
        number=number, posted_at=now, lines=list(entry.lines), previous_hash=previous_hash
    )
    await db.flush()

    await logger.ainfo(
        "journal_entry_posted",
        entry_id=str(entry.id),
        number=number,
        fiscal_period=period,
        debit_rial=debit,
        credit_rial=credit,
    )
    return entry


# ---------------------------------------------------------------------------
# Reversal
# ---------------------------------------------------------------------------


async def reverse_entry(
    db: "AsyncSession",
    *,
    entry_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID | None = None,
) -> JournalEntry:
    """Reverse a posted entry by posting a new mirrored one.

    The original is never edited beyond its status flip to ``reversed`` — the
    pair (original, reversal) sums to zero and both stay in the feed. The
    reversal posts into the **current** period when the original's period is
    closed, carrying ``reversal_reason`` with a reference to the original
    number so an external accounting package can trace it.
    """
    if not reason or not reason.strip():
        raise ValidationError(
            detail="دلیل برگشت سند الزامی است", error_code="REVERSAL_REASON_REQUIRED"
        )

    original = await db.get(JournalEntry, entry_id, with_for_update=True)
    if original is None:
        raise NotFoundError("JournalEntry")
    if original.status != JournalEntryStatus.POSTED:
        raise ConflictError(
            detail="فقط سند ثبتشده قابل برگشت است.",
            error_code="ENTRY_NOT_POSTED",
        )

    await db.refresh(original, attribute_names=["lines"])
    # Lines must know their account to be mirrored; load explicitly.
    for line in original.lines:
        if getattr(line, "account", None) is None:
            line.account = await db.get(Account, line.account_id)

    from app.modules.accounting.application.posting_rules import mirror_lines

    mirrored = mirror_lines(list(original.lines))
    ensure_balanced(mirrored)

    original_period = original.fiscal_period or fiscal_period_for(original.entry_date)
    original_period_row = await get_period(db, original_period)
    original_closed = (
        original_period_row is not None and original_period_row.status == PeriodStatus.CLOSED
    )

    period_override: str | None = None
    if original_closed:
        # A closed period is locked, so the correcting entry moves forward to
        # the first *open* Jalali period — the current period itself may also
        # already be closed, so this walks forward until it finds one.
        period_override = await _first_open_period(db, from_period=original_period)
        reversal_reason = (
            f"برگشت سند {original.number} (دوره {original_period} بسته است، "
            f"ثبت در دوره {period_override}): {reason.strip()}"
        )
    else:
        reversal_reason = f"برگشت سند {original.number}: {reason.strip()}"

    entry_date = datetime.now(UTC)

    reversal, created = await create_entry(
        db,
        source_type=JournalSourceType.MANUAL,
        source_id=None,  # manual-sourced: uniqueness is on reversal_of_id below
        entry_type="reversal",
        description=f"سند برگشتی {original.number or ''}".strip(),
        line_specs=mirrored,
        entry_date=entry_date,
        status=JournalEntryStatus.DRAFT,
        reversal_of_id=original.id,
        reversal_reason=reversal_reason,
        created_by=actor_id,
        fiscal_period_override=period_override,
    )
    # The reversal is unique per original, not per (source_type, source_id).
    reversal.idempotency_key = f"journal:reversal:{original.id}"
    reversal = await post_entry(
        db,
        entry_id=reversal.id,
        actor_id=actor_id,
        fiscal_period_override=period_override,
    )

    original.status = JournalEntryStatus.REVERSED
    await db.flush()

    await logger.ainfo(
        "journal_entry_reversed",
        original_id=str(original.id),
        original_number=original.number,
        reversal_id=str(reversal.id),
        reversal_number=reversal.number,
        actor_id=str(actor_id) if actor_id else None,
    )
    return reversal


# ---------------------------------------------------------------------------
# Period close
# ---------------------------------------------------------------------------


async def close_period(
    db: "AsyncSession",
    *,
    fiscal_period: str,
    actor_id: uuid.UUID | None = None,
) -> AccountingPeriod:
    """Close a Jalali fiscal period: lock it and snapshot its posted totals.

    Idempotent-safe: re-closing an already closed period raises a
    ``ConflictError`` (the admin UI shows the current state instead). Closing
    never edits entries — it flips the period row to ``closed`` and records
    the control totals, after which every write path into the period checks
    :func:`ensure_period_open`.
    """
    if not fiscal_period or not fiscal_period.strip():
        raise ValidationError(detail="دوره مالی الزامی است", error_code="PERIOD_REQUIRED")
    period_key = fiscal_period.strip()

    period = await get_period(db, period_key, for_update=True)
    if period is None:
        period = AccountingPeriod(fiscal_period=period_key, status=PeriodStatus.OPEN)
        db.add(period)
        await db.flush()

    if period.status == PeriodStatus.CLOSED:
        raise ConflictError(
            detail=f"دوره مالی {period_key} قبلاً بسته شده است.",
            error_code="PERIOD_ALREADY_CLOSED",
        )

    counts_stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit_rial), 0),
            func.coalesce(func.sum(JournalLine.credit_rial), 0),
        )
        .select_from(JournalEntry)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(
            JournalEntry.fiscal_period == period_key,
            JournalEntry.status.in_(
                [JournalEntryStatus.POSTED, JournalEntryStatus.REVERSED]
            ),
        )
    )
    debit_total, credit_total = (await db.execute(counts_stmt)).one()
    distinct_stmt = (
        select(func.count(func.distinct(JournalEntry.id)))
        .where(
            JournalEntry.fiscal_period == period_key,
            JournalEntry.status.in_(
                [JournalEntryStatus.POSTED, JournalEntryStatus.REVERSED]
            ),
        )
    )
    entry_count = int((await db.execute(distinct_stmt)).scalar_one() or 0)

    period.status = PeriodStatus.CLOSED
    period.closed_at = datetime.now(UTC)
    period.closed_by = actor_id
    period.entry_count = entry_count
    period.debit_total_rial = int(debit_total or 0)
    period.credit_total_rial = int(credit_total or 0)
    await db.flush()

    await logger.ainfo(
        "accounting_period_closed",
        fiscal_period=period_key,
        entry_count=entry_count,
        debit_total_rial=period.debit_total_rial,
        credit_total_rial=period.credit_total_rial,
    )
    return period


async def list_periods(
    db: "AsyncSession", *, fiscal_period: str | None = None
) -> list[AccountingPeriod]:
    stmt = select(AccountingPeriod).order_by(AccountingPeriod.fiscal_period.desc())
    if fiscal_period:
        stmt = stmt.where(AccountingPeriod.fiscal_period == fiscal_period)
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Read paths
# ---------------------------------------------------------------------------


async def list_entries(
    db: "AsyncSession",
    *,
    fiscal_period: str | None = None,
    status: JournalEntryStatus | None = None,
    source_type: JournalSourceType | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[JournalEntry], int]:
    stmt = select(JournalEntry).options(
        selectinload(JournalEntry.lines).selectinload(JournalLine.account)
    )
    count_stmt = select(func.count()).select_from(JournalEntry)
    if fiscal_period:
        stmt = stmt.where(JournalEntry.fiscal_period == fiscal_period)
        count_stmt = count_stmt.where(JournalEntry.fiscal_period == fiscal_period)
    if status is not None:
        stmt = stmt.where(JournalEntry.status == status)
        count_stmt = count_stmt.where(JournalEntry.status == status)
    if source_type is not None:
        stmt = stmt.where(JournalEntry.source_type == source_type)
        count_stmt = count_stmt.where(JournalEntry.source_type == source_type)

    total = int((await db.execute(count_stmt)).scalar_one())
    stmt = (
        stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, total


async def get_entry(db: "AsyncSession", entry_id: uuid.UUID) -> JournalEntry:
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .where(JournalEntry.id == entry_id)
    )
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if entry is None:
        raise NotFoundError("JournalEntry")
    return entry


async def verify_chain(
    db: "AsyncSession", *, fiscal_period: str | None = None
) -> dict[str, Any]:
    """Recompute the entry hash chain and report the first broken link."""
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .where(JournalEntry.number.is_not(None))
        .order_by(
            JournalEntry.fiscal_period.asc(),
            JournalEntry.posted_at.asc(),
            JournalEntry.created_at.asc(),
        )
    )
    if fiscal_period:
        stmt = stmt.where(JournalEntry.fiscal_period == fiscal_period)

    entries = list((await db.execute(stmt)).scalars().all())

    checked = 0
    running: dict[str, str] = {}
    first_broken: dict[str, Any] | None = None

    for entry in entries:
        key = entry.fiscal_period or ""
        expected_prev = running.get(key, GENESIS_HASH)
        prev_ok = (entry.previous_hash or GENESIS_HASH) == expected_prev
        own_ok = verify_entry(
            number=entry.number or "",
            posted_at=entry.posted_at or datetime.fromtimestamp(0, UTC),
            lines=list(entry.lines),
            previous_hash=entry.previous_hash or GENESIS_HASH,
            expected_hash=entry.hash or "",
        )
        checked += 1
        if prev_ok and own_ok:
            running[key] = entry.hash or GENESIS_HASH
            continue
        first_broken = {
            "entry_id": str(entry.id),
            "number": entry.number,
            "fiscal_period": entry.fiscal_period,
            "previous_hash_ok": prev_ok,
            "own_hash_ok": own_ok,
        }
        break

    return {
        "valid": first_broken is None,
        "entries_checked": checked,
        "first_broken": first_broken,
    }
