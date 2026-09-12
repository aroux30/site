"""Pydantic v2 schemas for Time-bounded Notices and SMS Hub (Karta Phase 6/8)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.notifications.domain.notice_models import NoticeType, TargetPage

# ── Notice Schemas ────────────────────────────────────────────────────────


class NoticeCreateRequest(BaseModel):
    """Admin payload to schedule a new system notice or banner."""

    title: str = Field(..., min_length=1, max_length=200, description="Notice headline")
    content_html: str = Field(..., min_length=1, description="HTML or rich text body")
    notice_type: NoticeType = NoticeType.POPUP
    target_page: TargetPage = TargetPage.ALL
    start_at: datetime | None = None
    end_at: datetime | None = None


class NoticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content_html: str
    notice_type: NoticeType
    target_page: TargetPage
    start_at: datetime
    end_at: datetime
    is_active: bool
    created_at: datetime


class MarkNoticeSeenResponse(BaseModel):
    user_id: uuid.UUID
    notice_id: uuid.UUID
    seen_at: datetime
    message: str = "اطلاعیه به عنوان دیده‌شده علامت‌گذاری شد"


# ── SMS Hub Schemas ───────────────────────────────────────────────────────


class SmsDispatchRequest(BaseModel):
    """Payload to dispatch an SMS message with automatic provider failover."""

    mobile: str = Field(..., min_length=10, max_length=15, description="Customer 11-digit mobile number")
    text: str = Field(..., min_length=1, max_length=1000, description="SMS text content")
    pattern: str | None = None


class SmsDispatchResponse(BaseModel):
    success: bool
    provider: str | None = None
    to: str | None = None
    error: str | None = None
