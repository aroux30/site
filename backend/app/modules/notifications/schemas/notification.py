"""Pydantic v2 schemas for the notifications module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.notifications.domain.models import NotificationChannel


# ── Notification ──────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    """Single notification record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str
    data: Optional[dict[str, Any]] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notification list."""

    items: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationCreate(BaseModel):
    """Payload to create a notification (internal/admin use)."""

    user_id: uuid.UUID
    type: str = Field(..., max_length=100)
    title: str = Field(..., max_length=300)
    body: str
    data: Optional[dict[str, Any]] = None
    channels: list[NotificationChannel] = [NotificationChannel.IN_APP]


class NotificationSendRequest(BaseModel):
    """Request to send a notification through specified channels."""

    channels: list[NotificationChannel] = [NotificationChannel.IN_APP]


# ── Templates ─────────────────────────────────────────────────────────────


class NotificationTemplateResponse(BaseModel):
    """Notification template response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    channel: NotificationChannel
    subject: Optional[str] = None
    body_template: str
    variables: Optional[list[Any]] = None
    created_at: datetime


class MarkReadResponse(BaseModel):
    """Response after marking notifications as read."""

    marked_count: int
