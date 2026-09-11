"""Order application service — business logic, state machine, and audit logging.

All monetary values are stored as ``BigInteger`` (Rials).
"""

from __future__ import annotations

import math
import random
import string
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    NotFoundError,
    ValidationError,
)
from app.modules.orders.domain.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)
from app.modules.orders.schemas.order import (
    OrderFilterParams,
    OrderListItem,
    OrderListResponse,
    OrderResponse,
    OrderStatusHistoryResponse,
    OrderTimelineResponse,
    PaginationMeta,
    PaginationParams,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Order State Machine ────────────────────────────────────────────────────

# Maps current status → set of allowed next statuses
_VALID_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELED}),
    OrderStatus.CONFIRMED: frozenset(
        {OrderStatus.PROCESSING, OrderStatus.CANCELED, OrderStatus.ON_HOLD}
    ),
    OrderStatus.PROCESSING: frozenset({OrderStatus.PACKING, OrderStatus.ON_HOLD}),
    OrderStatus.ON_HOLD: frozenset({OrderStatus.PROCESSING, OrderStatus.CANCELED}),
    OrderStatus.PACKING: frozenset({OrderStatus.SHIPPED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.COMPLETED, OrderStatus.RETURNED}),
    OrderStatus.COMPLETED: frozenset(),  # terminal
    OrderStatus.CANCELED: frozenset(),  # terminal
    OrderStatus.RETURNED: frozenset({OrderStatus.REFUNDED, OrderStatus.PARTIALLY_REFUNDED}),
    OrderStatus.REFUNDED: frozenset(),  # terminal
    OrderStatus.PARTIALLY_REFUNDED: frozenset(),  # terminal
}

# Statuses the *customer* is allowed to cancel from
_CUSTOMER_CANCELABLE: frozenset[OrderStatus] = frozenset(
    {OrderStatus.PENDING, OrderStatus.CONFIRMED}
)


def _validate_transition(
    current: OrderStatus,
    target: OrderStatus,
) -> None:
    """Raise ``ValidationError`` if the transition is not allowed."""
    allowed = _VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValidationError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Allowed transitions: {', '.join(s.value for s in allowed) or '(none – terminal state)'}",  # noqa: E501
            error_code="INVALID_STATUS_TRANSITION",
        )


# ── Helpers ────────────────────────────────────────────────────────────────


def _generate_order_number() -> str:
    """Generate a human-readable order number: ``ORD-YYYYMMDD-XXXX``."""
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))  # noqa: S311  # order numbers are not security-sensitive
    return f"ORD-{date_part}-{random_part}"


async def _record_status_change(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    from_status: str | None,
    to_status: str,
    changed_by: uuid.UUID | None = None,
    reason: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> OrderStatusHistory:
    """Insert an immutable audit record for a status transition."""
    entry = OrderStatusHistory(
        order_id=order_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        reason=reason,
        extra_data=extra_data,
    )
    db.add(entry)
    await db.flush()

    await logger.ainfo(
        "order_status_changed",
        order_id=str(order_id),
        from_status=from_status,
        to_status=to_status,
        changed_by=str(changed_by) if changed_by else None,
        reason=reason,
    )
    return entry


def _build_order_response(order: Order) -> OrderResponse:
    """Map an ORM ``Order`` (with eagerly-loaded relations) to a response schema."""
    timeline = sorted(
        (order.status_history or []),
        key=lambda h: h.created_at,
    )
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        user_id=order.user_id,
        subtotal=order.subtotal,
        shipping_cost=order.shipping_cost,
        tax=order.tax,
        discount_amount=order.discount_amount,
        total=order.total,
        shipping_address_snapshot=order.shipping_address_snapshot,
        notes=order.notes,
        ip_address=order.ip_address,
        items=[_build_item_response(item) for item in (order.items or [])],
        timeline=[_build_history_response(h) for h in timeline],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _build_item_response(item: OrderItem):
    from app.modules.orders.schemas.order import OrderItemResponse

    return OrderItemResponse(
        id=item.id,
        variant_id=item.variant_id,
        product_name=item.product_name,
        variant_info=item.variant_info,
        sku=item.sku,
        quantity=item.quantity,
        unit_price=item.unit_price,
        total_price=item.total_price,
    )


def _build_history_response(h: OrderStatusHistory) -> OrderStatusHistoryResponse:
    return OrderStatusHistoryResponse(
        id=h.id,
        from_status=h.from_status,
        to_status=h.to_status,
        changed_by=h.changed_by,
        reason=h.reason,
        extra_data=h.extra_data,
        created_at=h.created_at,
    )


# ── Query helpers ──────────────────────────────────────────────────────────


def _apply_filters(stmt, filters: OrderFilterParams):
    """Apply optional WHERE clauses to an order query."""
    if filters.status:
        stmt = stmt.where(Order.status == filters.status)
    if filters.from_date:
        stmt = stmt.where(Order.created_at >= filters.from_date)
    if filters.to_date:
        stmt = stmt.where(Order.created_at <= filters.to_date)
    if filters.min_total is not None:
        stmt = stmt.where(Order.total >= filters.min_total)
    if filters.max_total is not None:
        stmt = stmt.where(Order.total <= filters.max_total)
    if filters.search:
        stmt = stmt.where(Order.order_number.ilike(f"%{filters.search}%"))
    return stmt


# ══════════════════════════════════════════════════════════════════════════
# Public API — Customer-facing
# ══════════════════════════════════════════════════════════════════════════


async def get_orders(
    db: AsyncSession,
    user_id: uuid.UUID,
    filters: OrderFilterParams,
    pagination: PaginationParams,
) -> OrderListResponse:
    """Return a paginated list of orders belonging to *user_id*."""
    base = select(Order).where(Order.user_id == user_id)
    base = _apply_filters(base, filters)

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    total_items: int = (await db.execute(count_stmt)).scalar_one()
    total_pages = max(1, math.ceil(total_items / pagination.page_size))

    # Fetch page
    stmt = (
        base.order_by(Order.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    await logger.ainfo(
        "orders_listed",
        user_id=str(user_id),
        total_items=total_items,
        page=pagination.page,
    )

    return OrderListResponse(
        items=[OrderListItem.model_validate(o) for o in orders],
        meta=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1,
        ),
    )


async def get_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
) -> OrderResponse:
    """Return full order details (items + timeline) for an order owned by *user_id*."""
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    return _build_order_response(order)


async def _publish_order_event(
    db: AsyncSession,
    event_type: str,
    order_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    """Publish an order lifecycle event to the transactional outbox.

    Failures are logged, never raised: notifications/analytics must not
    break the order flow.
    """
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type=event_type,
            aggregate_type="order",
            aggregate_id=str(order_id),
            payload=payload,
        )
    except Exception as exc:
        await logger.awarning(
            "order_event_publish_skipped",
            event_type=event_type,
            order_id=str(order_id),
            error=str(exc),
        )


async def cancel_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    reason: str,
) -> OrderResponse:
    """Cancel an order on behalf of the customer.

    Only orders in ``pending`` or ``confirmed`` status may be cancelled by
    the customer.
    """
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    if order.status not in _CUSTOMER_CANCELABLE:
        raise ValidationError(
            f"Order in status '{order.status.value}' cannot be cancelled by the customer.",
            error_code="ORDER_NOT_CANCELABLE",
        )

    _validate_transition(order.status, OrderStatus.CANCELED)

    from_status = order.status.value
    order.status = OrderStatus.CANCELED
    db.add(order)
    await db.flush()

    # Return reserved/committed stock to available inventory so an abandoned
    # order cannot permanently lock stock.
    from app.modules.inventory.application import inventory_service

    try:
        await inventory_service.restock_order(db, order.id)
    except Exception as exc:
        await logger.aerror(
            "order_cancel_restock_failed",
            order_id=str(order.id),
            error=str(exc),
        )

    await _record_status_change(
        db,
        order_id=order.id,
        from_status=from_status,
        to_status=OrderStatus.CANCELED.value,
        changed_by=user_id,
        reason=reason,
        extra_data={"initiated_by": "customer"},
    )
    await _publish_order_event(
        db,
        "OrderCanceled",
        order.id,
        {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "initiated_by": "customer",
            "reason": reason,
        },
    )

    await db.refresh(order, attribute_names=["status_history"])
    return _build_order_response(order)


async def request_order_return(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    body: Any,
) -> Any:
    """Customer request for order return (RMA) within statutory 7-day window."""
    from app.modules.orders.application.returns_service import ReturnsService
    from app.modules.orders.domain.returns import ReturnItemSpec, ReturnReason
    from app.modules.orders.schemas.order import OrderReturnResponse, ReturnItemResponse

    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    returns_service = ReturnsService(return_window_days=7)
    delivered_event = next(
        (h for h in (order.status_history or []) if h.to_status == OrderStatus.DELIVERED.value),
        None,
    )
    delivered_at = delivered_event.created_at if delivered_event else order.updated_at

    specs = [
        ReturnItemSpec(
            order_item_id=item.order_item_id,
            variant_id=item.variant_id,
            quantity=item.quantity,
            reason=ReturnReason(item.reason)
            if item.reason in [r.value for r in ReturnReason]
            else ReturnReason.CUSTOMER_REMORSE,
            customer_notes=item.customer_notes,
        )
        for item in body.items
    ]

    rma = returns_service.create_return_request(
        order=order,
        user_id=user_id,
        delivered_at=delivered_at,
        items=specs,
    )

    return OrderReturnResponse(
        id=rma.id,
        order_id=rma.order_id,
        user_id=rma.user_id,
        status=rma.status.value,
        items=[
            ReturnItemResponse(
                order_item_id=i.order_item_id,
                variant_id=i.variant_id,
                quantity=i.quantity,
                reason=i.reason.value,
                customer_notes=i.customer_notes,
                inspection_outcome=i.inspection_outcome.value if i.inspection_outcome else None,
            )
            for i in rma.items
        ],
        created_at=rma.created_at,
        approved_at=rma.approved_at,
        inspected_at=rma.inspected_at,
        refunded_at=rma.refunded_at,
        admin_notes=rma.admin_notes,
        refund_amount=rma.refund_amount,
    )


async def get_order_timeline(
    db: AsyncSession,
    order_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> OrderTimelineResponse:
    """Return the status timeline for an order.

    If *user_id* is supplied, ownership is checked (customer endpoint).
    """
    stmt = (
        select(Order)
        .options(
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id)
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)

    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    events = sorted(order.status_history, key=lambda h: h.created_at)
    return OrderTimelineResponse(
        order_id=order.id,
        order_number=order.order_number,
        current_status=order.status.value,
        events=[_build_history_response(h) for h in events],
    )


# ══════════════════════════════════════════════════════════════════════════
# Public API — Admin
# ══════════════════════════════════════════════════════════════════════════


async def admin_get_orders(
    db: AsyncSession,
    filters: OrderFilterParams,
    pagination: PaginationParams,
) -> OrderListResponse:
    """Admin: list all orders with optional filters and pagination."""
    base = select(Order)
    base = _apply_filters(base, filters)

    count_stmt = select(func.count()).select_from(base.subquery())
    total_items: int = (await db.execute(count_stmt)).scalar_one()
    total_pages = max(1, math.ceil(total_items / pagination.page_size))

    stmt = (
        base.order_by(Order.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    await logger.ainfo(
        "admin_orders_listed",
        total_items=total_items,
        page=pagination.page,
    )

    return OrderListResponse(
        items=[OrderListItem.model_validate(o) for o in orders],
        meta=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1,
        ),
    )


async def admin_update_status(
    db: AsyncSession,
    order_id: uuid.UUID,
    new_status: str,
    actor_id: uuid.UUID,
    reason: str | None = None,
) -> OrderResponse:
    """Admin: transition an order to a new status with full audit logging."""
    # Resolve the target enum
    try:
        target = OrderStatus(new_status)
    except ValueError:
        valid = ", ".join(s.value for s in OrderStatus)
        raise ValidationError(
            f"Invalid status '{new_status}'. Valid statuses: {valid}",
            error_code="INVALID_STATUS",
        ) from None

    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    _validate_transition(order.status, target)

    from_status = order.status.value
    order.status = target
    db.add(order)
    await db.flush()

    # Cancelling an order must return its stock to available inventory.
    if target == OrderStatus.CANCELED:
        from app.modules.inventory.application import inventory_service

        try:
            await inventory_service.restock_order(db, order.id)
        except Exception as exc:
            await logger.aerror(
                "admin_cancel_restock_failed",
                order_id=str(order.id),
                error=str(exc),
            )
        await _publish_order_event(
            db,
            "OrderCanceled",
            order.id,
            {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "initiated_by": "admin",
                "reason": reason,
            },
        )

    await _record_status_change(
        db,
        order_id=order.id,
        from_status=from_status,
        to_status=target.value,
        changed_by=actor_id,
        reason=reason,
        extra_data={"initiated_by": "admin"},
    )

    await db.refresh(order, attribute_names=["status_history"])
    return _build_order_response(order)


# ══════════════════════════════════════════════════════════════════════════
# Order-number generation (used by checkout / order-creation flows)
# ══════════════════════════════════════════════════════════════════════════


async def generate_unique_order_number(db: AsyncSession) -> str:
    """Generate a unique order number, retrying on collision.

    Format: ``ORD-YYYYMMDD-XXXX`` (e.g. ``ORD-20260909-A3K7``).
    """
    for _ in range(10):
        candidate = _generate_order_number()
        exists_stmt = select(select(Order.id).where(Order.order_number == candidate).exists())
        exists = (await db.execute(exists_stmt)).scalar_one()
        if not exists:
            return candidate
    # Extremely unlikely – fallback with more randomness
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))  # noqa: S311  # order numbers are not security-sensitive
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    return f"ORD-{date_part}-{suffix}"
