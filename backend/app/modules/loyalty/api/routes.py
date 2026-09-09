"""Loyalty API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.loyalty.application.loyalty_service import LoyaltyService
from app.modules.loyalty.schemas.loyalty import (
    EarnPointsRequest,
    LoyaltyAccountResponse,
    LoyaltyTransactionListResponse,
    LoyaltyTransactionResponse,
    PointsOperationResponse,
    RedeemPointsRequest,
    TierInfoResponse,
)

router = APIRouter()


@router.get(
    "",
    response_model=LoyaltyAccountResponse,
    summary="Get loyalty account",
)
async def get_loyalty_account(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LoyaltyAccountResponse:
    """Return the authenticated user's loyalty account."""
    account = await LoyaltyService.get_or_create_account(db, user_id)
    return LoyaltyAccountResponse.model_validate(account)


@router.get(
    "/transactions",
    response_model=LoyaltyTransactionListResponse,
    summary="List loyalty transactions",
)
async def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LoyaltyTransactionListResponse:
    """Return paginated loyalty transactions for the authenticated user."""
    items, total = await LoyaltyService.get_transactions(
        db, user_id, skip=skip, limit=limit
    )
    return LoyaltyTransactionListResponse(
        items=[LoyaltyTransactionResponse.model_validate(t) for t in items],
        total=total,
    )


@router.post(
    "/earn",
    response_model=PointsOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Earn loyalty points",
)
async def earn_points(
    payload: EarnPointsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PointsOperationResponse:
    """Earn loyalty points for the authenticated user."""
    transaction, account = await LoyaltyService.earn_points(
        db,
        user_id,
        points=payload.points,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        description=payload.description,
    )
    return PointsOperationResponse(
        transaction_id=transaction.id,
        points_changed=payload.points,
        new_balance=account.points,
        new_tier=account.tier,
    )


@router.post(
    "/redeem",
    response_model=PointsOperationResponse,
    summary="Redeem loyalty points",
)
async def redeem_points(
    payload: RedeemPointsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PointsOperationResponse:
    """Redeem loyalty points for the authenticated user."""
    try:
        transaction, account = await LoyaltyService.redeem_points(
            db,
            user_id,
            points=payload.points,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    return PointsOperationResponse(
        transaction_id=transaction.id,
        points_changed=-payload.points,
        new_balance=account.points,
        new_tier=account.tier,
    )


@router.get(
    "/tiers",
    response_model=list[TierInfoResponse],
    summary="Get tier information",
)
async def get_tiers() -> list[TierInfoResponse]:
    """Return all loyalty tier definitions with thresholds and benefits."""
    tiers = await LoyaltyService.get_tier_info()
    return [TierInfoResponse(**t) for t in tiers]
