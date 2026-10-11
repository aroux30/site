"""Pydantic v2 schemas for the notifications module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

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
    data: dict[str, Any] | None = None
    is_read: bool
    read_at: datetime | None = None
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
    data: dict[str, Any] | None = None
    channels: list[NotificationChannel] = [NotificationChannel.IN_APP]


class NotificationSendRequest(BaseModel):
    """Request to send a notification through specified channels."""

    channels: list[NotificationChannel] = [NotificationChannel.IN_APP]


class MarkReadResponse(BaseModel):
    """Response after marking notifications as read."""

    marked_count: int


# ── Per-user Preferences ──────────────────────────────────────────────────


class NotificationPreferencesResponse(BaseModel):
    """Resolved per-user preference matrix (missing keys default to True)."""

    channels: dict[str, bool]
    categories: dict[str, bool]


class NotificationPreferencesUpdate(BaseModel):
    """Partial preference update; only provided matrices are merged."""

    channels: dict[str, bool] | None = None
    categories: dict[str, bool] | None = None
