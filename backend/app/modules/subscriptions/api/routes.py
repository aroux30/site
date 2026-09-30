"""Subscription API routes — customer self-service and admin operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.database.session import get_db
from app.core.exceptions.handlers import ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.subscriptions.application import subscription_service
from app.modules.subscriptions.domain.models import (
    Subscription,
    SubscriptionBilling,
    SubscriptionInterval,
)
from app.modules.subscriptions.schemas.subscription import (
    CancelSubscriptionRequest,
    CreateSubscriptionRequest,
    SubscriptionBillingResponse,
    SubscriptionDetailResponse,
    SubscriptionResponse,
    SubscriptionRunResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
# The admin_router is mounted with the API prefix only (the platform
# convention — see main._include_routers), so its paths are written in full:
# /admin/subscriptions/... keeps admin operations out of the customer router
# and matches how audit, invoicing et al. expose theirs.
_ADMIN = "/admin/subscriptions"
admin_router = APIRouter()


def _detail(subscription: Subscription) -> SubscriptionDetailResponse:
    """Serialise a subscription with its billing history, newest first."""
    billings = sorted(
        subscription.billings or [], key=lambda b: b.period_index, reverse=True
    )
    base = SubscriptionResponse.from_model(subscription)
    return SubscriptionDetailResponse(
        **base.model_dump(),
        billings=[SubscriptionBillingResponse.model_validate(b) for b in billings],
    )


# ══════════════════════════════════════════════════════════════════════════
# Customer endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "",
    response_model=SubscriptionDetailResponse,
    status_code=201,
    summary="Create a subscription (subscriber)",
)
async def create_subscription(
    body: CreateSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionDetailResponse:
    """Create a subscription. The first cycle bills on the next run.

    A saved card is optional: without one the customer pays each renewal
    manually from their account.
    """
    try:
        interval = SubscriptionInterval(body.interval)
    except ValueError:
        raise ValidationError(
            detail="دوره اشتراک نامعتبر است",
            error_code="INVALID_INTERVAL",
        ) from None

    subscription = await subscription_service.create_subscription(
        db,
        user_id=user_id,
        name=body.name,
        interval=interval,
        interval_count=body.interval_count,
        custom_interval_days=body.custom_interval_days,
        saved_method_id=body.saved_method_id,
        items=[item.model_dump() for item in body.items],
        shipping_address_snapshot=body.shipping_address_snapshot,
        notes=body.notes,
    )
    await db.refresh(subscription)
    return _detail(subscription)


@router.get(
    "",
    response_model=list[SubscriptionResponse],
    summary="List current user's subscriptions",
)
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[SubscriptionResponse]:
    """Return the caller's subscriptions, newest first."""
    subs = await subscription_service.list_user_subscriptions(db, user_id=user_id)
    return [SubscriptionResponse.from_model(s) for s in subs]


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionDetailResponse,
    summary="One subscription with billing history",
)
async def get_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionDetailResponse:
    """Return one of the caller's subscriptions with its billing cycles."""
    subscription = await subscription_service.get_subscription(
        db, subscription_id=subscription_id, user_id=user_id
    )
    return _detail(subscription)


@router.post(
    "/{subscription_id}/pause",
    response_model=SubscriptionResponse,
    summary="Pause a subscription",
)
async def pause_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """Pause billing. The pause window is never back-billed."""
    subscription = await subscription_service.pause_subscription(
        db, subscription_id=subscription_id, user_id=user_id
    )
    return SubscriptionResponse.from_model(subscription)


@router.post(
    "/{subscription_id}/resume",
    response_model=SubscriptionResponse,
    summary="Resume a paused subscription",
)
async def resume_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """Resume billing from now; the schedule re-anchors to the resume moment."""
    subscription = await subscription_service.resume_subscription(
        db, subscription_id=subscription_id, user_id=user_id
    )
    return SubscriptionResponse.from_model(subscription)


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel a subscription",
)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    body: CancelSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """Cancel for good. Idempotent — cancelling twice is not an error."""
    subscription = await subscription_service.cancel_subscription(
        db,
        subscription_id=subscription_id,
        user_id=user_id,
        reason=body.reason,
    )
    return SubscriptionResponse.from_model(subscription)


# ══════════════════════════════════════════════════════════════════════════
# Admin endpoints
# ══════════════════════════════════════════════════════════════════════════


@admin_router.get(
    _ADMIN,
    response_model=list[SubscriptionResponse],
    dependencies=[Depends(RequirePermissions("subscriptions:read"))],
    summary="List subscriptions (admin)",
)
async def admin_list_subscriptions(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, description="Filter by status"),
    user_id: uuid.UUID | None = Query(None, description="Filter by owner"),
    limit: int = Query(100, ge=1, le=500),
) -> list[SubscriptionResponse]:
    """List subscriptions for support and finance. Requires ``subscriptions:read``."""
    stmt = select(Subscription).order_by(Subscription.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Subscription.status == status)
    if user_id:
        stmt = stmt.where(Subscription.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [SubscriptionResponse.from_model(s) for s in rows]


@admin_router.get(
    f"{_ADMIN}/{{subscription_id}}",
    response_model=SubscriptionDetailResponse,
    dependencies=[Depends(RequirePermissions("subscriptions:read"))],
    summary="One subscription with billing history (admin)",
)
async def admin_get_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailResponse:
    """Any subscription with its billing cycles. Requires ``subscriptions:read``."""
    subscription = await subscription_service.get_subscription(
        db, subscription_id=subscription_id
    )
    return _detail(subscription)


@admin_router.post(
    f"{_ADMIN}/{{subscription_id}}/bill-now",
    response_model=SubscriptionBillingResponse,
    dependencies=[Depends(RequirePermissions("subscriptions:write"))],
    summary="Bill one cycle immediately (admin)",
)
async def admin_bill_now(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionBillingResponse:
    """Force one billing cycle — the "retry the failed card" button.

    Idempotent per period: if this cycle was already billed, its record is
    returned instead of charging twice. Requires ``subscriptions:write``.
    """
    subscription = await subscription_service.get_subscription(
        db, subscription_id=subscription_id
    )
    billing = await subscription_service.bill_cycle(db, subscription)
    await db.refresh(billing)
    return SubscriptionBillingResponse.model_validate(billing)


@admin_router.post(
    f"{_ADMIN}/run-due",
    response_model=SubscriptionRunResponse,
    dependencies=[Depends(RequirePermissions("subscriptions:write"))],
    summary="Run all due billings now (admin)",
)
async def admin_run_due(
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRunResponse:
    """Process every due subscription once — the manual counterpart of the
    Celery beat job. Requires ``subscriptions:write``."""
    summary = await subscription_service.run_due_billings(db, now=datetime.now(UTC))
    return SubscriptionRunResponse(**summary)


__all__ = ["admin_router", "router"]
