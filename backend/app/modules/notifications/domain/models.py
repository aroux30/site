"""Notification domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
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
    """Delivery channels.

    ``EMAIL`` was removed on 2026-10-07 with the rest of the email feature
    (the owner's store logs in with a phone number and sends SMS). The
    vocabulary keeps the NAME-storage contract: values stored in
    ``notification_preferences.channels`` are these member names.
    """

    SMS = "sms"
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


class NotificationPreference(BaseModel):
    """Per-user channel/category opt-in matrix.

    One row per user (created lazily on first read). ``channels`` maps
    channel value → bool and ``categories`` maps category value → bool;
    a missing key means the default (ON) so new channels/categories added
    later are opt-out, matching the platform's "default: all on" contract.
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

    def __repr__(self) -> str:
        return f"<NotificationPreference(id={self.id}, user_id={self.user_id})>"
