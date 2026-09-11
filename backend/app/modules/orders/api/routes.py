"""Order API routes — customer and admin endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.core.security.jwt import verify_token
from app.core.security.rate_limiter import limiter
from app.modules.orders.application import invoice_service, order_service
from app.modules.orders.schemas.order import (
    AdminOrderUpdateRequest,
    OrderCancelRequest,
    OrderFilterParams,
    OrderListResponse,
    OrderResponse,
    OrderReturnResponse,
    OrderTimelineResponse,
    PaginationParams,
    ReturnCreateRequest,
)

router = APIRouter()


_optional_bearer = HTTPBearer(auto_error=False)


async def _resolve_invoice_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    token: str | None = Query(None, description="Optional access token query parameter"),
) -> dict[str, Any]:
    raw_token: str | None = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view invoice",
        )
    return verify_token(raw_token, expected_type="access")


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
    status: str | None = Query(None, description="Filter by order status"),
    from_date: datetime | None = Query(None, description="Orders created after this datetime"),
    to_date: datetime | None = Query(None, description="Orders created before this datetime"),
    min_total: int | None = Query(None, description="Minimum order total (Rials)"),
    max_total: int | None = Query(None, description="Maximum order total (Rials)"),
    search: str | None = Query(None, description="Search in order number"),
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


@router.get(
    "/{order_id}/invoice",
    response_class=HTMLResponse,
    summary="Get official Iranian tax invoice (فاکتور رسمی الکترونیکی)",
)
async def get_order_invoice(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict[str, Any] = Depends(_resolve_invoice_claims),
) -> HTMLResponse:
    """Generate and return official Iranian tax invoice in printable HTML format.

    Requires order ownership or administrative permission (orders:read, orders:write, admin).
    """
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing or invalid 'sub' claim",
        ) from exc

    permissions = set(claims.get("permissions", []))
    roles = set(claims.get("roles", []))

    html = await invoice_service.generate_invoice_html_for_order(
        db=db,
        order_id_or_number=order_id,
        requesting_user_id=user_id,
        user_permissions=permissions,
        user_roles=roles,
    )
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel an order",
)
@limiter.limit("10/minute")
async def cancel_order(
    request: Request,
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


@router.post(
    "/{order_id}/returns",
    response_model=OrderReturnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request order return (RMA) within statutory 7-day window",
)
@limiter.limit("10/minute")
async def request_order_return(
    request: Request,
    order_id: uuid.UUID,
    body: ReturnCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderReturnResponse:
    return await order_service.request_order_return(db, user_id, order_id, body)


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
    status: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    min_total: int | None = Query(None),
    max_total: int | None = Query(None),
    search: str | None = Query(None),
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
