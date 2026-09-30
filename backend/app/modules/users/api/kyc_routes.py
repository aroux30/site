"""API endpoints for KYC, Shahkar identity, and bank cards (Karta Phase 1)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.users.application import bank_card_service, kyc_service
from app.modules.users.domain.kyc_models import DeliveryRiskLevel
from app.modules.users.schemas.kyc import (
    BankCardRegisterRequest,
    BankCardResponse,
    CardMatchVerifyRequest,
    CardMatchVerifyResponse,
    DeliveryPolicyEvaluationResponse,
    ShahkarVerificationRequest,
    ShahkarVerificationResponse,
    UserTrustProfileResponse,
)

router = APIRouter(prefix="/kyc", tags=["users-kyc"])


# ── Customer Shahkar Endpoints ────────────────────────────────────────────


@router.post(
    "/shahkar/verify",
    response_model=ShahkarVerificationResponse,
    summary="Verify National Code against mobile using Shahkar (Karta Zohal)",
)
@limiter.limit("5/minute")
async def verify_shahkar(
    request: Request,
    body: ShahkarVerificationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ShahkarVerificationResponse:
    result = await kyc_service.verify_user_shahkar(
        db,
        user_id=user_id,
        national_code=body.national_code,
        birth_date=body.birth_date,
        mobile=body.mobile,
    )
    return ShahkarVerificationResponse.model_validate(result)


@router.get(
    "/trust-profile",
    response_model=UserTrustProfileResponse,
    summary="Get user trust profile and risk metrics (customer view)",
)
async def get_trust_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserTrustProfileResponse:
    from app.modules.users.application.kyc_service import get_trust_profile
    from app.modules.users.domain.kyc_models import UserTrustProfile

    # Lookup must key off user_id — UserTrustProfile.id is a surrogate PK.
    trust = await get_trust_profile(db, user_id)
    if trust is None:
        # Column-level defaults only apply on flush; this preview object is
        # never persisted, so every response field must be set explicitly.
        trust = UserTrustProfile(
            user_id=user_id,
            is_trusted=False,
            shahkar_verified=False,
            risk_score=50,
            delayed_delivery_enabled=True,
            daily_spend_limit=50_000_000,
        )
    return UserTrustProfileResponse.model_validate(trust)


# ── Customer Bank Card Endpoints (Karta Mana / Nehab) ─────────────────────


@router.post(
    "/bank-cards",
    response_model=BankCardResponse,
    summary="Register and verify a bank card for checkout (Mana / Nehab)",
)
@limiter.limit("10/minute")
async def register_bank_card(
    request: Request,
    body: BankCardRegisterRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BankCardResponse:
    card = await bank_card_service.register_user_bank_card(
        db,
        user_id=user_id,
        card_number=body.card_number,
        iban=body.iban,
        is_default=body.is_default,
    )
    return BankCardResponse.model_validate(card)


@router.get(
    "/bank-cards",
    response_model=list[BankCardResponse],
    summary="List registered verified bank cards for customer",
)
async def list_bank_cards(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[BankCardResponse]:
    cards = await bank_card_service.list_user_bank_cards(db, user_id=user_id)
    return [BankCardResponse.model_validate(c) for c in cards]


@router.post(
    "/bank-cards/verify-match",
    response_model=CardMatchVerifyResponse,
    summary="Verify if payment card PAN matches user verified cards (anti-phishing)",
)
async def verify_card_match(
    body: CardMatchVerifyRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CardMatchVerifyResponse:
    matched = await bank_card_service.verify_payment_card_match(
        db, user_id=user_id, payment_card_pan=body.payment_card_pan
    )
    msg = (
        "کارت پرداخت متعلق به کاربر است و تایید شد"
        if matched
        else "کارت پرداخت با کارت‌های ثبت‌شده کاربر تطابق ندارد"
    )
    return CardMatchVerifyResponse(is_matched=matched, user_id=user_id, message=msg)


# ── Delivery Policy Evaluation ────────────────────────────────────────────


@router.get(
    "/delivery-policy",
    response_model=DeliveryPolicyEvaluationResponse,
    summary="Evaluate Instant vs. Delayed delivery routing for an order amount",
)
async def evaluate_delivery(
    order_amount: int = Query(..., ge=0, description="Total order amount in IRR"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DeliveryPolicyEvaluationResponse:
    policy = await kyc_service.evaluate_delivery_policy(
        db, user_id=user_id, order_amount=order_amount
    )
    return DeliveryPolicyEvaluationResponse(
        user_id=user_id,
        order_amount=order_amount,
        delivery_policy=policy,
        is_instant_eligible=policy == DeliveryRiskLevel.INSTANT,
    )
