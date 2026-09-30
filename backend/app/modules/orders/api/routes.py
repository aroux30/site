"""Order API routes — customer and admin endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    _extract_token,
    get_current_user_id,
)
from app.core.security.rate_limiter import limiter
from app.modules.orders.api.reseller_routes import router as reseller_router
from app.modules.orders.application import order_receipt_renderer, order_service
from app.modules.orders.schemas.order import (
    AdminOrderUpdateRequest,
    AdminReturnActionRequest,
    AdminReturnListResponse,
    OrderBulkStatusRequest,
    OrderBulkStatusResult,
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


async def _resolve_invoice_claims(
    payload: dict[str, Any] = Depends(_extract_token),
) -> dict[str, Any]:
    return payload


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

    html = await order_receipt_renderer.generate_invoice_html_for_order(
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


@router.get(
    "/{order_id}/returns",
    response_model=list[OrderReturnResponse],
    summary="List customer return requests (RMA) for an order",
)
async def list_order_returns(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[OrderReturnResponse]:
    return await order_service.get_order_returns(db, user_id, order_id)


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


# ── Admin RMA processing (TASK BE-20) ────────────────────────────────────


@router.get(
    "/admin/returns",
    response_model=AdminReturnListResponse,
    summary="Admin — list customer return requests (RMA)",
    dependencies=[Depends(RequirePermissions("orders:read"))],
)
async def admin_list_returns(
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AdminReturnListResponse:
    result = await order_service.admin_list_returns(
        db,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return AdminReturnListResponse(**result)


@router.post(
    "/admin/returns/{return_id}/transition",
    response_model=OrderReturnResponse,
    summary="Admin — apply one RMA state-machine transition",
    dependencies=[Depends(RequirePermissions("orders:write"))],
)
async def admin_transition_return(
    return_id: uuid.UUID,
    body: AdminReturnActionRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> OrderReturnResponse:
    """Move an RMA through its lifecycle: approve → receive → inspect →
    refund/replaced → close.  Transition rules are enforced by the domain
    state machine; REFUNDED also restocks passed inspection items.
    """
    return await order_service.admin_transition_return(
        db,
        return_id=return_id,
        target=body.target,
        actor_id=actor_id,
        notes=body.notes,
        inspection_outcomes=body.inspection_outcomes,
        refund_amount=body.refund_amount,
    )


# ── B2B Reseller API sub-router (Karta Phase 4) ────────────────────────────
router.include_router(reseller_router)
