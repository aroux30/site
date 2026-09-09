"""Pydantic v2 schemas for the loyalty module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.loyalty.domain.models import LoyaltyTier, LoyaltyTransactionType


# ── Loyalty Account ───────────────────────────────────────────────────────


class LoyaltyAccountResponse(BaseModel):
    """User loyalty account summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    points: int
    tier: LoyaltyTier
    created_at: datetime
    updated_at: datetime


# ── Loyalty Transactions ──────────────────────────────────────────────────


class LoyaltyTransactionResponse(BaseModel):
    """Single loyalty transaction record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    points: int
    type: LoyaltyTransactionType
    reference_type: Optional[str] = None
    reference_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    created_at: datetime


class LoyaltyTransactionListResponse(BaseModel):
    """Paginated loyalty transaction list."""

    items: list[LoyaltyTransactionResponse]
    total: int


# ── Earn / Redeem ─────────────────────────────────────────────────────────


class EarnPointsRequest(BaseModel):
    """Request to earn loyalty points."""

    points: int = Field(..., gt=0)
    reference_type: Optional[str] = Field(None, max_length=50)
    reference_id: Optional[uuid.UUID] = None
    description: Optional[str] = None


class RedeemPointsRequest(BaseModel):
    """Request to redeem loyalty points."""

    points: int = Field(..., gt=0)
    reference_type: Optional[str] = Field(None, max_length=50)
    reference_id: Optional[uuid.UUID] = None
    description: Optional[str] = None


class PointsOperationResponse(BaseModel):
    """Response after a points operation (earn/redeem)."""

    transaction_id: uuid.UUID
    points_changed: int
    new_balance: int
    new_tier: LoyaltyTier


# ── Tier Info ─────────────────────────────────────────────────────────────


class TierInfoResponse(BaseModel):
    """Information about tier thresholds."""

    tier: LoyaltyTier
    min_points: int
    benefits: list[str]
