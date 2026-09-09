"""Analytics API routes."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user
from app.modules.analytics.application.analytics_service import AnalyticsService
from app.modules.analytics.schemas.analytics import (
    CustomerAnalyticsResponse,
    OrderAnalyticsResponse,
    ProductAnalyticsResponse,
    SalesAnalyticsResponse,
    TrackEventRequest,
    TrackEventResponse,
)
from app.modules.users.domain.models import User

router = APIRouter()


@router.post(
    "/events",
    response_model=TrackEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track analytics event",
)
async def track_event(
    payload: TrackEventRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> TrackEventResponse:
    """Track a client-side analytics event."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user_id = current_user.id if current_user else None

    event = await AnalyticsService.track_event(
        db,
        event_type=payload.event_type,
        event_data=payload.event_data,
        user_id=user_id,
        session_id=payload.session_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return TrackEventResponse(
        event_id=event.id,
        event_type=event.event_type,
        created_at=event.created_at,
    )


@router.get(
    "/sales",
    response_model=SalesAnalyticsResponse,
    summary="Sales analytics report",
    dependencies=[Depends(RequirePermissions("analytics:read"))],
)
async def get_sales_analytics(
    start_date: Optional[date] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
) -> SalesAnalyticsResponse:
    """Get aggregated sales metrics and daily breakdown."""
    today = date.today()
    period_start = start_date or (today - timedelta(days=30))
    period_end = end_date or today

    data = await AnalyticsService.get_sales_analytics(db, period_start, period_end)
    return SalesAnalyticsResponse(**data)


@router.get(
    "/orders",
    response_model=OrderAnalyticsResponse,
    summary="Order analytics report",
    dependencies=[Depends(RequirePermissions("analytics:read"))],
)
async def get_order_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> OrderAnalyticsResponse:
    """Get order volume and status distribution."""
    today = date.today()
    period_start = start_date or (today - timedelta(days=30))
    period_end = end_date or today

    data = await AnalyticsService.get_order_analytics(db, period_start, period_end)
    return OrderAnalyticsResponse(**data)


@router.get(
    "/products",
    response_model=ProductAnalyticsResponse,
    summary="Product performance analytics",
    dependencies=[Depends(RequirePermissions("analytics:read"))],
)
async def get_product_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProductAnalyticsResponse:
    """Get best-selling products with revenue and conversion rates."""
    today = date.today()
    period_start = start_date or (today - timedelta(days=30))
    period_end = end_date or today

    data = await AnalyticsService.get_product_analytics(db, period_start, period_end, top_n=limit)
    return ProductAnalyticsResponse(**data)


@router.get(
    "/customers",
    response_model=CustomerAnalyticsResponse,
    summary="Customer analytics report",
    dependencies=[Depends(RequirePermissions("analytics:read"))],
)
async def get_customer_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CustomerAnalyticsResponse:
    """Get new vs returning customers and top spenders."""
    today = date.today()
    period_start = start_date or (today - timedelta(days=30))
    period_end = end_date or today

    data = await AnalyticsService.get_customer_analytics(db, period_start, period_end, top_n=limit)
    return CustomerAnalyticsResponse(**data)
