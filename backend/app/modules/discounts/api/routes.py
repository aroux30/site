"""Discount / Coupon API routes — customer and admin endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.modules.discounts.application import discount_service
from app.modules.discounts.schemas.discount import (
    CouponApplyRequest,
    CouponApplyResponse,
    CouponRemoveRequest,
    CouponRemoveResponse,
    DiscountCreateRequest,
    DiscountListResponse,
    DiscountResponse,
    DiscountUpdateRequest,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════
# Customer endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/coupons/apply",
    response_model=CouponApplyResponse,
    summary="Validate and preview a coupon code",
)
async def apply_coupon(
    body: CouponApplyRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    cart_total: int = Query(
        ...,
        ge=0,
        description="Current cart subtotal in Rials (required for discount calculation)",
    ),
) -> CouponApplyResponse:
    """Validate the coupon and return the computed discount amount.

    The coupon is **not** consumed here — actual redemption happens during
    order creation via the checkout flow.
    """
    return await discount_service.validate_coupon(
        db,
        code=body.code,
        user_id=user_id,
        cart_total=cart_total,
    )


@router.post(
    "/coupons/remove",
    response_model=CouponRemoveResponse,
    summary="Remove a previously applied coupon from the session",
)
async def remove_coupon(
    body: CouponRemoveRequest,
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> CouponRemoveResponse:
    """Mark the coupon as removed from the user's current session.

    This is a stateless acknowledgement — actual coupon state is managed
    client-side or in the cart service.
    """
    return CouponRemoveResponse(code=body.code, removed=True)


# ══════════════════════════════════════════════════════════════════════════
# Admin endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/admin/discounts",
    response_model=DiscountListResponse,
    summary="Admin — list discount rules",
    dependencies=[Depends(RequirePermissions("discounts:read"))],
)
async def admin_list_discounts(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False, description="Include deactivated discounts"),
) -> DiscountListResponse:
    return await discount_service.get_active_discounts(
        db,
        page=page,
        page_size=page_size,
        include_inactive=include_inactive,
    )


@router.post(
    "/admin/discounts",
    response_model=DiscountResponse,
    summary="Admin — create a discount rule",
    dependencies=[Depends(RequirePermissions("discounts:write"))],
)
async def admin_create_discount(
    body: DiscountCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> DiscountResponse:
    return await discount_service.create_discount(db, body)


@router.patch(
    "/admin/discounts/{discount_id}",
    response_model=DiscountResponse,
    summary="Admin — update a discount rule",
    dependencies=[Depends(RequirePermissions("discounts:write"))],
)
async def admin_update_discount(
    discount_id: uuid.UUID,
    body: DiscountUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> DiscountResponse:
    return await discount_service.update_discount(db, discount_id, body)
