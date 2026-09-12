"""Pydantic v2 schemas for Gamification: Gift Cards, Lucky Wheel, and Charge Packages (Karta Phase
5/7)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.gamification.domain.gift_models import PrizeType

# ── Internal Gift Card Schemas ────────────────────────────────────────────


class InternalGiftCardIssueRequest(BaseModel):
    """Admin or user payload to purchase/issue a digital gift voucher."""

    amount: int = Field(..., ge=10_000, description="Gift card amount in IRR")
    card_template: str = Field(
        "gold",
        max_length=32,
        description="Visual theme: gold, birthday, festive, vip",
    )
    sender_name: str | None = Field(None, max_length=100)
    recipient_email: str | None = Field(None, max_length=255)
    recipient_phone: str | None = Field(None, max_length=20)
    message: str | None = Field(None, max_length=1000)
    expires_at: datetime | None = None


class InternalGiftCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    amount: int
    remaining_balance: int
    card_template: str
    sender_name: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    message: str | None = None
    is_active: bool
    claimed_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class InternalGiftCardRedeemRequest(BaseModel):
    """Payload to redeem a gift card code into wallet balance."""

    code: str = Field(..., min_length=1, max_length=64, description="Gift card voucher code")


class InternalGiftCardRedeemResponse(BaseModel):
    code: str
    amount_credited: int
    claimed_at: datetime | None = None
    message: str = "مبلغ کارت هدیه با موفقیت به کیف‌پول شما افزوده شد"


# ── Lucky Wheel Schemas ───────────────────────────────────────────────────


class LuckyWheelSpinRequest(BaseModel):
    """Payload to spin lucky wheel after order completion."""

    order_id: uuid.UUID = Field(..., description="Completed order ID")


class LuckyWheelSpinResponse(BaseModel):
    order_id: uuid.UUID
    prize_title: str
    prize_type: str
    awarded_value: int
    message: str


class LuckyWheelPrizeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    prize_type: PrizeType
    value: int
    probability_weight: int
    icon: str | None = None
    is_active: bool


# ── Signup Gift Schemas ───────────────────────────────────────────────────


class SignupGiftResponse(BaseModel):
    user_id: uuid.UUID
    awarded_amount: int
    transaction_id: uuid.UUID | None = None
    new_balance: int | None = None
    message: str = "هدیه ثبت‌نام و خوش‌آمدگویی با موفقیت به کیف‌پول شما اضافه شد"


# ── Charge Package Schemas ────────────────────────────────────────────────


class ChargePackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    pay_amount: int
    credit_amount: int
    is_active: bool
    ordering: int
    bonus_amount: int = 0

    def model_post_init(self, __context: object) -> None:
        object.__setattr__(self, "bonus_amount", max(0, self.credit_amount - self.pay_amount))


class ChargePackageCreateRequest(BaseModel):
    """Admin payload to configure incentive top-up package."""

    title: str = Field(..., min_length=1, max_length=100)
    pay_amount: int = Field(..., ge=10_000, description="Amount customer pays in IRR")
    credit_amount: int = Field(..., ge=10_000, description="Total credit customer receives in IRR")
    ordering: int = Field(0, ge=0)
