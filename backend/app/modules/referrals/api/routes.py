"""Referral API routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.referrals.application import referral_config
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
admin_router = APIRouter(prefix="/admin/referrals", tags=["admin-referrals"])

_require_read = Depends(RequirePermissions("referrals:read"))
_require_write = Depends(RequirePermissions("referrals:write"))

#: Read-path ceiling for the customer-facing referral endpoints. They are
#: authenticated and cheap, but they hit the DB on every poll from the
#: account panel — a ceiling stops one leaked token from hammering them.
_READ_LIMIT = "60/minute"
#: Admin read ceiling — the history/export endpoints run aggregate queries;
#: the ceiling keeps a runaway dashboard tab from saturating the DB.
_ADMIN_READ_LIMIT = "120/minute"
#: Admin write ceiling — config saves are rare and expensive (one JSONB
#: upsert + audit); anything above a handful per minute is a script, not an
#: operator.
_ADMIN_WRITE_LIMIT = "20/minute"
#: Export ceiling — the CSV build scans the reward history; 10/minute is far
#: above any human clicking and far below a loop.
_EXPORT_LIMIT = "10/minute"


class ReferralConfigUpdateRequest(BaseModel):
    """Partial config update — only known keys are applied."""

    config: dict[str, Any]


class ReferralConfigResponse(BaseModel):
    """Full program config."""

    config: dict[str, Any]


class RewardHistoryItem(BaseModel):
    """One paid reward row (from the wallet ledger, with its context)."""

    id: str
    kind: str
    amount: int
    created_at: str | None
    earner_id: str
    earner_name: str
    earner_phone: str | None = None
    level: int | None = None
    invited_user_name: str | None = None
    order_number: str | None = None
    payment_amount: int | None = None


class RewardHistoryResponse(BaseModel):
    """Paginated reward payout history."""

    items: list[RewardHistoryItem]
    total: int


@router.get(
    "/referral",
    response_model=ReferralCodeResponse,
    summary="Get or generate referral code",
)
@limiter.limit(_READ_LIMIT)
async def get_referral_code(
    request: Request,
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
@limiter.limit(_READ_LIMIT)
async def get_referral_stats(
    request: Request,
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
@limiter.limit(_READ_LIMIT)
async def list_commissions(
    request: Request,
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
@limiter.limit(_READ_LIMIT)
async def list_referrals(
    request: Request,
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


# ── Admin: program configuration + reward history ─────────────────────────


@admin_router.get(
    "/config",
    response_model=ReferralConfigResponse,
    summary="Admin — get referral program config",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_READ_LIMIT)
async def admin_get_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ReferralConfigResponse:
    """Return the full referral/bonus program configuration."""
    return ReferralConfigResponse(config=await referral_config.get_config(db))


@admin_router.put(
    "/config",
    response_model=ReferralConfigResponse,
    summary="Admin — update referral program config",
    dependencies=[_require_write],
)
@limiter.limit(_ADMIN_WRITE_LIMIT)
async def admin_update_config(
    request: Request,
    payload: ReferralConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ReferralConfigResponse:
    """Upsert the program config (only known keys are applied)."""
    config = await referral_config.set_config(db, payload.config)
    await db.commit()
    return ReferralConfigResponse(config=config)


@admin_router.get(
    "/history",
    response_model=RewardHistoryResponse,
    summary="Admin — reward payout history",
    dependencies=[_require_read],
)
@limiter.limit(_ADMIN_READ_LIMIT)
async def admin_reward_history(
    request: Request,
    kind: str | None = Query(
        None,
        pattern="^(signup_gift|commission|recharge_bonus)$",
        description="Filter by reward type; omit for all",
    ),
    q: str | None = Query(
        None,
        max_length=100,
        description="Free-text search: earner name/phone, order number, invited user",
    ),
    date_from: date | None = Query(
        None, description="Only rewards created on/after this date (inclusive)"
    ),
    date_to: date | None = Query(
        None, description="Only rewards created on/before this date (inclusive)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RewardHistoryResponse:
    """Every reward the program has paid, with who received it and why.

    Read from the wallet ledger (``wallet_transactions``) — the single source
    of truth for money that actually moved — joined to the earner and, per
    kind, to the referral chain / order / top-up that caused it.
    """
    from app.modules.referrals.application.reward_history import (
        fetch_reward_history,
    )

    items, total = await fetch_reward_history(
        db, kind=kind, q=q, date_from=date_from, date_to=date_to, skip=skip, limit=limit
    )
    return RewardHistoryResponse(
        items=[RewardHistoryItem(**item) for item in items], total=total
    )


@admin_router.get(
    "/history/export.csv",
    summary="Admin — reward history as Excel-safe CSV",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
@limiter.limit(_EXPORT_LIMIT)
async def admin_reward_history_export(
    request: Request,
    kind: str | None = Query(
        None, pattern="^(signup_gift|commission|recharge_bonus)$"
    ),
    q: str | None = Query(None, max_length=100),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The FILTERED history as a downloadable CSV (UTF-8 BOM for Excel).

    Same filters as the tab; all matching rows (capped at 50k). Uses the
    reporting module's builder — formula-injection hardened, the project's
    single CSV convention.
    """
    from app.modules.referrals.application.reward_history import (
        build_reward_history_csv,
    )

    csv_bytes = await build_reward_history_csv(
        db, kind=kind, q=q, date_from=date_from, date_to=date_to
    )
    stamp = date.today().strftime("%Y%m%d")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="referral-rewards-{stamp}.csv"'
        },
    )
