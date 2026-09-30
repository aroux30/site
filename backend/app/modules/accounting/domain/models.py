"""Accounting feed domain models.

Three tables make up the feed:

* :class:`Account` — minimal chart of accounts (Iranian standard skeleton is
  seeded idempotently by ``application/account_seed.py``).
* :class:`JournalEntry` + :class:`JournalLine` — double-entry journal: every
  entry must balance (sum debit == sum credit) and every line carries exactly
  one non-zero side. Posted entries are numbered sequentially per Jalali
  fiscal period (same gapless-allocation protocol as ``invoice_sequences``)
  and chained with a SHA-256 tamper-evident hash exactly like the fiscal
  invoices.
* :class:`AccountingPeriod` — per-Jalali-year close record: once a period is
  closed its posted entries are locked and no new entry may post into it.
* :class:`JournalSequence` — the per-period counter row behind the numbering.

Money convention: integer **Rial** (BigInteger), never float. Debit and credit
are both stored positive; the side is which column is non-zero.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class AccountType(str, enum.Enum):
    """Standard five-way account classification."""

    ASSET = "asset"  # دارایی
    LIABILITY = "liability"  # بدهی
    EQUITY = "equity"  # حقوق صاحبان سهام
    REVENUE = "revenue"  # درآمد
    EXPENSE = "expense"  # هزینه


class JournalSourceType(str, enum.Enum):
    """What real-world event produced a journal entry."""

    ORDER = "order"  # order placed → revenue recognition
    PAYMENT = "payment"  # payment captured → clearing / top-up
    REFUND = "refund"  # refund / credit note → contra revenue
    WALLET = "wallet"  # wallet withdrawal sweep → liability movement
    SETTLEMENT = "settlement"  # vendor settlement paid → payable cleared
    PURCHASE = "purchase"  # purchase order received → inventory / accounts payable
    MANUAL = "manual"  # admin-created adjusting entry


class JournalEntryStatus(str, enum.Enum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


# Allowed status transitions, mirroring the invoicing lifecycle vocabulary:
# - draft  -> posted  (allocate number + hash, becomes immutable)
# - posted -> reversed (a correction is a NEW mirrored entry, never an edit)
JOURNAL_TRANSITIONS: dict[JournalEntryStatus, frozenset[JournalEntryStatus]] = {
    JournalEntryStatus.DRAFT: frozenset({JournalEntryStatus.POSTED}),
    JournalEntryStatus.POSTED: frozenset({JournalEntryStatus.REVERSED}),
    JournalEntryStatus.REVERSED: frozenset(),
}


class PeriodStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class Account(BaseModel):
    """One row of the chart of accounts (کدینگ حسابها)."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_accounts_code"),
        Index("ix_accounts_type", "type"),
        Index("ix_accounts_parent_id", "parent_id"),
        Index("ix_accounts_is_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type_enum", native_enum=False),
        nullable=False,
    )
    # Hierarchical chart: group nodes (e.g. "1" داراییها) carry children.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Account(code='{self.code}', name_fa='{self.name_fa}', type={self.type.value})>"


class JournalEntry(BaseModel):
    """Double-entry journal header (سند حسابداری)."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("number", name="uq_journal_entries_number"),
        UniqueConstraint(
            "source_type", "source_id", "entry_type", name="uq_journal_entries_source"
        ),
        Index("ix_journal_entries_fiscal_period", "fiscal_period"),
        Index("ix_journal_entries_status", "status"),
        Index("ix_journal_entries_source_type", "source_type"),
        Index("ix_journal_entries_entry_date", "entry_date"),
        Index("ix_journal_entries_posted_at", "posted_at"),
        Index("ix_journal_entries_idempotency_key", "idempotency_key"),
    )

    # Fiscal document number (JE-1404-000123); NULL while draft.
    number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Jalali fiscal year, e.g. "1404". Set at post time from entry_date.
    fiscal_period: Mapped[str | None] = mapped_column(String(8), nullable=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[JournalSourceType] = mapped_column(
        Enum(JournalSourceType, name="journal_source_type_enum", native_enum=False),
        default=JournalSourceType.MANUAL,
        nullable=False,
    )
    # Free-form reference to the source row (order id, payment id, refund id /
    # event key, settlement id, wallet transaction id). NULL for manual.
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Rule discriminator: revenue | clearing | topup | contra | settlement |
    # withdrawal | manual | reversal. Part of the per-source uniqueness, so a
    # source can never produce two entries of the same kind.
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[JournalEntryStatus] = mapped_column(
        Enum(JournalEntryStatus, name="journal_entry_status_enum", native_enum=False),
        default=JournalEntryStatus.DRAFT,
        nullable=False,
    )

    # SHA-256 tamper-evident chain per fiscal period (same pattern as the
    # fiscal invoices): hash = sha256(number | posted_at | lines | previous).
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # For reversal entries: the posted entry this one mirrors.
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="entry",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="JournalLine.position",
    )

    @property
    def is_mutable(self) -> bool:
        """Only drafts may still be edited; posted entries are immutable."""
        return self.status == JournalEntryStatus.DRAFT

    @property
    def total_debit_rial(self) -> int:
        return sum(int(ln.debit_rial) for ln in (self.lines or []))

    @property
    def total_credit_rial(self) -> int:
        return sum(int(ln.credit_rial) for ln in (self.lines or []))

    def __repr__(self) -> str:
        return (
            f"<JournalEntry(id={self.id}, number={self.number}, "
            f"type={self.entry_type}, status={self.status.value})>"
        )


class JournalLine(BaseModel):
    """One side of one account movement. Exactly one of debit/credit is > 0."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        Index("ix_journal_lines_entry_id", "entry_id"),
        Index("ix_journal_lines_account_id", "account_id"),
        CheckConstraint(
            "debit_rial >= 0 AND credit_rial >= 0", name="ck_journal_lines_nonneg"
        ),
        CheckConstraint(
            "(debit_rial > 0 AND credit_rial = 0) OR (credit_rial > 0 AND debit_rial = 0)",
            name="ck_journal_lines_one_sided",
        ),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    debit_rial: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    credit_rial: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["Account"] = relationship("Account", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<JournalLine(entry_id={self.entry_id}, account_id={self.account_id}, "
            f"debit={self.debit_rial}, credit={self.credit_rial})>"
        )


class AccountingPeriod(BaseModel):
    """Jalali fiscal period close record.

    A period is *open* until an admin closes it. Closing locks every posted
    entry in the period (mutations raise) and only records the closing
    totals — it never touches the entries themselves.
    """

    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("fiscal_period", name="uq_accounting_periods_period"),
        Index("ix_accounting_periods_status", "status"),
    )

    fiscal_period: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus, name="accounting_period_status_enum", native_enum=False),
        default=PeriodStatus.OPEN,
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Snapshot taken at close: posted-entry count and control totals.
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    debit_total_rial: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    credit_total_rial: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<AccountingPeriod(period={self.fiscal_period}, status={self.status.value})>"


class JournalSequence(BaseModel):
    """Per-fiscal-period gapless counter for journal numbers (JE-1404-000123).

    Same allocation protocol as ``invoice_sequences``: the row is locked
    ``FOR UPDATE`` inside the posting transaction, so concurrent posters
    serialize and a rollback re-uses the still-committed ``last_value`` +
    1 — the committed sequence has no gaps.
    """

    __tablename__ = "journal_sequences"
    __table_args__ = (
        UniqueConstraint("fiscal_period", name="uq_journal_sequences_period"),
    )

    fiscal_period: Mapped[str] = mapped_column(String(8), nullable=False)
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<JournalSequence(period={self.fiscal_period} last={self.last_value})>"


def journal_lines_balance(lines: list[Any]) -> tuple[int, int]:
    """Sum the two sides of a line list; helper for guards and reports."""
    debit = sum(int(getattr(ln, "debit_rial", 0) or 0) for ln in lines)
    credit = sum(int(getattr(ln, "credit_rial", 0) or 0) for ln in lines)
    return debit, credit
