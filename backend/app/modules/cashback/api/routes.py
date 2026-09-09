"""Cashback API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.cashback.application.cashback_service import CashbackService
from app.modules.cashback.schemas.cashback import (
    CashbackRuleCreate,
    CashbackRuleListResponse,
    CashbackRuleResponse,
    CashbackRuleUpdate,
    CashbackTransactionListResponse,
    CashbackTransactionResponse,
)

router = APIRouter()


# ── User Endpoints ────────────────────────────────────────────────────────


@router.get(
    "/transactions",
    response_model=CashbackTransactionListResponse,
    summary="List user cashback transactions",
)
async def list_user_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CashbackTransactionListResponse:
    """Return paginated cashback transactions for the authenticated user."""
    items, total = await CashbackService.get_user_transactions(
        db, user_id, skip=skip, limit=limit
    )
    return CashbackTransactionListResponse(
        items=[CashbackTransactionResponse.model_validate(t) for t in items],
        total=total,
    )


# ── Admin Endpoints ──────────────────────────────────────────────────────


@router.get(
    "/admin/rules",
    response_model=CashbackRuleListResponse,
    summary="List cashback rules (admin)",
    dependencies=[Depends(RequirePermissions("cashback:read"))],
)
async def list_rules(
    is_active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CashbackRuleListResponse:
    """Return paginated cashback rules (admin only)."""
    items, total = await CashbackService.list_rules(
        db, is_active=is_active, skip=skip, limit=limit
    )
    return CashbackRuleListResponse(
        items=[CashbackRuleResponse.model_validate(r) for r in items],
        total=total,
    )


@router.post(
    "/admin/rules",
    response_model=CashbackRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create cashback rule (admin)",
    dependencies=[Depends(RequirePermissions("cashback:write"))],
)
async def create_rule(
    payload: CashbackRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> CashbackRuleResponse:
    """Create a new cashback rule."""
    rule = await CashbackService.create_rule(db, **payload.model_dump())
    return CashbackRuleResponse.model_validate(rule)


@router.get(
    "/admin/rules/{rule_id}",
    response_model=CashbackRuleResponse,
    summary="Get cashback rule (admin)",
    dependencies=[Depends(RequirePermissions("cashback:read"))],
)
async def get_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CashbackRuleResponse:
    """Get a single cashback rule by ID."""
    rule = await CashbackService.get_rule(db, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cashback rule not found.",
        )
    return CashbackRuleResponse.model_validate(rule)


@router.patch(
    "/admin/rules/{rule_id}",
    response_model=CashbackRuleResponse,
    summary="Update cashback rule (admin)",
    dependencies=[Depends(RequirePermissions("cashback:write"))],
)
async def update_rule(
    rule_id: uuid.UUID,
    payload: CashbackRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> CashbackRuleResponse:
    """Update an existing cashback rule."""
    try:
        rule = await CashbackService.update_rule(
            db, rule_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    return CashbackRuleResponse.model_validate(rule)


@router.delete(
    "/admin/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete cashback rule (admin)",
    dependencies=[Depends(RequirePermissions("cashback:write"))],
)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate (soft-delete) a cashback rule."""
    try:
        await CashbackService.delete_rule(db, rule_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
