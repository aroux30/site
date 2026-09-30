"""Pydantic contracts for the accounting feed (admin API)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountTypeLiteral = Literal["asset", "liability", "equity", "revenue", "expense"]
EntryStatusLiteral = Literal["draft", "posted", "reversed"]
PeriodStatusLiteral = Literal["open", "closed"]


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class AccountCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name_fa: str = Field(..., min_length=1, max_length=200)
    type: AccountTypeLiteral
    parent_id: uuid.UUID | None = None
    is_active: bool = True
    description: str | None = Field(None, max_length=2000)


class AccountUpdateRequest(BaseModel):
    """Only mutable fields: the code is the posting rules' contract."""

    name_fa: str | None = Field(None, min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    is_active: bool | None = None
    description: str | None = Field(None, max_length=2000)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_fa: str
    type: AccountTypeLiteral
    parent_id: uuid.UUID | None = None
    is_active: bool
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AccountListResponse(BaseModel):
    items: list[AccountResponse]
    total: int


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------


class JournalLineInput(BaseModel):
    """One side of a manual entry: exactly one of debit/credit must be > 0."""

    account_id: uuid.UUID | None = None
    account_code: str | None = Field(None, max_length=20)
    debit_rial: int = Field(0, ge=0)
    credit_rial: int = Field(0, ge=0)
    description: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _one_side_only(self) -> "JournalLineInput":
        if self.account_id is None and not self.account_code:
            raise ValueError("هر ردیف باید کد یا شناسه حساب داشته باشد")
        if (self.debit_rial > 0) == (self.credit_rial > 0):
            raise ValueError("هر ردیف باید دقیقاً یک طرف بدهکار یا بستانکار داشته باشد")
        return self


class JournalEntryCreateRequest(BaseModel):
    """Manual journal entry (سند دستی)."""

    entry_date: datetime | None = None
    description: str = Field(..., min_length=1, max_length=1000)
    lines: list[JournalLineInput] = Field(..., min_length=2)
    post_now: bool = True

    @model_validator(mode="after")
    def _must_balance(self) -> "JournalEntryCreateRequest":
        debit = sum(ln.debit_rial for ln in self.lines)
        credit = sum(ln.credit_rial for ln in self.lines)
        if debit != credit:
            raise ValueError(f"سند تراز نیست: بدهکار {debit} و بستانکار {credit}")
        if debit == 0:
            raise ValueError("سند با مبلغ صفر مجاز نیست")
        return self


class JournalLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    account_code: str | None = None
    account_name_fa: str | None = None
    position: int
    debit_rial: int
    credit_rial: int
    description: str | None = None

    @classmethod
    def from_line(cls, line: Any) -> "JournalLineResponse":
        account = getattr(line, "account", None)
        return cls(
            id=line.id,
            account_id=line.account_id,
            account_code=getattr(account, "code", None),
            account_name_fa=getattr(account, "name_fa", None),
            position=int(line.position or 0),
            debit_rial=int(line.debit_rial or 0),
            credit_rial=int(line.credit_rial or 0),
            description=line.description,
        )


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str | None = None
    fiscal_period: str | None = None
    entry_date: datetime
    source_type: str
    source_id: str | None = None
    entry_type: str
    description: str
    status: EntryStatusLiteral
    hash: str | None = None
    previous_hash: str | None = None
    posted_at: datetime | None = None
    reversal_of_id: uuid.UUID | None = None
    reversal_reason: str | None = None
    lines: list[JournalLineResponse] = Field(default_factory=list)
    total_debit_rial: int = 0
    total_credit_rial: int = 0
    balanced: bool = True
    created_at: datetime | None = None

    @classmethod
    def from_entry(cls, entry: Any) -> "JournalEntryResponse":
        lines = [JournalLineResponse.from_line(ln) for ln in (entry.lines or [])]
        debit = sum(ln.debit_rial for ln in lines)
        credit = sum(ln.credit_rial for ln in lines)
        return cls(
            id=entry.id,
            number=entry.number,
            fiscal_period=entry.fiscal_period,
            entry_date=entry.entry_date,
            source_type=(
                entry.source_type.value
                if hasattr(entry.source_type, "value")
                else str(entry.source_type)
            ),
            source_id=entry.source_id,
            entry_type=entry.entry_type,
            description=entry.description,
            status=(
                entry.status.value if hasattr(entry.status, "value") else str(entry.status)
            ),
            hash=entry.hash,
            previous_hash=entry.previous_hash,
            posted_at=entry.posted_at,
            reversal_of_id=entry.reversal_of_id,
            reversal_reason=entry.reversal_reason,
            lines=lines,
            total_debit_rial=debit,
            total_credit_rial=credit,
            balanced=debit == credit,
            created_at=entry.created_at,
        )


class JournalEntryListResponse(BaseModel):
    items: list[JournalEntryResponse]
    total: int
    page: int
    page_size: int


class ReverseEntryRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class ChainBrokenLink(BaseModel):
    entry_id: str
    number: str | None = None
    fiscal_period: str | None = None
    previous_hash_ok: bool
    own_hash_ok: bool


class ChainVerificationResponse(BaseModel):
    valid: bool
    entries_checked: int
    first_broken: ChainBrokenLink | None = None


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------


class ClosePeriodRequest(BaseModel):
    fiscal_period: str = Field(..., min_length=1, max_length=8)


class PeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fiscal_period: str
    status: PeriodStatusLiteral
    closed_at: datetime | None = None
    closed_by: uuid.UUID | None = None
    entry_count: int = 0
    debit_total_rial: int = 0
    credit_total_rial: int = 0

    @classmethod
    def from_period(cls, period: Any) -> "PeriodResponse":
        return cls(
            id=period.id,
            fiscal_period=period.fiscal_period,
            status=(
                period.status.value if hasattr(period.status, "value") else str(period.status)
            ),
            closed_at=period.closed_at,
            closed_by=period.closed_by,
            entry_count=int(period.entry_count or 0),
            debit_total_rial=int(period.debit_total_rial or 0),
            credit_total_rial=int(period.credit_total_rial or 0),
        )


class PeriodListResponse(BaseModel):
    items: list[PeriodResponse]
    total: int


class PeriodCloseResponse(PeriodResponse):
    """Close result: the locked period plus the seed's account count hint."""

    message_fa: str = "دوره مالی با موفقیت بسته شد"
