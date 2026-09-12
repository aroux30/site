"""Pydantic v2 schemas for KYC, Shahkar identity, and bank cards (Karta Phase 1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.domain.kyc_models import DeliveryRiskLevel

# ── Shahkar Verification Schemas ──────────────────────────────────────────


class ShahkarVerificationRequest(BaseModel):
    """Payload to verify National Code against mobile."""

    national_code: str = Field(..., min_length=10, max_length=10, description="10-digit Iranian National Code")
    birth_date: date | None = Field(None, description="Birth date for Civil Registry verification (Zohal)")


class ShahkarVerificationResponse(BaseModel):
    user_id: uuid.UUID
    is_verified: bool
    is_trusted: bool
    risk_score: int
    verified_at: datetime | None = None


# ── Bank Card Schemas ─────────────────────────────────────────────────────


class BankCardRegisterRequest(BaseModel):
    """Payload to register and verify customer bank card."""

    card_number: str = Field(..., min_length=16, max_length=19, description="16-digit debit card number")
    iban: str | None = Field(None, max_length=30, description="Optional Sheba/IBAN number")
    is_default: bool = False


class BankCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    card_pan_masked: str
    iban: str | None = None
    bank_name: str | None = None
    is_verified: bool
    is_default: bool
    verified_at: datetime | None = None
    created_at: datetime


class CardMatchVerifyRequest(BaseModel):
    """Payload for gateway callback verification."""

    payment_card_pan: str = Field(..., description="Card PAN returned by Shaparak PSP")


class CardMatchVerifyResponse(BaseModel):
    is_matched: bool
    user_id: uuid.UUID
    message: str


# ── Delivery Policy & Trust Profile ───────────────────────────────────────


class UserTrustProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    is_trusted: bool
    shahkar_verified: bool
    risk_score: int
    delayed_delivery_enabled: bool
    daily_spend_limit: int
    verified_at: datetime | None = None


class DeliveryPolicyEvaluationResponse(BaseModel):
    user_id: uuid.UUID
    order_amount: int
    delivery_policy: DeliveryRiskLevel
    is_instant_eligible: bool
