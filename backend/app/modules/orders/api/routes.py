"""Order API routes — customer and admin endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.modules.orders.application import order_service
from app.modules.orders.schemas.order import (
    AdminOrderUpdateRequest,
    OrderCancelRequest,
    OrderFilterParams,
    OrderListResponse,
    OrderResponse,
    OrderTimelineResponse,
    PaginationParams,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════
# Customer endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List current user's orders",
)
async def list_orders(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    status: Optional[str] = Query(None, description="Filter by order status"),
    from_date: Optional[datetime] = Query(None, description="Orders created after this datetime"),
    to_date: Optional[datetime] = Query(None, description="Orders created before this datetime"),
    min_total: Optional[int] = Query(None, description="Minimum order total (Rials)"),
    max_total: Optional[int] = Query(None, description="Maximum order total (Rials)"),
    search: Optional[str] = Query(None, description="Search in order number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OrderListResponse:
    filters = OrderFilterParams(
        status=status,
        from_date=from_date,
        to_date=to_date,
        min_total=min_total,
        max_total=max_total,
        search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await order_service.get_orders(db, user_id, filters, pagination)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderResponse:
    return await order_service.get_order(db, user_id, order_id)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel an order",
)
async def cancel_order(
    order_id: uuid.UUID,
    body: OrderCancelRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderResponse:
    return await order_service.cancel_order(db, user_id, order_id, body.reason)


@router.get(
    "/{order_id}/timeline",
    response_model=OrderTimelineResponse,
    summary="Get order status timeline",
)
async def get_order_timeline(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderTimelineResponse:
    return await order_service.get_order_timeline(db, order_id, user_id=user_id)


# ══════════════════════════════════════════════════════════════════════════
# Admin endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/admin/orders",
    response_model=OrderListResponse,
    summary="Admin — list all orders",
    dependencies=[Depends(RequirePermissions("orders:read"))],
)
async def admin_list_orders(
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    min_total: Optional[int] = Query(None),
    max_total: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OrderListResponse:
    filters = OrderFilterParams(
        status=status,
        from_date=from_date,
        to_date=to_date,
        min_total=min_total,
        max_total=max_total,
        search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await order_service.admin_get_orders(db, filters, pagination)


@router.patch(
    "/admin/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="Admin — update order status",
    dependencies=[Depends(RequirePermissions("orders:write"))],
)
async def admin_update_order_status(
    order_id: uuid.UUID,
    body: AdminOrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderResponse:
    return await order_service.admin_update_status(
        db,
        order_id=order_id,
        new_status=body.status,
        actor_id=actor_id,
        reason=body.notes,
    )
