"""Pydantic v2 schemas for the cashback module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.modules.cashback.domain.models import CashbackRuleType, CashbackTransactionStatus


def _percent_to_bp(p: float) -> int:
    """Convert a percent value (0 < p <= 100) to integer basis points (1% = 100 bp)."""
    return round(p * 100)


def _bp_to_percent(bp: int) -> float:
    """Convert integer basis points to percent for the API contract (1% = 100 bp)."""
    return bp / 100

# ── Cashback Rules ────────────────────────────────────────────────────────


class CashbackRuleCreate(BaseModel):
    """Payload to create a new cashback rule."""

    name: str = Field(..., max_length=200)
    type: CashbackRuleType
    scope_id: str | None = Field(None, max_length=255)
    percentage: float = Field(..., gt=0, le=100)
    max_amount: int | None = Field(None, gt=0)
    is_active: bool = True
    starts_at: datetime
    ends_at: datetime


class CashbackRuleUpdate(BaseModel):
    """Payload to update an existing cashback rule."""

    name: str | None = Field(None, max_length=200)
    type: CashbackRuleType | None = None
    scope_id: str | None = Field(None, max_length=255)
    percentage: float | None = Field(None, gt=0, le=100)
    max_amount: int | None = Field(None, gt=0)
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CashbackRuleResponse(BaseModel):
    """Single cashback rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: CashbackRuleType
    scope_id: str | None = None
    percentage_bp: int
    max_amount: int | None = None
    is_active: bool
    starts_at: datetime
    ends_at: datetime
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def percentage(self) -> float:
        """Percent-unit view of the stored integer basis points."""
        return _bp_to_percent(self.percentage_bp)


class CashbackRuleListResponse(BaseModel):
    """Paginated cashback rule list."""

    items: list[CashbackRuleResponse]
    total: int


# ── Cashback Transactions ────────────────────────────────────────────────


class CashbackTransactionResponse(BaseModel):
    """Single cashback transaction response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    order_id: uuid.UUID
    rule_id: uuid.UUID
    amount: int
    status: CashbackTransactionStatus
    created_at: datetime


class CashbackTransactionListResponse(BaseModel):
    """Paginated cashback transaction list."""

    items: list[CashbackTransactionResponse]
    total: int


class CashbackCalculationResponse(BaseModel):
    """Response after calculating cashback for an order."""

    total_cashback: int
    transactions_created: int
