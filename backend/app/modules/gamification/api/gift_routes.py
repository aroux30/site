"""API routes for Gamification: gift cards, lucky wheel, signup gift, charge packages."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.gamification.application import gift_card_service, lucky_wheel_service
from app.modules.gamification.schemas.gifts import (
    ChargePackageCreateRequest,
    ChargePackageResponse,
    InternalGiftCardIssueRequest,
    InternalGiftCardRedeemRequest,
    InternalGiftCardRedeemResponse,
    InternalGiftCardResponse,
    LuckyWheelSpinRequest,
    LuckyWheelSpinResponse,
    SignupGiftResponse,
)

router = APIRouter(prefix="/gifts", tags=["gamification-gifts"])


# ── Internal Gift Card Endpoints ──────────────────────────────────────────


@router.post(
    "/cards/issue",
    response_model=InternalGiftCardResponse,
    summary="Issue a digital gift card voucher with a custom template (admin)",
    dependencies=[Depends(RequirePermissions("gamification:write"))],
)
async def issue_gift_card(
    body: InternalGiftCardIssueRequest,
    user_id: uuid.UUID | None = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InternalGiftCardResponse:
    card = await gift_card_service.issue_internal_gift_card(
        db,
        amount=body.amount,
        card_template=body.card_template,
        sender_name=body.sender_name,
        recipient_email=body.recipient_email,
        recipient_phone=body.recipient_phone,
        message=body.message,
        created_by_user_id=user_id,
        expires_at=body.expires_at,
    )
    return InternalGiftCardResponse.model_validate(card)


@router.post(
    "/cards/redeem",
    response_model=InternalGiftCardRedeemResponse,
    summary="Redeem gift card code directly into customer wallet balance",
)
async def redeem_gift_card(
    body: InternalGiftCardRedeemRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InternalGiftCardRedeemResponse:
    result = await gift_card_service.redeem_internal_gift_card(db, user_id=user_id, code=body.code)
    return InternalGiftCardRedeemResponse.model_validate(result)


# ── Lucky Spin Wheel Endpoints (Karta try_gifts) ──────────────────────────


@router.post(
    "/lucky-wheel/spin",
    response_model=LuckyWheelSpinResponse,
    summary="Spin post-order lucky wheel to win prizes or wallet credit (Karta try_gifts)",
)
async def spin_wheel(
    body: LuckyWheelSpinRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LuckyWheelSpinResponse:
    result = await lucky_wheel_service.spin_lucky_wheel_for_order(
        db, user_id=user_id, order_id=body.order_id
    )
    return LuckyWheelSpinResponse.model_validate(result)


# ── Welcome Signup Gift Endpoints (Karta signup_gift) ─────────────────────


@router.post(
    "/signup-gift/claim",
    response_model=SignupGiftResponse,
    summary="Claim welcome bonus credit upon initial phone verification",
)
async def claim_signup_bonus(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SignupGiftResponse:
    result = await lucky_wheel_service.apply_signup_gift(db, user_id=user_id)
    return SignupGiftResponse.model_validate(result)


# ── Charge Packages Endpoints (Karta charge_packages) ─────────────────────


@router.get(
    "/charge-packages",
    response_model=list[ChargePackageResponse],
    summary="List active incentive wallet top-up packages with bonus credit",
)
async def list_charge_packages(
    db: AsyncSession = Depends(get_db),
) -> list[ChargePackageResponse]:
    packages = await gift_card_service.list_active_charge_packages(db)
    return [ChargePackageResponse.model_validate(p) for p in packages]


@router.post(
    "/admin/charge-packages",
    response_model=ChargePackageResponse,
    summary="Create an incentive wallet top-up package with bonus (admin)",
    dependencies=[Depends(RequirePermissions("gamification:write"))],
)
async def create_package(
    body: ChargePackageCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ChargePackageResponse:
    pkg = await gift_card_service.create_charge_package(
        db,
        title=body.title,
        pay_amount=body.pay_amount,
        credit_amount=body.credit_amount,
        ordering=body.ordering,
    )
    return ChargePackageResponse.model_validate(pkg)
