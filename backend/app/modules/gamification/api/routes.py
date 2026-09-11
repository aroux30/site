"""Gamification API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.gamification.application.gamification_service import GamificationService
from app.modules.gamification.schemas.gamification import (
    ClaimRewardRequest,
    ClaimRewardResponse,
    GamificationEventListResponse,
    GamificationEventResponse,
    GamificationRuleCreate,
    GamificationRuleResponse,
    GamificationRuleUpdate,
    RewardCreate,
    RewardResponse,
    RewardUpdate,
    UserPointsSummaryResponse,
)

router = APIRouter()


# ── Customer Endpoints ───────────────────────────────────────────────────


@router.get(
    "/summary",
    response_model=UserPointsSummaryResponse,
    summary="Get user points summary and available rewards",
)
async def get_summary(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserPointsSummaryResponse:
    """Return points summary (earned, spent, available, rank) and claimable rewards."""
    summary_data = await GamificationService.get_user_points(db, user_id=user_id)
    rewards = await GamificationService.list_rewards(db, active_only=True)
    summary_data["available_rewards"] = [RewardResponse.model_validate(r) for r in rewards]
    return UserPointsSummaryResponse(**summary_data)


@router.get(
    "/rewards",
    response_model=list[RewardResponse],
    summary="List claimable rewards",
)
async def list_rewards(
    db: AsyncSession = Depends(get_db),
) -> list[RewardResponse]:
    """List all active rewards that users can claim with points."""
    rewards = await GamificationService.list_rewards(db, active_only=True)
    return [RewardResponse.model_validate(r) for r in rewards]


@router.post(
    "/rewards/{reward_id}/claim",
    response_model=ClaimRewardResponse,
    summary="Claim a reward using loyalty points",
)
async def claim_reward(
    reward_id: uuid.UUID,
    payload: ClaimRewardRequest | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ClaimRewardResponse:
    """Deduct points and claim the specified reward."""
    try:
        response = await GamificationService.claim_reward(
            db,
            user_id=user_id,
            reward_id=reward_id,
        )
        await db.commit()
        return response
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/history",
    response_model=GamificationEventListResponse,
    summary="Get user's point earning history",
)
async def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GamificationEventListResponse:
    """Return paginated history of point-earning events for current user."""
    events, total = await GamificationService.get_user_history(
        db,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )
    items = [GamificationEventResponse.model_validate(e) for e in events]
    return GamificationEventListResponse(items=items, total=total)


# ── Admin Endpoints ──────────────────────────────────────────────────────


@router.get(
    "/admin/rules",
    response_model=list[GamificationRuleResponse],
    summary="List gamification rules (Admin)",
    dependencies=[Depends(RequirePermissions("gamification:read"))],
)
async def admin_list_rules(
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[GamificationRuleResponse]:
    """List all gamification rules."""
    rules = await GamificationService.admin_list_rules(
        db,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return [GamificationRuleResponse.model_validate(r) for r in rules]


@router.post(
    "/admin/rules",
    response_model=GamificationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a gamification rule (Admin)",
    dependencies=[Depends(RequirePermissions("gamification:write"))],
)
async def admin_create_rule(
    payload: GamificationRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> GamificationRuleResponse:
    """Create a new point-awarding rule."""
    rule = await GamificationService.admin_create_rule(db, payload)
    await db.commit()
    return GamificationRuleResponse.model_validate(rule)


@router.patch(
    "/admin/rules/{rule_id}",
    response_model=GamificationRuleResponse,
    summary="Update a gamification rule (Admin)",
    dependencies=[Depends(RequirePermissions("gamification:write"))],
)
async def admin_update_rule(
    rule_id: uuid.UUID,
    payload: GamificationRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> GamificationRuleResponse:
    """Update an existing rule."""
    try:
        rule = await GamificationService.admin_update_rule(db, rule_id, payload)
        await db.commit()
        return GamificationRuleResponse.model_validate(rule)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/admin/rewards",
    response_model=RewardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reward (Admin)",
    dependencies=[Depends(RequirePermissions("gamification:write"))],
)
async def admin_create_reward(
    payload: RewardCreate,
    db: AsyncSession = Depends(get_db),
) -> RewardResponse:
    """Create a new claimable reward."""
    reward = await GamificationService.admin_create_reward(db, payload)
    await db.commit()
    return RewardResponse.model_validate(reward)


@router.patch(
    "/admin/rewards/{reward_id}",
    response_model=RewardResponse,
    summary="Update a reward (Admin)",
    dependencies=[Depends(RequirePermissions("gamification:write"))],
)
async def admin_update_reward(
    reward_id: uuid.UUID,
    payload: RewardUpdate,
    db: AsyncSession = Depends(get_db),
) -> RewardResponse:
    """Update an existing reward."""
    try:
        reward = await GamificationService.admin_update_reward(db, reward_id, payload)
        await db.commit()
        return RewardResponse.model_validate(reward)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
