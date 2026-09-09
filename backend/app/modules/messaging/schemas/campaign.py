"""Pydantic v2 schemas for Broadcast Messaging & User Segmentation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.messaging.domain.models import (
    CampaignChannel,
    CampaignStatus,
    RecipientStatus,
    TargetSegment,
)


# ── Campaign Schemas ──────────────────────────────────────────────────────


class BroadcastCampaignCreate(BaseModel):
    """Schema for creating a new broadcast campaign."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Campaign title / identifier",
        examples=["Flash Sale Weekend Announcement"],
    )
    channel: CampaignChannel = Field(
        ...,
        description="Delivery channel: sms, email, push, in_app",
    )
    target_segment: TargetSegment = Field(
        ...,
        description="Target user segment: all_users, active_buyers, inactive_users, abandoned_carts, wishlist_users",
    )
    message_template: str = Field(
        ...,
        min_length=1,
        description="Main message text or template",
        examples=["Special 20% discount code: WEEKEND20"],
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Optional scheduled dispatch time (UTC)",
    )
    status: Optional[CampaignStatus] = Field(
        CampaignStatus.DRAFT,
        description="Initial campaign status (defaults to draft)",
    )
    ab_test_enabled: bool = Field(
        False,
        description="Whether A/B testing is enabled with an alternative variant",
    )
    variant_b_template: Optional[str] = Field(
        None,
        description="Alternative message template for variant B (required if ab_test_enabled)",
    )


class BroadcastCampaignUpdate(BaseModel):
    """Schema for updating an existing broadcast campaign."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    channel: Optional[CampaignChannel] = None
    target_segment: Optional[TargetSegment] = None
    message_template: Optional[str] = Field(None, min_length=1)
    scheduled_at: Optional[datetime] = None
    status: Optional[CampaignStatus] = None
    ab_test_enabled: Optional[bool] = None
    variant_b_template: Optional[str] = None


class BroadcastCampaignResponse(BaseModel):
    """Full detail view of a broadcast campaign."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    channel: CampaignChannel
    target_segment: TargetSegment
    message_template: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    status: CampaignStatus
    total_recipients: int = 0
    success_count: int = 0
    fail_count: int = 0
    ab_test_enabled: bool = False
    variant_b_template: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BroadcastCampaignListResponse(BaseModel):
    """Paginated list response for broadcast campaigns."""

    items: list[BroadcastCampaignResponse]
    total: int
    page: int
    page_size: int


class SegmentEstimateResponse(BaseModel):
    """Response containing estimated audience size for a target segment."""

    target_segment: TargetSegment
    estimated_count: int
    description: Optional[str] = None


class BroadcastRecipientResponse(BaseModel):
    """Schema for campaign recipient logs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    user_id: uuid.UUID
    status: RecipientStatus
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    variant_used: Optional[str] = "A"
    created_at: datetime
