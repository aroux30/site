"""Notification domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

# ---- Enums ----


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationCategory(str, enum.Enum):
    """Coarse notification topics a user can opt in/out of per channel."""

    ORDER = "order"
    PAYMENT = "payment"
    SHIPPING = "shipping"
    PROMOTION = "promotion"
    SYSTEM = "system"


# ---- Models ----


class Notification(BaseModel):
    """User-facing notifications across channels."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_type", "type"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"


class NotificationTemplate(BaseModel):
    """Reusable notification templates with variable substitution."""

    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_name", "name"),
        Index("ix_notification_templates_channel", "channel"),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<NotificationTemplate(id={self.id}, name={self.name}, channel={self.channel})>"


class EmailDeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    #: Nothing was sent because the channel is not configured (no SMTP host
    #: or from_address). Distinct from SENT, which means it really went out,
    #: and from FAILED, which means a real dispatch was attempted and failed.
    SKIPPED = "skipped"


class EmailDeliveryLog(BaseModel):
    """Per-email delivery record: one row per attempted outbound email.

    Written by the email service before dispatch (QUEUED) and updated to
    SENT/FAILED with the provider response or the sanitized error so ops
    can audit exactly what left the platform and why something did not.
    """

    __tablename__ = "email_delivery_logs"
    __table_args__ = (
        Index("ix_email_delivery_logs_recipient", "recipient"),
        Index("ix_email_delivery_logs_status", "status"),
        Index("ix_email_delivery_logs_notification_id", "notification_id"),
        Index("ix_email_delivery_logs_created_at", "created_at"),
    )

    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    template: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[EmailDeliveryStatus] = mapped_column(
        Enum(
            EmailDeliveryStatus,
            name="email_delivery_status_enum",
            native_enum=False,
            # Without an explicit length SQLAlchemy sizes the column from the
            # longest member NAME ("FAILED" -> 6), while "skipped" is 7 — so
            # every delivery log insert failed on truncation. 20 covers the
            # current vocabulary and any member added later.
            length=20,
        ),
        default=EmailDeliveryStatus.QUEUED,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), default="smtp", nullable=False)
    provider_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EmailDeliveryLog(id={self.id}, recipient={self.recipient}, "
            f"status={self.status})>"
        )


class TelegramDeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class TelegramDeliveryLog(BaseModel):
    """Per-message delivery record: one row per attempted Telegram send.

    Mirror of :class:`EmailDeliveryLog` for the Telegram Bot API channel so
    ops can audit delivery without reading worker logs.
    """

    __tablename__ = "telegram_delivery_logs"
    __table_args__ = (
        Index("ix_telegram_delivery_logs_recipient", "recipient"),
        Index("ix_telegram_delivery_logs_status", "status"),
        Index("ix_telegram_delivery_logs_notification_id", "notification_id"),
        Index("ix_telegram_delivery_logs_created_at", "created_at"),
    )

    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    # The Telegram chat_id the message targeted (string; can be negative for groups).
    recipient: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[TelegramDeliveryStatus] = mapped_column(
        Enum(
            TelegramDeliveryStatus,
            name="telegram_delivery_status_enum",
            native_enum=False,
        ),
        default=TelegramDeliveryStatus.QUEUED,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), default="telegram_bot", nullable=False)
    provider_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TelegramDeliveryLog(id={self.id}, recipient={self.recipient}, "
            f"status={self.status})>"
        )


class NotificationPreference(BaseModel):
    """Per-user channel/category opt-in matrix plus Telegram link state.

    One row per user (created lazily on first read). ``channels`` maps
    channel value → bool and ``categories`` maps category value → bool;
    a missing key means the default (ON) so new channels/categories added
    later are opt-out, matching the platform's "default: all on" contract.

    ``telegram_chat_id`` is populated by the verification-code link flow
    (see telegram_service module docstring); ``telegram_link_code`` holds
    the single active code until it expires or is consumed.
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("ix_notification_preferences_user_id", "user_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    channels: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    categories: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    telegram_link_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(id={self.id}, user_id={self.user_id})>"


class PushSubscription(BaseModel):
    """One browser Web Push subscription (endpoint + VAPID keys) per row.

    A user may have several subscriptions (phone + desktop); the endpoint
    URL is the unique identity the push service assigns, so dedupe is by
    endpoint. ``keys`` stores {"p256dh": ..., "auth": ...} exactly as the
    browser's PushSubscription.toJSON() yields it.
    """

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        Index("ix_push_subscriptions_user_id", "user_id"),
        Index("ix_push_subscriptions_endpoint", "endpoint", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    keys: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<PushSubscription(id={self.id}, user_id={self.user_id})>"
