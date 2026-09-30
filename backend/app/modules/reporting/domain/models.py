"""Reporting domain models: saved report definitions and run history."""

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
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class ReportType(str, enum.Enum):
    """Parameterized report families served by this module."""

    SALES = "sales"
    STOCK = "stock"
    VENDOR_SETTLEMENT = "vendor_settlement"
    TAX_VAT = "tax_vat"


class ReportRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # Report generated but delivery was skipped (e.g. SMTP not configured).
    COMPLETED_NO_DELIVERY = "completed_no_delivery"


class SavedReport(BaseModel):
    """A named, reusable report definition with optional cron schedule."""

    __tablename__ = "saved_reports"
    __table_args__ = (
        Index("ix_saved_reports_owner_id", "owner_id"),
        Index("ix_saved_reports_report_type", "report_type"),
        Index("ix_saved_reports_next_run_at", "next_run_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type_enum", native_enum=False),
        nullable=False,
    )
    # Report parameters: date_from/date_to (ISO date strings), group_by and
    # optional warehouse_id/vendor_id/category_id filters.
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Standard five-field cron (minute hour day-of-month month day-of-week),
    # evaluated in Asia/Tehran. NULL = manual runs only.
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # e.g. ["email"]; in-app notification is always available.
    delivery_channels: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    # e.g. ["ops@example.com"] for the email channel.
    recipients: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    runs: Mapped[list["ReportRun"]] = relationship(
        "ReportRun", back_populates="saved_report", cascade="all, delete-orphan", lazy="select"
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("filters", {})
        kw.setdefault("delivery_channels", [])
        kw.setdefault("recipients", [])
        kw.setdefault("is_active", True)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<SavedReport(id={self.id}, name={self.name}, type={self.report_type})>"


class ReportRun(BaseModel):
    """One execution of a saved report (scheduled or manual)."""

    __tablename__ = "report_runs"
    __table_args__ = (
        Index("ix_report_runs_saved_report_id", "saved_report_id"),
        Index("ix_report_runs_status", "status"),
        Index("ix_report_runs_started_at", "started_at"),
    )

    saved_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("saved_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ReportRunStatus] = mapped_column(
        Enum(ReportRunStatus, name="report_run_status_enum", native_enum=False),
        default=ReportRunStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # CSV artifact persisted under the uploads/report-runs directory.
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Archived HTML rendering (fallback for deferred PDF export).
    html_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # e.g. {"email": "sent"|"failed"|"skipped_not_configured"}
    delivery_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    saved_report: Mapped["SavedReport"] = relationship("SavedReport", back_populates="runs")

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("status", ReportRunStatus.PENDING)
        kw.setdefault("row_count", 0)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return (
            f"<ReportRun(id={self.id}, "
            f"saved_report_id={self.saved_report_id}, status={self.status})>"
        )
