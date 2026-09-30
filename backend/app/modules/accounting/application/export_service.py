"""Journal export: flat CSV + JSON for external accounting software.

The CSV is a **flat journal-line export** — one row per journal line, with the
entry header repeated on every row so the file imports without a second pass.
It reuses ``reporting/application/csv_builder.py`` verbatim: UTF-8 with BOM
(so Excel shows Persian correctly) and the formula-injection escaping
(``= + - @`` prefixed cells get a leading apostrophe).

**Target format — هلو (Holoo) journal import.** Holoo's «ورود اسناد از فایل»
expects, in order: شماره سند (entry number), تاریخ (date), کد حساب, نام حساب,
شرح, بدهکار, بستانکار — amounts as plain integers with no separators and no
currency suffix. ``سپیدار`` (Sepidar) and ``محک`` (Mahak) accept the same
column order with their own date separators, so the ISO and Jalali dates are
both emitted and the consumer picks the one it needs. The header row is
Persian, matching what all three packages' import wizards expect to map.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.accounting.domain.models import (
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from app.modules.invoicing.application.numbering import fiscal_period_for
from app.modules.orders.application.invoice_service import gregorian_to_jalali
from app.modules.reporting.application.csv_builder import build_csv_bytes

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Holoo/Sepidar/Mahak-friendly column order.
EXPORT_HEADER: list[str] = [
    "شماره سند",
    "تاریخ (شمسی)",
    "تاریخ (میلادی)",
    "دوره مالی",
    "کد حساب",
    "نام حساب",
    "شرح سند",
    "شرح ردیف",
    "بدهکار",
    "بستانکار",
    "نوع منبع",
    "مرجع منبع",
    "وضعیت",
]

# Statuses that belong in an export handed to an accountant: drafts are
# unfinished work and must never reach the ledger.
_EXPORTABLE_STATUSES = (JournalEntryStatus.POSTED, JournalEntryStatus.REVERSED)


def format_jalali_date(dt: datetime) -> str:
    """``1404/06/02`` — the date format Iranian accounting packages expect."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def _rows_for_entries(entries: Iterable[JournalEntry]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for entry in entries:
        posted_at = entry.posted_at or entry.entry_date
        jalali = format_jalali_date(posted_at)
        iso = posted_at.astimezone(UTC).isoformat() if posted_at.tzinfo else posted_at.isoformat()
        for line in entry.lines or []:
            account = getattr(line, "account", None)
            rows.append(
                [
                    entry.number or "",
                    jalali,
                    iso,
                    entry.fiscal_period or "",
                    getattr(account, "code", "") or "",
                    getattr(account, "name_fa", "") or "",
                    entry.description or "",
                    line.description or "",
                    int(line.debit_rial or 0),
                    int(line.credit_rial or 0),
                    entry.source_type.value,
                    entry.source_id or "",
                    entry.status.value,
                ]
            )
    return rows


async def _load_entries(
    db: "AsyncSession",
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    fiscal_period: str | None,
    include_drafts: bool = False,
) -> list[JournalEntry]:
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .order_by(
            JournalEntry.fiscal_period.asc(),
            JournalEntry.posted_at.asc(),
            JournalEntry.number.asc(),
        )
    )
    if not include_drafts:
        stmt = stmt.where(JournalEntry.status.in_(_EXPORTABLE_STATUSES))
    if fiscal_period:
        stmt = stmt.where(JournalEntry.fiscal_period == fiscal_period)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)

    return list((await db.execute(stmt)).scalars().all())


async def export_csv(
    db: "AsyncSession",
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    fiscal_period: str | None = None,
) -> bytes:
    """Flat journal-line CSV (UTF-8 BOM, formula-injection-safe)."""
    entries = await _load_entries(
        db, date_from=date_from, date_to=date_to, fiscal_period=fiscal_period
    )
    return build_csv_bytes(EXPORT_HEADER, _rows_for_entries(entries))


async def export_json(
    db: "AsyncSession",
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    fiscal_period: str | None = None,
) -> dict[str, Any]:
    """Structured export for API integrations (same data as the CSV).

    Header totals are included so a consumer can assert the feed balances
    without re-summing the lines itself.
    """
    entries = await _load_entries(
        db, date_from=date_from, date_to=date_to, fiscal_period=fiscal_period
    )

    items: list[dict[str, Any]] = []
    total_debit = 0
    total_credit = 0

    for entry in entries:
        posted_at = entry.posted_at or entry.entry_date
        lines = []
        for line in entry.lines or []:
            account = getattr(line, "account", None)
            debit = int(line.debit_rial or 0)
            credit = int(line.credit_rial or 0)
            total_debit += debit
            total_credit += credit
            lines.append(
                {
                    "position": int(line.position or 0),
                    "account_code": getattr(account, "code", None),
                    "account_name_fa": getattr(account, "name_fa", None),
                    "account_type": (
                        account.type.value if getattr(account, "type", None) else None
                    ),
                    "debit_rial": debit,
                    "credit_rial": credit,
                    "description": line.description,
                }
            )
        items.append(
            {
                "id": str(entry.id),
                "number": entry.number,
                "fiscal_period": entry.fiscal_period,
                "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
                "entry_date_jalali": format_jalali_date(posted_at),
                "posted_at": entry.posted_at.isoformat() if entry.posted_at else None,
                "source_type": entry.source_type.value,
                "source_id": entry.source_id,
                "entry_type": entry.entry_type,
                "description": entry.description,
                "status": entry.status.value,
                "reversal_of_id": str(entry.reversal_of_id) if entry.reversal_of_id else None,
                "reversal_reason": entry.reversal_reason,
                "hash": entry.hash,
                "previous_hash": entry.previous_hash,
                "lines": lines,
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "filters": {
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "fiscal_period": fiscal_period,
        },
        "entry_count": len(items),
        "total_debit_rial": total_debit,
        "total_credit_rial": total_credit,
        "balanced": total_debit == total_credit,
        "currency": "IRR",
        "items": items,
    }


def export_filename(
    *, fiscal_period: str | None, date_from: datetime | None, date_to: datetime | None
) -> str:
    """Deterministic download filename for the CSV response."""
    if fiscal_period:
        return f"journal-{fiscal_period}.csv"
    if date_from and date_to:
        j_from = format_jalali_date(date_from).replace("/", "")
        j_to = format_jalali_date(date_to).replace("/", "")
        return f"journal-{j_from}-{j_to}.csv"
    return "journal.csv"


def period_for(dt: datetime) -> str:
    """Jalali fiscal period of a datetime (thin re-export for the API layer)."""
    return fiscal_period_for(dt)
