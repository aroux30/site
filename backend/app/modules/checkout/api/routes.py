"""Checkout API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.checkout.application import checkout_service
from app.modules.checkout.schemas.checkout import (
    CheckoutQuoteRequest,
    CheckoutQuoteResponse,
    CheckoutValidationResponse,
    CreateOrderRequest,
    CreateOrderResponse,
)

router = APIRouter()


@router.post(
    "/quote",
    response_model=CheckoutQuoteResponse,
    summary="Calculate order quote with shipping and discounts",
)
async def calculate_quote(
    body: CheckoutQuoteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CheckoutQuoteResponse:
    return await checkout_service.calculate_quote(db, user_id, body)


@router.post(
    "/validate",
    response_model=CheckoutValidationResponse,
    summary="Validate checkout readiness (stock, address, coupon)",
)
async def validate_checkout(
    body: CheckoutQuoteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CheckoutValidationResponse:
    return await checkout_service.validate_checkout(db, user_id, body)


@router.post(
    "/create-order",
    response_model=CreateOrderResponse,
    summary="Create order — full checkout flow",
)
async def create_order(
    body: CreateOrderRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CreateOrderResponse:
    # Extract client IP for audit
    ip_address = request.client.host if request.client else None

    return await checkout_service.create_order(
        db,
        user_id=user_id,
        data=body,
        ip_address=ip_address,
    )
