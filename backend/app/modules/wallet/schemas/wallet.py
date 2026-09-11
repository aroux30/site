"""Pydantic v2 schemas for the wallet module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.wallet.domain.models import WalletTransactionType

# ── Request Schemas ───────────────────────────────────────────────────────


class WalletDepositRequest(BaseModel):
    """Deposit funds into the user's wallet."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: int = Field(..., gt=0, description="Amount to deposit in IRR (Rials)")


class WalletWithdrawRequest(BaseModel):
    """Withdraw funds from the user's wallet."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: int = Field(..., gt=0, description="Amount to withdraw in IRR (Rials)")


# ── Response Schemas ──────────────────────────────────────────────────────


class WalletResponse(BaseModel):
    """Current wallet state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    balance: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WalletTransactionResponse(BaseModel):
    """A single wallet transaction."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wallet_id: uuid.UUID
    amount: int
    type: WalletTransactionType
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    description: str | None = None
    balance_after: int
    created_at: datetime


class WalletTransactionListResponse(BaseModel):
    """Paginated list of wallet transactions."""

    items: list[WalletTransactionResponse]
    total: int
    page: int
    page_size: int
    pages: int
