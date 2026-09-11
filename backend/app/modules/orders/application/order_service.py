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

    # Persist the RMA (BE-20): the lifecycle must be durable and
    # admin-processable, not an in-memory object lost after the response.
    from app.modules.orders.domain.return_models import (
        OrderReturn as OrderReturnRow,
    )
    from app.modules.orders.domain.return_models import (
        OrderReturnItem as OrderReturnItemRow,
    )

    rma_number = f"RMA-{rma.created_at.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    rma_row = OrderReturnRow(
        id=rma.id,
        rma_number=rma_number,
        order_id=rma.order_id,
        user_id=rma.user_id,
        status=rma.status.value,
        admin_notes=rma.admin_notes,
        created_at=rma.created_at,
    )
    for i in rma.items:
        rma_row.items.append(
            OrderReturnItemRow(
                return_id=rma.id,
                order_item_id=i.order_item_id,
                variant_id=i.variant_id,
                quantity=i.quantity,
                reason=i.reason.value,
                customer_notes=i.customer_notes,
            )
        )
    db.add(rma_row)
    await db.flush()

    return OrderReturnResponse(
        id=rma.id,
        rma_number=rma_number,
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
            return candidate
    # Extremely unlikely – fallback with more randomness
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))  # noqa: S311  # order numbers are not security-sensitive
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    return f"ORD-{date_part}-{suffix}"


# ══════════════════════════════════════════════════════════════════════════
# Admin RMA processing (TASK BE-20)
# ══════════════════════════════════════════════════════════════════════════


def _rma_row_to_response(row: Any) -> Any:
    """Map an OrderReturn row (with items) to the API response."""
    from app.modules.orders.schemas.order import OrderReturnResponse, ReturnItemResponse

    return OrderReturnResponse(
        id=row.id,
        rma_number=row.rma_number,
        order_id=row.order_id,
        user_id=row.user_id,
        status=row.status,
        items=[
            ReturnItemResponse(
                order_item_id=i.order_item_id,
                variant_id=i.variant_id,
                quantity=i.quantity,
                reason=i.reason,
                customer_notes=i.customer_notes,
                inspection_outcome=i.inspection_outcome,
            )
            for i in (row.items or [])
        ],
        created_at=row.created_at,
        approved_at=row.approved_at,
        inspected_at=row.inspected_at,
        refunded_at=row.refunded_at,
        admin_notes=row.admin_notes,
        refund_amount=row.refund_amount,
    )


async def admin_list_returns(
    db: AsyncSession,
    status_filter: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Admin: paginated list of RMAs, newest first."""
    from app.modules.orders.domain.return_models import OrderReturn

    stmt = select(OrderReturn).order_by(OrderReturn.created_at.desc())
    count_stmt = select(func.count()).select_from(OrderReturn)
    if status_filter:
        stmt = stmt.filter_by(status=status_filter)
        count_stmt = count_stmt.filter_by(status=status_filter)

    total = (await db.scalar(count_stmt)) or 0
    rows = (await db.scalars(stmt.limit(page_size).offset((page - 1) * page_size))).all()
    return {
        "items": [_rma_row_to_response(r) for r in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


async def admin_transition_return(
    db: AsyncSession,
    return_id: uuid.UUID,
    target: str,
    actor_id: uuid.UUID,
    notes: str | None = None,
    inspection_outcomes: dict[str, str] | None = None,
    refund_amount: int | None = None,
) -> Any:
    """Admin: apply one RMA state-machine transition with full audit.

    On REFUNDED, passed inspection items are restocked (P3-01) and a
    ReturnRefunded event is published.  On APPROVED a ReturnApproved event
    is published.  All transition rules come from the domain state machine
    (``orders/domain/returns.py``), never from the caller.
    """
    from app.modules.orders.application.returns_service import ReturnsService
    from app.modules.orders.domain.return_models import OrderReturn as OrderReturnRow
    from app.modules.orders.domain.returns import (
        RETURN_TRANSITIONS,
        InspectionOutcome,
        OrderReturnDomain,
        ReturnItemSpec,
        ReturnReason,
        ReturnStatus,
    )

    try:
        target_status = ReturnStatus(target)
    except ValueError:
        valid = ", ".join(s.value for s in ReturnStatus)
        raise ValidationError(
            f"Invalid return status '{target}'. Valid statuses: {valid}",
            error_code="INVALID_RETURN_STATUS",
        ) from None

    safe_return_id = uuid.UUID(str(return_id))
    row = await db.get(OrderReturnRow, safe_return_id, with_for_update=True)
    if row is None:
        raise NotFoundError("Return")

    rma = OrderReturnDomain(
        id=row.id,
        order_id=row.order_id,
        user_id=row.user_id,
        status=ReturnStatus(row.status),
        items=[
            ReturnItemSpec(
                order_item_id=i.order_item_id,
                variant_id=i.variant_id,
                quantity=i.quantity,
                reason=ReturnReason(i.reason),
                customer_notes=i.customer_notes,
                inspection_outcome=InspectionOutcome(i.inspection_outcome)
                if i.inspection_outcome
                else None,
            )
            for i in (row.items or [])
        ],
        created_at=row.created_at,
        approved_at=row.approved_at,
        inspected_at=row.inspected_at,
        refunded_at=row.refunded_at,
        admin_notes=row.admin_notes,
        refund_amount=row.refund_amount,
    )

    # Pre-check with the domain machine so an illegal move is a clean 422
    # (the domain transition would otherwise raise a bare ValueError).
    if not rma.can_transition_to(target_status):
        allowed = ", ".join(s.value for s in RETURN_TRANSITIONS.get(rma.status, frozenset()))
        raise ValidationError(
            f"Cannot transition return from '{rma.status.value}' to "
            f"'{target_status.value}'. Allowed: {allowed}",
            error_code="INVALID_RETURN_TRANSITION",
        )

    service = ReturnsService(return_window_days=7)
    if target_status == ReturnStatus.APPROVED:
        service.approve_return(rma, notes)
    elif target_status == ReturnStatus.REJECTED:
        service.reject_return(rma, notes or "")
    elif target_status == ReturnStatus.RECEIVED:
        service.mark_received(rma)
    elif target_status == ReturnStatus.INSPECTED:
        outcomes: dict[uuid.UUID, Any] = {}
        if inspection_outcomes:
            for item_id_str, outcome_str in inspection_outcomes.items():
                outcomes[uuid.UUID(item_id_str)] = InspectionOutcome(outcome_str)
        service.complete_inspection(rma, outcomes, notes)
    elif target_status == ReturnStatus.REFUNDED:
        service.process_refund(rma, refund_amount or 0)
    else:
        # CLOSED / REPLACED
        rma.transition_to(target_status, notes)

    # Persist transition results
    row.status = rma.status.value
    if notes:
        row.admin_notes = notes
    row.approved_at = rma.approved_at
    row.inspected_at = rma.inspected_at
    row.refunded_at = rma.refunded_at
    row.refund_amount = rma.refund_amount
    if target_status == ReturnStatus.INSPECTED:
        outcome_by_item = {i.order_item_id: i.inspection_outcome for i in rma.items}
        for item_row in row.items or []:
            outcome = outcome_by_item.get(item_row.order_item_id)
            item_row.inspection_outcome = outcome.value if outcome else None
    await db.flush()

    # Restock passed items when the return is financially settled (P3-01)
    if target_status == ReturnStatus.REFUNDED:
        from app.modules.inventory.application import inventory_service

        entries = [
            (i.variant_id, i.quantity)
            for i in rma.items
            if i.inspection_outcome == InspectionOutcome.PASSED
        ]
        if entries:
            try:
                await inventory_service.restock_returned_items(db, entries)
            except Exception as exc:
                await logger.aerror(
                    "return_restock_failed",
                    return_id=str(row.id),
                    error=str(exc),
                )

    # Lifecycle events
    try:
        from app.shared.events.outbox_service import OutboxService

        if target_status == ReturnStatus.APPROVED:
            await OutboxService.publish(
                db,
                event_type="ReturnApproved",
                aggregate_type="return",
                aggregate_id=str(row.id),
                payload={
                    "return_id": str(row.id),
                    "order_id": str(row.order_id),
                    "rma_number": row.rma_number,
                },
            )
        elif target_status == ReturnStatus.REFUNDED:
            await OutboxService.publish(
                db,
                event_type="ReturnRefunded",
                aggregate_type="return",
                aggregate_id=str(row.id),
                payload={
                    "return_id": str(row.id),
                    "order_id": str(row.order_id),
                    "rma_number": row.rma_number,
                    "refund_amount": row.refund_amount,
                },
            )
    except Exception as exc:
        await logger.awarning(
            "return_event_publish_skipped",
            return_id=str(row.id),
            error=str(exc),
        )

    await logger.ainfo(
        "return_transitioned",
        return_id=str(row.id),
        to_status=target_status.value,
        actor_id=str(actor_id),
    )
    return _rma_row_to_response(row)
