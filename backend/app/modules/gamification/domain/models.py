"""Gamification domain models."""

import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class GamificationRule(BaseModel):
    """Rules that award points for specific user events."""

    __tablename__ = "gamification_rules"
    __table_args__ = (
        Index("ix_gamification_rules_event_type", "event_type"),
        Index("ix_gamification_rules_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    conditions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    events: Mapped[list["GamificationEvent"]] = relationship(
        "GamificationEvent", back_populates="rule", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<GamificationRule(id={self.id}, name={self.name}, event_type={self.event_type})>"


class GamificationEvent(BaseModel):
    """Recorded gamification point awards."""

    __tablename__ = "gamification_events"
    __table_args__ = (
        Index("ix_gamification_events_user_id", "user_id"),
        Index("ix_gamification_events_rule_id", "rule_id"),
        Index("ix_gamification_events_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gamification_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    event_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationships
    rule: Mapped["GamificationRule"] = relationship(
        "GamificationRule", back_populates="events"
    )

    def __repr__(self) -> str:
        return f"<GamificationEvent(id={self.id}, user_id={self.user_id}, points={self.points_earned})>"


class Reward(BaseModel):
    """Redeemable rewards in the gamification system."""

    __tablename__ = "rewards"
    __table_args__ = (
        Index("ix_rewards_type", "type"),
        Index("ix_rewards_is_active", "is_active"),
        Index("ix_rewards_points_required", "points_required"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    points_required: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quantity_available: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<Reward(id={self.id}, name={self.name}, points_required={self.points_required})>"
