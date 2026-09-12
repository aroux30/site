"""Time-bounded notices and seen notices domain models (Karta Phase 6/8).

Implements:
- Notice: Scheduled banners, popups, and notification bars with date intervals and target page routing (Karta notices)
- SeenNotice: User viewing history to prevent repetitive, annoying popup impressions (Karta seen_notices)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class NoticeType(str, enum.Enum):
    BANNER = "banner"
    POPUP = "popup"
    ALERT_BAR = "alert_bar"


class TargetPage(str, enum.Enum):
    ALL = "all"
    HOME = "home"
    CHECKOUT = "checkout"
    DASHBOARD = "dashboard"


class Notice(BaseModel):
    """System notice or banner scheduled with start and end timestamps (Karta notices)."""

    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_is_active", "is_active"),
        Index("ix_notices_target_page", "target_page"),
        Index("ix_notices_time_window", "start_at", "end_at"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    notice_type: Mapped[NoticeType] = mapped_column(
        Enum(NoticeType, name="notice_type_enum", native_enum=False),
        default=NoticeType.POPUP,
        nullable=False,
    )
    target_page: Mapped[TargetPage] = mapped_column(
        Enum(TargetPage, name="target_page_enum", native_enum=False),
        default=TargetPage.ALL,
        nullable=False,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Notice(id={self.id}, title={self.title}, type={self.notice_type})>"


class SeenNotice(BaseModel):
    """Tracks which notices a user has already dismissed or viewed (Karta seen_notices)."""

    __tablename__ = "seen_notices"
    __table_args__ = (
        UniqueConstraint("user_id", "notice_id", name="uq_seen_notices_user_notice"),
        Index("ix_seen_notices_user_id", "user_id"),
        Index("ix_seen_notices_notice_id", "notice_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notices.id", ondelete="CASCADE"),
        nullable=False,
    )
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<SeenNotice(user_id={self.user_id}, notice_id={self.notice_id})>"
