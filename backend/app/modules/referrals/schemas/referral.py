"""Pydantic v2 schemas for the referrals module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.referrals.domain.models import CommissionStatus, ReferralStatus


# ── Referral ──────────────────────────────────────────────────────────────


class ReferralCodeResponse(BaseModel):
    """Response containing the user's unique referral code."""

    model_config = ConfigDict(from_attributes=True)

    referral_code: str
    referral_link: str


class ReferralResponse(BaseModel):
    """Single referral record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    referrer_id: uuid.UUID
    referred_id: uuid.UUID
    code: str
    level: int
    status: ReferralStatus
    created_at: datetime


class ReferralStatsResponse(BaseModel):
    """Aggregated referral statistics for a user."""

    model_config = ConfigDict(from_attributes=True)

    total_referrals: int = 0
    completed_referrals: int = 0
    pending_referrals: int = 0
    level1_count: int = 0
    level2_count: int = 0
    total_commission_earned: int = 0
    total_commission_pending: int = 0


# ── Commissions ───────────────────────────────────────────────────────────


class CommissionResponse(BaseModel):
    """Single commission record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    referral_id: uuid.UUID
    order_id: uuid.UUID
    amount: int
    level: int
    status: CommissionStatus
    created_at: datetime


class CommissionListResponse(BaseModel):
    """Paginated commission list."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CommissionResponse]
    total: int


class ReferralListResponse(BaseModel):
    """Paginated referral list."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReferralResponse]
    total: int
