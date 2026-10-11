"""Order API routes — customer and admin endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.core.security.rate_limiter import limiter
from app.modules.orders.application import order_service
from app.modules.orders.schemas.order import (
    AdminOrderDetailResponse,
    AdminOrderStatsResponse,
    AdminOrderUpdateRequest,
    OrderBulkStatusRequest,
    OrderBulkStatusResult,
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


# ── Price snapshot (customer) ─────────────────────────────────────────────


@router.get(
    "/{order_id}/price-snapshot",
    summary="Get the frozen pricing breakdown for an order",
)
async def get_order_price_snapshot(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Return the immutable price snapshot created at checkout.

    Only the order owner can access this. The response includes a
    ``hash_valid`` flag that is ``True`` when the stored hash matches
    a freshly recomputed one (tamper detection).
    """
    from app.modules.checkout.application import snapshot_service
    from app.modules.checkout.schemas.price_snapshot import PriceSnapshotResponse

    # Ownership check — raises NotFoundError if not the owner
    await order_service.get_order(db, user_id, order_id)

    snapshot = await snapshot_service.get_snapshot(db, order_id)
    hash_valid = await snapshot_service.verify_snapshot(db, order_id)

    return PriceSnapshotResponse(
        id=snapshot.id,
        order_id=snapshot.order_id,
        currency=snapshot.currency,
        lines=snapshot.lines,
        subtotal_rial=snapshot.subtotal_rial,
        total_discount_rial=snapshot.total_discount_rial,
        total_tax_rial=snapshot.total_tax_rial,
        shipping_rial=snapshot.shipping_rial,
        grand_total_rial=snapshot.grand_total_rial,
        snapshot_hash=snapshot.snapshot_hash,
        hash_valid=hash_valid,
        created_at=snapshot.created_at,
    ).model_dump()


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
    statuses: str | None = Query(
        None,
        description="Comma-separated status filter (one of the board's grouped lanes)",
    ),
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
        statuses=[s for s in statuses.split(",") if s] if statuses else None,
        from_date=from_date,
        to_date=to_date,
        min_total=min_total,
        max_total=max_total,
        search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await order_service.admin_get_orders(db, filters, pagination)


@router.get(
    "/admin/orders/stats",
    response_model=AdminOrderStatsResponse,
    summary="Admin — per-status order counts and sums",
    dependencies=[Depends(RequirePermissions("orders:read"))],
)
async def admin_order_stats(
    db: AsyncSession = Depends(get_db),
) -> AdminOrderStatsResponse:
    """Whole-table per-status aggregates for the admin board headers.

    Registered BEFORE ``/admin/orders/{order_id}`` on purpose: with the
    detail route first, ``stats`` would be captured as an order id and the
    request would 422 instead of reaching this handler.
    """
    return await order_service.admin_get_order_stats(db)


@router.get(
    "/admin/orders/{order_id}",
    response_model=AdminOrderDetailResponse,
    summary="Admin — full order detail (unmasked address, payments)",
    dependencies=[Depends(RequirePermissions("orders:read"))],
)
async def admin_get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AdminOrderDetailResponse:
    return await order_service.admin_get_order_detail(db, order_id)


@router.post(
    "/admin/orders/bulk/status",
    response_model=OrderBulkStatusResult,
    summary="Admin — update the status of many orders at once",
    dependencies=[Depends(RequirePermissions("orders:write"))],
)
async def admin_bulk_update_order_status(
    body: OrderBulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderBulkStatusResult:
    """Move up to 100 orders to one status, reporting each order's outcome.

    Registered BEFORE ``/admin/orders/{order_id}/status`` on purpose: the two
    paths have the same segment count, so a later registration would let
    ``{order_id}`` claim the literal ``bulk`` and answer 422 instead of
    reaching this handler.

    Every order is transitioned through the single-order service, so the
    state machine, restock and wallet refund apply identically here. Orders
    whose transition is illegal (or whose cancellation is blocked, e.g. a
    delivered digital good) are rolled back individually and reported with
    their reason; the rest still commit. ``succeeded``/``failed`` in the
    response are the whole truth of the run — read them as a partial result
    whenever ``failed`` is non-zero.
    """
    return await order_service.admin_bulk_update_status(
        db,
        order_ids=body.ids,
        new_status=body.status,
        actor_id=actor_id,
        reason=body.notes,
    )


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
