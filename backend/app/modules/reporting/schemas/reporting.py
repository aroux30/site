"""Pydantic v2 schemas for the reporting module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ── Report data ───────────────────────────────────────────────────────────


class ReportColumnSchema(BaseModel):
    """One output column descriptor."""

    key: str
    label: str
    kind: str = "text"


class ReportResponse(BaseModel):
    """Parameterized report payload (all money fields are integer Rials)."""

    report_type: str
    date_from: date
    date_to: date
    group_by: str
    columns: list[ReportColumnSchema]
    rows: list[dict[str, Any]]
    totals: dict[str, Any] = {}
    notes: list[str] = []


# ── Saved reports ─────────────────────────────────────────────────────────


class SavedReportCreate(BaseModel):
    """Create a saved report definition."""

    name: str = Field(..., min_length=1, max_length=200)
    report_type: str = Field(..., description="sales | stock | vendor_settlement | tax_vat")
    filters: dict[str, Any] = Field(
        ...,
        description=(
            "date_from/date_to (ISO date) الزامی؛ group_by و فیلترهای "
            "اختیاری warehouse_id/vendor_id/category_id"
        ),
    )
    schedule_cron: str | None = Field(
        None, max_length=100, description="کرون ۵ فیلدی (دقیقه ساعت روز-ماه ماه روز-هفته)"
    )
    delivery_channels: list[str] = Field(default_factory=list)
    recipients: list[str] = Field(default_factory=list)
    is_active: bool = True


class SavedReportUpdate(BaseModel):
    """Partial update of a saved report definition."""

    name: str | None = Field(None, min_length=1, max_length=200)
    filters: dict[str, Any] | None = None
    schedule_cron: str | None = Field(None, max_length=100)
    delivery_channels: list[str] | None = None
    recipients: list[str] | None = None
    is_active: bool | None = None


class SavedReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    report_type: str
    filters: dict[str, Any]
    schedule_cron: str | None = None
    delivery_channels: list[Any] = []
    recipients: list[Any] = []
    owner_id: uuid.UUID
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SavedReportListResponse(BaseModel):
    items: list[SavedReportResponse]
    total: int
    page: int
    page_size: int


# ── Runs ──────────────────────────────────────────────────────────────────


class ReportRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    saved_report_id: uuid.UUID
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    row_count: int = 0
    delivery_result: dict[str, Any] | None = None
    has_csv: bool = False
    has_html: bool = False


class ReportRunListResponse(BaseModel):
    items: list[ReportRunResponse]
    total: int
    page: int
    page_size: int
