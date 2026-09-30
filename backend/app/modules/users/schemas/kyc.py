"""Pydantic v2 schemas for KYC, Shahkar identity, and bank cards (Karta Phase 1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.users.domain.kyc_models import DeliveryRiskLevel

# ── Shahkar Verification Schemas ──────────────────────────────────────────


class ShahkarVerificationRequest(BaseModel):
    """Payload to verify National Code against mobile."""

    national_code: str = Field(
        ...,
        min_length=10,
        max_length=10,
        description="10-digit Iranian National Code",
    )

    @field_validator("national_code")
    @classmethod
    def validate_national_code(cls, v: str) -> str:
        import re

        from app.modules.users.application.validation_utils import (
            normalise_digits,
        )
        from app.modules.users.application.validation_utils import (
            validate_national_code as check_national_code,
        )

        clean = re.sub(r"\D", "", normalise_digits(v)).strip()
        if not check_national_code(clean):
            raise ValueError("کد ملی وارد شده معتبر نیست (کنترل رقم چک Modulo-11)")
        return clean
    birth_date: date | None = Field(
        None,
        description="Birth date for Civil Registry verification (Zohal)",
    )
    mobile: str | None = Field(
        None,
        max_length=15,
        description=(
            "Mobile to match (defaults to the account's own phone; "
            "a provider credential is required for any real verification)"
        ),
    )


class ShahkarVerificationResponse(BaseModel):
    """Verification outcome — never a fake success (P0.1).

    ``status``: verified | failed | unavailable
    """

    status: str
    message: str | None = None
    user_id: uuid.UUID
    is_verified: bool
    is_trusted: bool
    risk_score: int
    verified_at: datetime | None = None


# ── Bank Card Schemas ─────────────────────────────────────────────────────


class BankCardRegisterRequest(BaseModel):
    """Payload to register and verify customer bank card."""

    card_number: str = Field(
        ...,
        min_length=16,
        max_length=19,
        description="16-digit debit card number",
    )
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

    @field_validator("iban")
    @classmethod
    def mask_iban_field(cls, v: str | None) -> str | None:
        if v:
            from app.core.security.data_protection import mask_iban
            return mask_iban(v)
        return v


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


# ── Admin Security Endpoints (Karta failed_attempts panel) ────────────────


class FailedAttemptResponse(BaseModel):
    """A persisted failed security operation for the admin panel (P1.4)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    identifier: str
    attempt_type: str
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class FailedAttemptListResponse(BaseModel):
    items: list[FailedAttemptResponse]
    total: int
