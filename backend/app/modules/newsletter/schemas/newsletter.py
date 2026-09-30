"""Newsletter schemas (public + admin)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.newsletter.domain.models import (
    CampaignStatus,
    NewsletterStatus,
    RecipientStatus,
)

# ── Public ────────────────────────────────────────────────────────────────


class SubscribeRequest(BaseModel):
    """Public newsletter signup. Deliberately leaks nothing: any well-formed
    request gets the same generic response, whether or not the address was
    already on the list."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    source: str | None = Field(None, max_length=50)


class SubscribeResponse(BaseModel):
    message: str


class ConfirmRequest(BaseModel):
    """The emailed link carries both values; the (token, email) pair must
    recompute the server-side MAC exactly."""

    token: str = Field(min_length=16, max_length=64)
    email: EmailStr


class UnsubscribeRequest(BaseModel):
    token: str = Field(min_length=16, max_length=64)
    email: EmailStr


class SubscriptionStatusResponse(BaseModel):
    status: NewsletterStatus


# ── Admin ─────────────────────────────────────────────────────────────────


class SubscriberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    status: NewsletterStatus
    source: str
    confirmed_at: datetime | None = None
    unsubscribed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SubscriberListResponse(BaseModel):
    items: list[SubscriberResponse]
    total: int
    page: int
    page_size: int
    status_counts: dict[Literal["pending", "subscribed", "unsubscribed"], int]


# ── Admin — campaigns ─────────────────────────────────────────────────────


class CampaignCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=255)
    preheader: str | None = Field(None, max_length=255)
    body_html: str = Field(min_length=1)
    body_text: str | None = None


class CampaignUpdate(BaseModel):
    """Partial update of a draft campaign; ignored fields stay untouched."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=200)
    subject: str | None = Field(None, min_length=1, max_length=255)
    preheader: str | None = Field(None, max_length=255)
    body_html: str | None = Field(None, min_length=1)
    body_text: str | None = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    subject: str
    preheader: str | None = None
    body_html: str
    body_text: str | None = None
    status: CampaignStatus
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    total_recipients: int
    total_sent: int
    total_failed: int
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    page: int
    page_size: int


class CampaignScheduleRequest(BaseModel):
    """When the campaign should go out; the beat sweep fires within ~1 min."""

    scheduled_at: datetime


class CampaignSendResponse(BaseModel):
    id: uuid.UUID
    status: CampaignStatus
    # "queued" = handed to the Celery worker; "inline" = broker unavailable,
    # the request sent the campaign synchronously (small lists / dev).
    mode: Literal["queued", "inline"]
    total_recipients: int
    total_sent: int = 0
    total_failed: int = 0


class CampaignTestSendRequest(BaseModel):
    """Send the rendered campaign to one arbitrary address (no recipient rows)."""

    email: EmailStr


class CampaignTestSendResponse(BaseModel):
    email: str
    sent: bool


class CampaignPreviewResponse(BaseModel):
    """Fully rendered email (unsubscribe footer included) for admin review."""

    subject: str
    html: str
    text: str


class CampaignRecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: uuid.UUID
    # The subscriber primary key is the address; exposed as `email` via the
    # model's `email` property.
    email: str
    status: RecipientStatus
    error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


class CampaignRecipientListResponse(BaseModel):
    items: list[CampaignRecipientResponse]
    total: int
    page: int
    page_size: int
