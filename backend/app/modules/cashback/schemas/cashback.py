"""Pydantic v2 schemas for the cashback module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.cashback.domain.models import CashbackRuleType, CashbackTransactionStatus


# ── Cashback Rules ────────────────────────────────────────────────────────


class CashbackRuleCreate(BaseModel):
    """Payload to create a new cashback rule."""

    name: str = Field(..., max_length=200)
    type: CashbackRuleType
    scope_id: Optional[str] = Field(None, max_length=255)
    percentage: float = Field(..., gt=0, le=100)
    max_amount: Optional[int] = Field(None, gt=0)
    is_active: bool = True
    starts_at: datetime
    ends_at: datetime


class CashbackRuleUpdate(BaseModel):
    """Payload to update an existing cashback rule."""

    name: Optional[str] = Field(None, max_length=200)
    type: Optional[CashbackRuleType] = None
    scope_id: Optional[str] = Field(None, max_length=255)
    percentage: Optional[float] = Field(None, gt=0, le=100)
    max_amount: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class CashbackRuleResponse(BaseModel):
    """Single cashback rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: CashbackRuleType
    scope_id: Optional[str] = None
    percentage: float
    max_amount: Optional[int] = None
    is_active: bool
    starts_at: datetime
    ends_at: datetime
    created_at: datetime
    updated_at: datetime


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
