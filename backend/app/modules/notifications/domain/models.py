"""Notification domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


# ---- Enums ----

class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    PUSH = "push"
    IN_APP = "in_app"


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
    data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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
    subject: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<NotificationTemplate(id={self.id}, name={self.name}, channel={self.channel})>"
