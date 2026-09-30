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


# ── Templates ─────────────────────────────────────────────────────────────


class NotificationTemplateResponse(BaseModel):
    """Notification template response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    channel: NotificationChannel
    subject: str | None = None
    body_template: str
    variables: list[Any] | None = None
    created_at: datetime


class MarkReadResponse(BaseModel):
    """Response after marking notifications as read."""

    marked_count: int


# ── Per-user Preferences ──────────────────────────────────────────────────


class NotificationPreferencesResponse(BaseModel):
    """Resolved per-user preference matrix (missing keys default to True)."""

    channels: dict[str, bool]
    categories: dict[str, bool]
    telegram_linked: bool = False
    telegram_chat_id_masked: str | None = None


class NotificationPreferencesUpdate(BaseModel):
    """Partial preference update; only provided matrices are merged."""

    channels: dict[str, bool] | None = None
    categories: dict[str, bool] | None = None


# ── Telegram Account Linking ──────────────────────────────────────────────


class TelegramLinkCodeResponse(BaseModel):
    """Freshly generated link code + bot deep link for the account page."""

    code: str
    expires_at: datetime
    bot_deep_link: str | None = None  # https://t.me/<bot_username> when known


class TelegramLinkStatusResponse(BaseModel):
    """Whether the account has a linked Telegram chat."""

    linked: bool
    telegram_chat_id_masked: str | None = None


class TelegramAdminLinkRequest(BaseModel):
    """Admin manual link: bind a user's outstanding code to a chat_id.

    Interim for the deferred bot webhook (see telegram_service docstring):
    an operator reads the code the user sent to the bot and the sender's
    chat_id from the bot's inbox, then binds the two here.
    """

    code: str = Field(..., min_length=4, max_length=16)
    chat_id: str = Field(..., min_length=1, max_length=64)


class TelegramAdminLinkResponse(BaseModel):
    """Result of a manual/webhook link attempt."""

    linked: bool
    user_id: uuid.UUID | None = None


# ── Web Push Subscriptions ────────────────────────────────────────────────


class PushSubscriptionKeys(BaseModel):
    """Browser PushSubscription keys (p256dh + auth)."""

    p256dh: str = Field(..., min_length=1, max_length=500)
    auth: str = Field(..., min_length=1, max_length=500)


class PushSubscribeRequest(BaseModel):
    """Browser PushSubscription.toJSON() payload."""

    endpoint: str = Field(..., min_length=10, max_length=2000)
    keys: PushSubscriptionKeys


class PushUnsubscribeRequest(BaseModel):
    """Unsubscribe a single browser endpoint."""

    endpoint: str = Field(..., min_length=10, max_length=2000)


class PushPublicKeyResponse(BaseModel):
    """The VAPID public key browsers need to subscribe; empty when unconfigured."""

    public_key: str
    configured: bool


class PushSubscriptionResponse(BaseModel):
    """Outcome of a subscribe/unsubscribe call."""

    success: bool
