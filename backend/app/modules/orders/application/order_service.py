"""Order application service — business logic, state machine, and audit logging.

All monetary values are stored as ``BigInteger`` (Rials).
"""

from __future__ import annotations

import contextlib
import math
import secrets
import string
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.modules.orders.application.admin_order_helpers import enrich_admin_order_rows
from app.modules.orders.domain.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)
from app.modules.orders.schemas.order import (
    AdminOrderDetailResponse,
    AdminOrderPaymentSummary,
    AdminOrderStatsResponse,
    AdminOrderStatusCount,
    OrderBulkStatusResult,
    OrderBulkStatusResultItem,
    OrderFilterParams,
    OrderItemResponse,
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
#
# The chain is deliberately short now (digital store, WooCommerce vocabulary):
#
#   waiting_payment_gateway ─┐                          ┌→ canceled
#   waiting_payment_card    ─┼→ pending → processing → ┴→ completed
#                    ┘                          └→ refunded
#
# REFUNDED is reachable from every non-terminal state, including the two
# payment-waiting ones: an admin can refund an order that never got paid for.
#
# WAITING_PAYMENT_CARD deliberately has no exit except an explicit admin action. The
# automated expiry sweep that cancels abandoned gateway payments MUST NOT touch
# it — the customer's money may already be in the account while the admin is
# still looking at the receipt, and silently canceling that order would destroy
# a sale (and lose the refund obligation).
_VALID_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    # Gateway order, awaiting the callback. Expires to CANCELED on a timer.
    OrderStatus.WAITING_PAYMENT_GATEWAY: frozenset(
        {OrderStatus.PENDING, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    ),
    # Card-to-card: waiting for an ADMIN. Never expires.
    OrderStatus.WAITING_PAYMENT_CARD: frozenset(
        {OrderStatus.PENDING, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    ),
    # Paid and accepted.
    OrderStatus.PENDING: frozenset(
        {OrderStatus.PROCESSING, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    ),
    # Being fulfilled / under review.
    OrderStatus.PROCESSING: frozenset(
        {OrderStatus.COMPLETED, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    ),
    OrderStatus.COMPLETED: frozenset(),  # terminal
    OrderStatus.CANCELED: frozenset(),  # terminal
    OrderStatus.REFUNDED: frozenset(),  # terminal
}

# Statuses the *customer* is allowed to cancel from
_CUSTOMER_CANCELABLE: frozenset[OrderStatus] = frozenset(
    {OrderStatus.WAITING_PAYMENT_GATEWAY, OrderStatus.WAITING_PAYMENT_CARD, OrderStatus.PENDING}
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


async def apply_refund_status(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    fully_refunded: bool,
    reason: str,
) -> OrderStatus | None:
    """Record a payment refund on an order through the order state machine.

    This is the ONLY sanctioned way for the payments module to change an
    order's status because of a refund — it validates the transition and
    writes the status-change history row.

    Returns the new status, or ``None`` when no transition applies (order
    missing, already fully refunded/canceled, or a further partial refund on
    an already partially refunded order).
    """
    order = await db.get(Order, order_id, with_for_update=True)
    if order is None:
        return None

    current = order.status
    if current in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
        return None

    # ``partially_refunded`` was removed as an order status (2026-10-11): the
    # partial amount is tracked on the Refund/Payment rows, not on the order,
    # so the order itself only ever reaches the terminal REFUNDED.
    target = OrderStatus.REFUNDED
    if target == current:
        return None

    _validate_transition(current, target)

    order.status = target
    await _record_status_change(
        db,
        order_id=order.id,
        from_status=current.value,
        to_status=target.value,
        changed_by=actor_id,
        reason=reason,
        extra_data={"initiated_by": "payment_refund"},
    )
    await logger.ainfo(
        "order_refund_status_applied",
        order_id=str(order.id),
        from_status=current.value,
        to_status=target.value,
        fully_refunded=fully_refunded,
    )
    return target


async def _refund_cancelled_order_to_wallet(
    db: AsyncSession,
    *,
    order: Order,
    actor_id: uuid.UUID,
    reason: str,
) -> int:
    """Credit the still-refundable amount of a cancelled order to the wallet.

    Records the ``Refund`` row, marks the payment fully refunded when the
    whole paid amount is returned, and credits the wallet inside the caller's
    transaction. Returns the refunded amount (0 when nothing is refundable).

    Callers must have loaded ``order.payments`` with each payment's
    ``refunds`` collection.
    """
    from app.modules.payments.domain.models import PaymentStatus, Refund, RefundStatus

    completed_payments = [p for p in order.payments if p.status == PaymentStatus.COMPLETED]
    paid_total = sum(p.amount for p in completed_payments)
    refunded_so_far = sum(
        r.amount for p in order.payments for r in p.refunds if r.status != RefundStatus.REJECTED
    )
    refundable = paid_total - refunded_so_far
    if refundable <= 0 or not completed_payments:
        return 0

    payment = completed_payments[0]
    db.add(
        Refund(
            payment_id=payment.id,
            order_id=order.id,
            amount=refundable,
            reason=reason,
            status=RefundStatus.PROCESSED,
            processed_by=actor_id,
            processed_at=datetime.now(UTC),
        )
    )
    if refundable == paid_total:
        payment.status = PaymentStatus.REFUNDED

    from app.modules.wallet.application import wallet_service
    from app.modules.wallet.domain.models import WalletTransactionType

    await wallet_service.credit(
        db,
        user_id=order.user_id,
        amount=refundable,
        tx_type=WalletTransactionType.REFUND,
        reference_type="order_cancel",
        reference_id=order.id,
        description=f"بازگشت وجه لغو سفارش {order.order_number}",
    )
    await logger.ainfo(
        "order_cancel_auto_refunded",
        order_id=str(order.id),
        amount=refundable,
        actor_id=str(actor_id),
    )
    return refundable


# ── Helpers ────────────────────────────────────────────────────────────────


def _generate_order_number() -> str:
    """Generate a human-readable order number: ``ORD-YYYYMMDD-XXXX``."""
    alphabet = string.ascii_uppercase + string.digits
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    random_part = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"ORD-{date_part}-{random_part}"


async def _record_status_change(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    from_status: str | None,
    to_status: str,
    changed_by: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    correlation_id: str | None = None,
    reason: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> OrderStatusHistory:
    """Insert an immutable audit record for a status transition."""
    effective_actor = actor_id or changed_by
    meta = dict(extra_data or {})

    # Extract correlation_id if not explicitly provided
    if correlation_id:
        meta["correlation_id"] = correlation_id
    elif "correlation_id" not in meta:
        with contextlib.suppress(Exception):
            ctx = structlog.contextvars.get_contextvars()
            cid = ctx.get("correlation_id") or ctx.get("request_id")
            if cid:
                meta["correlation_id"] = str(cid)

    if effective_actor and "actor_id" not in meta:
        meta["actor_id"] = str(effective_actor)

    entry = OrderStatusHistory(
        order_id=order_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=effective_actor,
        reason=reason,
        extra_data=meta or None,
    )
    db.add(entry)
    await db.flush()

    await logger.ainfo(
        "order_status_changed",
        order_id=str(order_id),
        from_status=from_status,
        to_status=to_status,
        changed_by=str(effective_actor) if effective_actor else None,
        actor_id=str(effective_actor) if effective_actor else None,
        correlation_id=meta.get("correlation_id"),
        reason=reason,
    )

    from app.shared.events.domain_events import (
        OrderCancelled,
        OrderStatusChanged,
        record_domain_event,
    )

    await record_domain_event(
        OrderStatusChanged(
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=effective_actor,
            reason=reason,
        ),
        aggregate_type="order",
        aggregate_id=order_id,
    )
    if to_status == OrderStatus.CANCELED.value:
        await record_domain_event(
            OrderCancelled(
                order_id=order_id,
                user_id=effective_actor or uuid.UUID(int=0),
                reason=reason,
            ),
            aggregate_type="order",
            aggregate_id=order_id,
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


def _build_item_response(item: OrderItem) -> OrderItemResponse:
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


def _apply_filters(stmt: Select[tuple[Order]], filters: OrderFilterParams) -> Select[tuple[Order]]:
    """Apply optional WHERE clauses to an order query."""
    if filters.status:
        stmt = stmt.where(Order.status == filters.status)
    elif filters.statuses:
        # `status` wins when both are sent: the caller asked for an exact
        # single status, and silently widening it to a set would return rows
        # it did not ask for.
        wanted = [s.strip() for s in filters.statuses if s and s.strip()]
        if wanted:
            stmt = stmt.where(Order.status.in_(wanted))
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
    # Lock the order row to prevent concurrent cancel/refund races (P0 fix).
    from app.core.exceptions.handlers import ConflictError
    from app.modules.payments.domain.models import Payment, PaymentStatus, RefundStatus

    lock_stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .with_for_update()
    )
    lock_result = await db.execute(lock_stmt)
    order = lock_result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    if order.status not in _CUSTOMER_CANCELABLE:
        raise ValidationError(
            f"Order in status '{order.status.value}' cannot be cancelled by the customer.",
            error_code="ORDER_NOT_CANCELABLE",
        )

    _validate_transition(order.status, OrderStatus.CANCELED)

    # Reload with eagerly-loaded relationships for refund computation.
    order = await db.get(
        Order,
        order.id,
        options=(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments).selectinload(Payment.refunds),
        ),
        populate_existing=True,
    )
    if order is None:  # pragma: no cover — row verified to exist above
        raise NotFoundError("Order")

    completed_payments = [p for p in order.payments if p.status == PaymentStatus.COMPLETED]
    paid_total = sum(p.amount for p in completed_payments)
    refunded_so_far = sum(
        r.amount for p in order.payments for r in p.refunds if r.status != RefundStatus.REJECTED
    )
    refundable = paid_total - refunded_so_far

    if refundable > 0:
        from app.modules.inventory.application import card_service

        has_delivered = await card_service.has_delivered_cards(db, order_id=order.id)
        if has_delivered:
            raise ConflictError(
                detail=(
                    "این سفارش کالای دیجیتال تحویل‌شده دارد و قابل لغو خودکار نیست؛ "
                    "برای بازگشت وجه با پشتیبانی تماس بگیرید"
                ),
                error_code="ORDER_HAS_DELIVERED_DIGITAL_GOODS",
            )

    from_status = order.status.value
    order.status = OrderStatus.CANCELED
    db.add(order)
    await db.flush()

    # Return reserved/committed stock to available inventory so an abandoned
    # order cannot permanently lock stock. Failures must abort the cancel so
    # the order is not marked CANCELED while units remain reserved/committed.
    from app.modules.inventory.application import inventory_service

    await inventory_service.restock_order(db, order.id)

    # Refund the remaining paid amount to the customer's wallet inside the
    # same transaction — cancelling a paid order must never silently keep
    # the money; restocking alone is not enough.
    refunded_amount = 0
    if refundable > 0 and completed_payments:
        refunded_amount = await _refund_cancelled_order_to_wallet(
            db,
            order=order,
            actor_id=user_id,
            reason=f"لغو سفارش توسط مشتری: {reason}",
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
    if refunded_amount > 0:
        await _publish_order_event(
            db,
            "RefundProcessed",
            order.id,
            {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "amount": refunded_amount,
                "initiated_by": "customer_cancel",
            },
        )

    await db.refresh(order, attribute_names=["status_history"])
    return _build_order_response(order)


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
        items=enrich_admin_order_rows(orders),
        meta=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1,
        ),
    )


async def admin_get_order_stats(db: AsyncSession) -> AdminOrderStatsResponse:
    """Count and sum orders per status across the whole table.

    One GROUP BY, not twelve COUNT queries: the admin board renders every
    column header at once, and per-status endpoints would make the board's
    first paint issue a dozen round trips. Zero-fill the enum so the UI
    receives every status even when no order carries it.
    """
    rows = await db.execute(
        select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .group_by(Order.status)
    )
    by_status = {str(status.value): (int(count), int(total)) for status, count, total in rows}

    statuses = [
        AdminOrderStatusCount(
            status=member.value,
            count=by_status.get(member.value, (0, 0))[0],
            total=by_status.get(member.value, (0, 0))[1],
        )
        for member in OrderStatus
    ]

    # Revenue excludes money that was given back or never became revenue:
    # canceled orders, refunds, and held orders that may still be canceled.
    revenue_statuses = {
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
        OrderStatus.COMPLETED,
    }
    total_orders = sum(entry.count for entry in statuses)
    total_revenue = sum(
        entry.total for entry in statuses if OrderStatus(entry.status) in revenue_statuses
    )

    return AdminOrderStatsResponse(
        by_status=statuses,
        total_orders=total_orders,
        total_revenue_rials=total_revenue,
    )


async def admin_get_order_detail(db: AsyncSession, order_id: uuid.UUID) -> AdminOrderDetailResponse:
    """Return one order with full (unmasked) address, payments and customer.

    Distinct from :func:`get_order` on purpose: that path is the customer's
    and masks the address + checks ownership. This path is admin-only
    (``orders:read``) and exists because the admin list endpoint carries no
    address snapshot and no payment rows — the old board fabricated both.
    """
    from app.modules.payments.domain.models import Payment

    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
        )
        .where(Order.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order")

    timeline = sorted((order.status_history or []), key=lambda h: h.created_at)
    payments = sorted(
        (order.payments or []),
        key=lambda p: p.created_at,
        reverse=True,
    )

    customer_name: str | None = None
    customer_phone: str | None = None
    user = getattr(order, "user", None)
    if user is not None:
        customer_phone = getattr(user, "phone", None)
        # Names live on the profile, not the user row (the old list mapper
        # read user.first_name, which does not exist — every admin screen
        # showed a null customer name).
        profile = getattr(user, "profile", None)
        if profile is not None:
            names = [
                getattr(profile, "first_name", None),
                getattr(profile, "last_name", None),
            ]
            customer_name = " ".join(n for n in names if n).strip() or None
        if not customer_name:
            profile_display = getattr(profile, "display_name", None) if profile else None
            customer_name = profile_display or None

    return AdminOrderDetailResponse(
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
        payments=[
            AdminOrderPaymentSummary.model_validate(p) for p in payments
        ],
        customer_name=customer_name,
        customer_phone=customer_phone,
        created_at=order.created_at,
        updated_at=order.updated_at,
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
        .with_for_update()
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    _validate_transition(order.status, target)

    from_status = order.status.value

    # Guard digital-goods + refund eligibility BEFORE mutating status or stock.
    # Restocking then raising would leave the order CANCELED with inventory already
    # returned, and a later retry would not reverse the restock.
    if target == OrderStatus.CANCELED:
        from app.core.exceptions.handlers import ConflictError
        from app.modules.inventory.application import card_service
        from app.modules.payments.domain.models import Payment, PaymentStatus

        order = await db.get(
            Order,
            order.id,
            options=(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.payments).selectinload(Payment.refunds),
            ),
            populate_existing=True,
        )
        if order is None:  # pragma: no cover — row verified to exist above
            raise NotFoundError("Order")

        completed_payments = [
            p for p in order.payments if p.status == PaymentStatus.COMPLETED
        ]
        if completed_payments:
            has_delivered = await card_service.has_delivered_cards(db, order_id=order.id)
            if has_delivered:
                raise ConflictError(
                    detail=(
                        "این سفارش کالای دیجیتال تحویل‌شده دارد؛ "
                        "لغو خودکار با بازگشت وجه ممکن نیست. "
                        "ابتدا کارت‌های تحویل‌شده را باطل کنید یا از مسیر بازگشت کالا اقدام کنید"
                    ),
                    error_code="ORDER_HAS_DELIVERED_DIGITAL_GOODS",
                )

    order.status = target
    db.add(order)
    await db.flush()

    # Cancelling an order must return its stock to available inventory.
    # Failures abort the transition so units cannot stay locked after cancel.
    if target == OrderStatus.CANCELED:
        from app.modules.inventory.application import inventory_service

        await inventory_service.restock_order(db, order.id)

        refunded_amount = await _refund_cancelled_order_to_wallet(
            db,
            order=order,
            actor_id=actor_id,
            reason=f"لغو سفارش توسط مدیر: {reason or 'بدون توضیح'}",
        )
        if refunded_amount > 0:
            await _publish_order_event(
                db,
                "RefundProcessed",
                order.id,
                {
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "amount": refunded_amount,
                    "initiated_by": "admin_cancel",
                },
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
    elif target in (
        OrderStatus.PROCESSING,
        OrderStatus.COMPLETED,
    ):
        await _publish_order_event(
            db,
            f"Order{target.value.capitalize()}",
            order.id,
            {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "from_status": from_status,
                "to_status": target.value,
                "initiated_by": "admin",
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


async def admin_bulk_update_status(
    db: AsyncSession,
    order_ids: list[uuid.UUID],
    new_status: str,
    actor_id: uuid.UUID,
    reason: str | None = None,
) -> OrderBulkStatusResult:
    """Admin: apply one status transition to many orders, per order.

    Every order goes through :func:`admin_update_status` — the same service
    the single-order PATCH uses — so the state machine, the restock, the
    wallet refund and the audit row cannot diverge between the two paths.
    There is deliberately no "fast lane" UPDATE statement here: a bulk
    transition that skipped the service would skip exactly the side effects
    that make a cancel reversible.

    A failure on one order must not take the batch down, and must not be
    reported as a success. Each order runs inside its own SAVEPOINT, so a
    rejected order rolls back only its own stock/refund/audit writes while
    the ones that already succeeded stay committed. The result carries the
    per-order reason, because "3 of 10 moved" is not actionable without
    knowing which three and why the other seven did not.
    """
    # Resolve the target once, up front: an unknown status is a request-level
    # error (422), not a per-order failure the operator would have to read 100
    # identical rows to diagnose.
    try:
        target = OrderStatus(new_status)
    except ValueError:
        valid = ", ".join(s.value for s in OrderStatus)
        raise ValidationError(
            f"Invalid status '{new_status}'. Valid statuses: {valid}",
            error_code="INVALID_STATUS",
        ) from None

    items: list[OrderBulkStatusResultItem] = []

    for order_id in order_ids:
        # Read the pre-state inside the savepoint so a rollback of a failed
        # order cannot leave a stale status cached on the identity map.
        try:
            async with db.begin_nested():
                before = await db.get(Order, order_id)
                from_status = before.status if before is not None else None
                order_number = before.order_number if before is not None else None
                await admin_update_status(
                    db,
                    order_id=order_id,
                    new_status=target.value,
                    actor_id=actor_id,
                    reason=reason,
                )
        except (NotFoundError, ValidationError, ConflictError) as exc:
            # The savepoint above is already rolled back: this order is
            # untouched, and the orders before it keep their committed writes.
            await logger.ainfo(
                "order_bulk_status_item_failed",
                order_id=str(order_id),
                target=target.value,
                error_code=getattr(exc, "error_code", None),
            )
            items.append(
                OrderBulkStatusResultItem(
                    order_id=order_id,
                    order_number=order_number,
                    status=target,
                    from_status=from_status,
                    success=False,
                    error_code=getattr(exc, "error_code", None) or type(exc).__name__,
                    detail=str(exc),
                )
            )
            continue
        except Exception as exc:  # one bad row must not kill the batch
            await logger.awarning(
                "order_bulk_status_item_error",
                order_id=str(order_id),
                target=target.value,
                error=str(exc),
            )
            items.append(
                OrderBulkStatusResultItem(
                    order_id=order_id,
                    order_number=order_number,
                    status=target,
                    from_status=from_status,
                    success=False,
                    error_code="BULK_ITEM_FAILED",
                    detail=f"خطای غیرمنتظره در تغییر وضعیت سفارش: {exc}",
                )
            )
            continue

        items.append(
            OrderBulkStatusResultItem(
                order_id=order_id,
                order_number=order_number,
                status=target,
                from_status=from_status,
                success=True,
            )
        )

    succeeded = sum(1 for i in items if i.success)
    result = OrderBulkStatusResult(
        requested=len(order_ids),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=items,
    )
    await logger.ainfo(
        "orders_bulk_status_updated",
        target=target.value,
        requested=result.requested,
        succeeded=result.succeeded,
        failed=result.failed,
    )
    return result


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
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    return f"ORD-{date_part}-{suffix}"

