"""API routes for Broadcast Messaging & User Segmentation (پیام‌رسانی انبوه و بخش‌بندی کاربران)."""

from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.messaging.application import broadcast_service
from app.modules.messaging.domain.models import CampaignStatus, TargetSegment
from app.modules.messaging.schemas.campaign import (
    BroadcastCampaignCreate,
    BroadcastCampaignListResponse,
    BroadcastCampaignResponse,
    BroadcastCampaignUpdate,
    SegmentEstimateResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()

# Permission dependency instances
_require_messaging_read = Depends(RequirePermissions("messaging:read"))
_require_messaging_write = Depends(RequirePermissions("messaging:write"))


# ── Campaign Endpoints ────────────────────────────────────────────────────


@router.get(
    "/campaigns",
    response_model=BroadcastCampaignListResponse,
    summary="Admin — List broadcast campaigns",
    dependencies=[_require_messaging_read],
)
async def list_campaigns(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[CampaignStatus] = Query(
        None,
        alias="status",
        description="Filter campaigns by status (draft, scheduled, processing, sent, failed, cancelled)",
    ),
    db: AsyncSession = Depends(get_db),
) -> BroadcastCampaignListResponse:
    """List broadcast campaigns with pagination and optional status filter."""
    items, total = await broadcast_service.list_campaigns(
        db=db,
        page=page,
        page_size=page_size,
        status=status_filter,
    )
    return BroadcastCampaignListResponse(
        items=[BroadcastCampaignResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/campaigns",
    response_model=BroadcastCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin — Create a broadcast campaign",
    dependencies=[_require_messaging_write],
)
async def create_campaign(
    body: BroadcastCampaignCreate,
    db: AsyncSession = Depends(get_db),
) -> BroadcastCampaignResponse:
    """Create a new broadcast campaign (supports A/B test setup)."""
    if body.ab_test_enabled and not body.variant_b_template:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="variant_b_template is required when ab_test_enabled is True",
        )

    campaign = await broadcast_service.create_campaign(db=db, data=body)
    return BroadcastCampaignResponse.model_validate(campaign)


@router.get(
    "/campaigns/{id}",
    response_model=BroadcastCampaignResponse,
    summary="Admin — Get campaign detail",
    dependencies=[_require_messaging_read],
)
async def get_campaign(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BroadcastCampaignResponse:
    """Retrieve detailed information and metrics for a specific broadcast campaign."""
    campaign = await broadcast_service.get_campaign(db=db, campaign_id=id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID '{id}' not found",
        )
    return BroadcastCampaignResponse.model_validate(campaign)


@router.patch(
    "/campaigns/{id}",
    response_model=BroadcastCampaignResponse,
    summary="Admin — Update a draft or scheduled campaign",
    dependencies=[_require_messaging_write],
)
async def update_campaign(
    id: uuid.UUID,
    body: BroadcastCampaignUpdate,
    db: AsyncSession = Depends(get_db),
) -> BroadcastCampaignResponse:
    """Update fields of an existing draft or scheduled campaign."""
    try:
        updated = await broadcast_service.update_campaign(
            db=db,
            campaign_id=id,
            data=body,
        )
        return BroadcastCampaignResponse.model_validate(updated)
    except ValueError as exc:
        err_msg = str(exc)
        if "not found" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/campaigns/{id}/send",
    response_model=BroadcastCampaignResponse,
    summary="Admin — Trigger campaign broadcast dispatch",
    dependencies=[_require_messaging_write],
)
async def trigger_send_campaign(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BroadcastCampaignResponse:
    """Trigger immediate execution of a campaign to its target segment."""
    campaign = await broadcast_service.get_campaign(db=db, campaign_id=id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID '{id}' not found",
        )

    if campaign.status in (CampaignStatus.SENT, CampaignStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign is already in '{campaign.status.value}' state and cannot be re-sent",
        )

    try:
        updated = await broadcast_service.send_campaign(db=db, campaign_id=id)
        return BroadcastCampaignResponse.model_validate(updated)
    except Exception as exc:
        await logger.aerror(
            "send_campaign_route_error",
            campaign_id=str(id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute campaign: {exc}",
        )
    """Trigger immediate execution of a campaign to its target segment."""
    campaign = await broadcast_service.get_campaign(db=db, campaign_id=campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID '{campaign_id}' not found",
        )

    if campaign.status in (CampaignStatus.SENT, CampaignStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign is already in '{campaign.status.value}' state and cannot be re-sent",
        )

    try:
        updated = await broadcast_service.send_campaign(db=db, campaign_id=campaign_id)
        return BroadcastCampaignResponse.model_validate(updated)
    except Exception as exc:
        await logger.aerror(
            "send_campaign_route_error",
            campaign_id=str(campaign_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute campaign: {exc}",
        )


# ── Segmentation Estimate Endpoints ───────────────────────────────────────


@router.get(
    "/estimate/{segment}",
    response_model=SegmentEstimateResponse,
    summary="Admin — Get audience size estimate for a segment",
    dependencies=[_require_messaging_read],
)
async def estimate_segment_size(
    segment: str,
    db: AsyncSession = Depends(get_db),
) -> SegmentEstimateResponse:
    """Estimate the audience size for a given segment criteria.

    Valid segments:
    - all_users: total active users
    - active_buyers: users with orders in last 60 days
    - inactive_users: users with no orders in last 90 days
    - abandoned_carts: users with active carts older than 2 hours
    - wishlist_users: users with >= 1 items in wishlist
    """
    try:
        target_segment = TargetSegment(segment)
    except ValueError:
        valid_options = ", ".join(s.value for s in TargetSegment)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid segment '{segment}'. Valid options are: {valid_options}",
        )

    count = await broadcast_service.estimate_segment_size(db=db, segment=target_segment)

    descriptions = {
        TargetSegment.ALL_USERS: "Total active registered users",
        TargetSegment.ACTIVE_BUYERS: "Users with at least one order placed in the last 60 days",
        TargetSegment.INACTIVE_USERS: "Users who have not placed any orders in the last 90 days",
        TargetSegment.ABANDONED_CARTS: "Users with active shopping carts untouched for over 2 hours",
        TargetSegment.WISHLIST_USERS: "Users with at least one product saved in their wishlist",
    }

    return SegmentEstimateResponse(
        target_segment=target_segment,
        estimated_count=count,
        description=descriptions.get(target_segment),
    )
