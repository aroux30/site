"""Broadcast Messaging domain models (پیام‌رسانی انبوه و بخش‌بندی کاربران)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.users.domain.models import User


# ── Enums ─────────────────────────────────────────────────────────────────


class CampaignChannel(enum.StrEnum):
    """Supported broadcast communication channels."""

    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"


class TargetSegment(enum.StrEnum):
    """User audience segmentation criteria."""

    ALL_USERS = "all_users"
    ACTIVE_BUYERS = "active_buyers"
    INACTIVE_USERS = "inactive_users"
    ABANDONED_CARTS = "abandoned_carts"
    WISHLIST_USERS = "wishlist_users"


class CampaignStatus(enum.StrEnum):
    """Lifecycle states of a broadcast campaign."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecipientStatus(enum.StrEnum):
    """Delivery status for an individual recipient."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# ── Models ────────────────────────────────────────────────────────────────


class BroadcastCampaign(BaseModel):
    """Mass messaging campaign definition and execution tracking."""

    __tablename__ = "broadcast_campaigns"
    __table_args__ = (
        Index("ix_broadcast_campaigns_status", "status"),
        Index("ix_broadcast_campaigns_channel", "channel"),
        Index("ix_broadcast_campaigns_target_segment", "target_segment"),
        Index("ix_broadcast_campaigns_scheduled_at", "scheduled_at"),
        Index("ix_broadcast_campaigns_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[CampaignChannel] = mapped_column(
        Enum(CampaignChannel, name="campaign_channel_enum", native_enum=False),
        nullable=False,
    )
    target_segment: Mapped[TargetSegment] = mapped_column(
        Enum(TargetSegment, name="target_segment_enum", native_enum=False),
        nullable=False,
    )
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status_enum", native_enum=False),
        default=CampaignStatus.DRAFT,
        nullable=False,
    )
    total_recipients: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    success_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    ab_test_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    variant_b_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    recipients: Mapped[list[BroadcastRecipient]] = relationship(
        "BroadcastRecipient",
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("total_recipients", 0)
        kwargs.setdefault("success_count", 0)
        kwargs.setdefault("fail_count", 0)
        kwargs.setdefault("ab_test_enabled", False)
        kwargs.setdefault("status", CampaignStatus.DRAFT)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<BroadcastCampaign(id={self.id}, title='{self.title}', status='{self.status}')>"


class BroadcastRecipient(BaseModel):
    """Delivery log and A/B tracking for each recipient in a campaign."""

    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        Index("ix_broadcast_recipients_campaign_id", "campaign_id"),
        Index("ix_broadcast_recipients_user_id", "user_id"),
        Index("ix_broadcast_recipients_status", "status"),
        UniqueConstraint("campaign_id", "user_id", name="uq_broadcast_recipients_campaign_user"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("broadcast_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus, name="recipient_status_enum", native_enum=False),
        default=RecipientStatus.PENDING,
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_used: Mapped[str | None] = mapped_column(
        String(10),
        default="A",
        nullable=True,
    )

    # Relationships
    campaign: Mapped[BroadcastCampaign] = relationship(
        "BroadcastCampaign",
        back_populates="recipients",
        lazy="select",
    )
    user: Mapped[User] = relationship(
        "User",
        lazy="select",
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("status", RecipientStatus.PENDING)
        kwargs.setdefault("variant_used", "A")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<BroadcastRecipient(id={self.id}, campaign_id={self.campaign_id}, "
            f"user_id={self.user_id}, status='{self.status}', variant='{self.variant_used}')>"
        )
