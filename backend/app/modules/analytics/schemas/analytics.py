"""Pydantic v2 schemas for the analytics module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Event Tracking ────────────────────────────────────────────────────────


class TrackEventRequest(BaseModel):
    """Payload to track an analytics event."""

    event_type: str = Field(..., max_length=100)
    event_data: Optional[dict[str, Any]] = None
    session_id: Optional[str] = Field(None, max_length=255)


class TrackEventResponse(BaseModel):
    """Response after tracking an event."""

    event_id: uuid.UUID
    event_type: str
    created_at: datetime


# ── Sales Analytics ───────────────────────────────────────────────────────


class SalesAnalyticsResponse(BaseModel):
    """Aggregated sales analytics."""

    total_sales: int = 0
    order_count: int = 0
    average_order_value: float = 0.0
    period_start: date
    period_end: date
    daily_breakdown: list["DailySalesEntry"] = []


class DailySalesEntry(BaseModel):
    """Daily sales data point."""

    date: date
    total_sales: int = 0
    order_count: int = 0


# ── Order Analytics ───────────────────────────────────────────────────────


class OrderAnalyticsResponse(BaseModel):
    """Order analytics with status breakdown."""

    total_orders: int = 0
    status_breakdown: dict[str, int] = {}
    period_start: date
    period_end: date


# ── Product Analytics ─────────────────────────────────────────────────────


class ProductAnalyticsEntry(BaseModel):
    """Analytics for a single product."""

    product_name: str
    variant_id: uuid.UUID
    total_sold: int = 0
    total_revenue: int = 0
    view_count: int = 0
    conversion_rate: float = 0.0


class ProductAnalyticsResponse(BaseModel):
    """Product analytics response."""

    best_sellers: list[ProductAnalyticsEntry] = []
    period_start: date
    period_end: date


# ── Customer Analytics ────────────────────────────────────────────────────


class TopCustomerEntry(BaseModel):
    """Analytics for a single top customer."""

    user_id: uuid.UUID
    order_count: int = 0
    total_spent: int = 0


class CustomerAnalyticsResponse(BaseModel):
    """Customer analytics response."""

    total_customers: int = 0
    new_customers: int = 0
    returning_customers: int = 0
    top_customers: list[TopCustomerEntry] = []
    period_start: date
    period_end: date


# ── Daily Metrics ─────────────────────────────────────────────────────────


class DailyMetricResponse(BaseModel):
    """Single daily metric record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: date
    metric_name: str
    metric_value: float
    dimensions: Optional[dict[str, Any]] = None


# Rebuild forward refs
SalesAnalyticsResponse.model_rebuild()
