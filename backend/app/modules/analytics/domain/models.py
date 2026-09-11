"""Analytics and metrics domain models."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class AnalyticsEvent(BaseModel):
    """Raw analytics event stream for user behaviour tracking."""

    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_events_user_id", "user_id"),
        Index("ix_analytics_events_session_id", "session_id"),
        Index("ix_analytics_events_event_type", "event_type"),
        Index("ix_analytics_events_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<AnalyticsEvent(id={self.id}, event_type={self.event_type})>"


class DailyMetric(BaseModel):
    """Pre-aggregated daily metric snapshots for dashboards."""

    __tablename__ = "daily_metrics"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "metric_name",
            "dimensions",
            name="uq_daily_metrics_date_name_dims",
        ),
        Index("ix_daily_metrics_date", "date"),
        Index("ix_daily_metrics_metric_name", "metric_name"),
        Index("ix_daily_metrics_date_metric", "date", "metric_name"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<DailyMetric(id={self.id}, date={self.date}, metric={self.metric_name})>"
