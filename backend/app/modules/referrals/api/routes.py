"""Referral API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.referrals.application.referral_service import ReferralService
from app.modules.referrals.schemas.referral import (
    CommissionListResponse,
    CommissionResponse,
    ReferralCodeResponse,
    ReferralListResponse,
    ReferralResponse,
    ReferralStatsResponse,
)

router = APIRouter()


@router.get(
    "/referral",
    response_model=ReferralCodeResponse,
    summary="Get or generate referral code",
)
async def get_referral_code(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReferralCodeResponse:
    """Return the authenticated user's unique referral code and link."""
    code = await ReferralService.get_or_create_referral_code(db, user_id)
    return ReferralCodeResponse(
        referral_code=code,
        referral_link=f"/register?ref={code}",
    )


@router.get(
    "/referral/stats",
    response_model=ReferralStatsResponse,
    summary="Referral statistics",
)
async def get_referral_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReferralStatsResponse:
    """Return aggregated referral statistics for the authenticated user."""
    stats = await ReferralService.get_referral_stats(db, user_id)
    return ReferralStatsResponse(**stats)


@router.get(
    "/referral/commissions",
    response_model=CommissionListResponse,
    summary="List commissions",
)
async def list_commissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommissionListResponse:
    """Return paginated commission records for the authenticated user."""
    items, total = await ReferralService.get_commissions(db, user_id, skip=skip, limit=limit)
    return CommissionListResponse(
        items=[CommissionResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get(
    "/referrals",
    response_model=ReferralListResponse,
    summary="List referrals",
)
async def list_referrals(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReferralListResponse:
    """Return paginated referral records for the authenticated user."""
    items, total = await ReferralService.get_referrals(db, user_id, skip=skip, limit=limit)
    return ReferralListResponse(
        items=[ReferralResponse.model_validate(r) for r in items],
        total=total,
    )
