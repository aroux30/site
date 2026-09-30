"""Shipping application service — rate calculation, shipment lifecycle, and audit logging.

All monetary values are ``BigInteger`` (Rials).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.shipping.domain.models import (
    DeliveryType,
    PickupPoint,
    Shipment,
    ShipmentItem,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShippingMethod,
    ShippingRate,
)
from app.modules.shipping.schemas.shipping import (
    ShipmentItemResponse,
    ShipmentResponse,
    ShippingMethodResponse,
    ShippingQuoteMethodItem,
    ShippingQuoteResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Shipment state machine ─────────────────────────────────────────────────

_SHIPMENT_TRANSITIONS: dict[ShipmentStatus, frozenset[ShipmentStatus]] = {
    ShipmentStatus.PENDING: frozenset(
        {ShipmentStatus.PROCESSING, ShipmentStatus.SHIPPED, ShipmentStatus.CANCELLED}
    ),
    ShipmentStatus.PROCESSING: frozenset({ShipmentStatus.SHIPPED, ShipmentStatus.CANCELLED}),
    # Once the carrier has it, cancellation is no longer a status flip — the
    # parcel is physically out and must come back (RETURNED). This is why the
    # cancel endpoint refuses a SHIPPED/IN_TRANSIT shipment.
    ShipmentStatus.SHIPPED: frozenset({ShipmentStatus.IN_TRANSIT}),
    ShipmentStatus.IN_TRANSIT: frozenset({ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED}),
    ShipmentStatus.DELIVERED: frozenset(),  # terminal
    ShipmentStatus.RETURNED: frozenset(),  # terminal
    ShipmentStatus.CANCELLED: frozenset(),  # terminal
}

#: Statuses from which a shipment can still be cancelled (pre-pickup).
CANCELLABLE_STATUSES: frozenset[ShipmentStatus] = frozenset(
    {ShipmentStatus.PENDING, ShipmentStatus.PROCESSING}
)


def _validate_shipment_transition(
    current: ShipmentStatus,
    target: ShipmentStatus,
) -> None:
    """Raise ``ValidationError`` when the transition is not permitted."""
    allowed = _SHIPMENT_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValidationError(
            f"Cannot transition shipment from '{current.value}' to '{target.value}'. "
            f"Allowed: {', '.join(s.value for s in allowed) or '(terminal)'}",
            error_code="INVALID_SHIPMENT_TRANSITION",
        )


# ── Helpers ────────────────────────────────────────────────────────────────


def _build_shipment_response(shipment: Shipment) -> ShipmentResponse:
    """Map ORM ``Shipment`` to its Pydantic response."""
    return ShipmentResponse(
        id=shipment.id,
        order_id=shipment.order_id,
        method_id=shipment.method_id,
        tracking_code=shipment.tracking_code,
        status=shipment.status.value,
        shipped_at=shipment.shipped_at,
        delivered_at=shipment.delivered_at,
        items=[
            ShipmentItemResponse(
                id=item.id,
                order_item_id=item.order_item_id,
                quantity=item.quantity,
            )
            for item in (shipment.items or [])
        ],
        delivery_type=getattr(shipment, "delivery_type", DeliveryType.HOME).value
        if getattr(shipment, "delivery_type", None) is not None
        else DeliveryType.HOME.value,
        cod_amount_rial=shipment.cod_amount_rial,
        cod_collected_at=shipment.cod_collected_at,
        pickup_point_id=shipment.pickup_point_id,
        cancelled_at=shipment.cancelled_at,
        cancelled_reason=shipment.cancelled_reason,
        label_url=shipment.label_url,
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
    )


# ══════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════


async def get_shipping_methods(db: AsyncSession) -> list[ShippingMethodResponse]:
    """Return all **active** shipping methods."""
    stmt = (
        select(ShippingMethod)
        .where(ShippingMethod.is_active.is_(True))
        .order_by(ShippingMethod.name)
    )
    result = await db.execute(stmt)
    methods = result.scalars().all()

    await logger.ainfo("shipping_methods_listed", count=len(methods))

    return [ShippingMethodResponse.model_validate(m) for m in methods]


async def calculate_shipping(
    db: AsyncSession,
    province: str,
    weight: float,
    order_amount: int,
) -> ShippingQuoteResponse:
    """Calculate shipping cost for each active method.

    Rate selection logic:
    1. Look for a rate that matches the exact *province*, and whose weight /
       price thresholds cover the given values.
    2. Fall back to a rate with ``province IS NULL`` (default / nationwide rate).
    3. If the rate's ``min_order_amount`` is set and the order meets it the
       shipping is free.
    """
    stmt = (
        select(ShippingMethod)
        .options(selectinload(ShippingMethod.rates))
        .where(ShippingMethod.is_active.is_(True))
    )
    result = await db.execute(stmt)
    methods = result.scalars().all()

    quote_items: list[ShippingQuoteMethodItem] = []

    for method in methods:
        best_rate = _find_best_rate(method.rates, province, weight, order_amount)
        if best_rate is None:
            continue  # no applicable rate for this method

        is_free = (
            best_rate.min_order_amount is not None and order_amount >= best_rate.min_order_amount
        )

        quote_items.append(
            ShippingQuoteMethodItem(
                method_id=method.id,
                name=method.name,
                slug=method.slug,
                provider=method.provider,
                estimated_days_min=method.estimated_days_min,
                estimated_days_max=method.estimated_days_max,
                price=0 if is_free else best_rate.price,
                is_free=is_free,
            )
        )

    await logger.ainfo(
        "shipping_quote_calculated",
        province=province,
        weight=weight,
        order_amount=order_amount,
        options=len(quote_items),
    )

    return ShippingQuoteResponse(
        province=province,
        weight=weight,
        order_amount=order_amount,
        methods=quote_items,
    )


def _find_best_rate(
    rates: list[ShippingRate],
    province: str,
    weight: float,
    order_amount: int,
) -> ShippingRate | None:
    """Pick the most specific matching rate from a method's rate list.

    Province-specific rates take priority over nationwide (province=NULL).
    """
    province_lower = province.lower()
    province_rates: list[ShippingRate] = []
    default_rates: list[ShippingRate] = []

    for rate in rates:
        # Weight check
        if rate.min_weight is not None and weight < rate.min_weight:
            continue
        if rate.max_weight is not None and weight > rate.max_weight:
            continue

        if rate.province is not None and rate.province.lower() == province_lower:
            province_rates.append(rate)
        elif rate.province is None:
            default_rates.append(rate)

    # Pick cheapest within most specific group
    candidates = province_rates or default_rates
    if not candidates:
        return None
    return min(candidates, key=lambda r: r.price)


# ── Shipment CRUD ──────────────────────────────────────────────────────────


async def create_shipment(
    db: AsyncSession,
    order_id: uuid.UUID,
    method_id: uuid.UUID,
    items: list[dict[str, Any]],
    actor_id: uuid.UUID,
    tracking_code: str | None = None,
    delivery_type: DeliveryType | str = DeliveryType.HOME,
    pickup_point_id: uuid.UUID | None = None,
) -> ShipmentResponse:
    """Create a new shipment for an order (admin operation)."""
    # Validate method exists
    method = await db.get(ShippingMethod, method_id)
    if method is None:
        raise NotFoundError("ShippingMethod")

    # Validate order exists and can be shipped
    from app.modules.orders.domain.models import Order, OrderStatus

    order = await db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order")
    if order.status in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
        raise ValidationError(f"Cannot create shipment for order in status {order.status.value}")

    if isinstance(delivery_type, str):
        try:
            delivery_type = DeliveryType(delivery_type)
        except ValueError as exc:
            raise ValidationError(
                f"نوع تحویل نامعتبر است: {delivery_type}", error_code="INVALID_DELIVERY_TYPE"
            ) from exc

    # COD amount = what the courier must collect at the door: the order's
    # unpaid balance. Refunded money is excluded because a refund means the
    # order was already paid at least once.
    cod_amount = None
    if delivery_type == DeliveryType.CASH_ON_DELIVERY:
        from sqlalchemy import func as sa_func

        from app.modules.payments.domain.models import Payment, PaymentStatus

        already_paid = await db.scalar(
            select(sa_func.coalesce(sa_func.sum(Payment.amount), 0)).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.COMPLETED,
            )
        )
        cod_amount = cod_amount_for_order(order.total, int(already_paid or 0))

    resolved_tracking_code = tracking_code
    if not resolved_tracking_code:
        from app.modules.shipping.infrastructure.carrier_provider import ShippingProviderFactory

        provider = ShippingProviderFactory.get_provider(method.provider or "internal")
        dispatch_res = await provider.create_shipment(
            order_id=order_id,
            recipient_name="مشتری",
            recipient_phone="09120000000",
            full_address="تهران",
            postal_code="1122334455",
            weight_kg=1.0,
        )
        resolved_tracking_code = dispatch_res.tracking_code

    shipment = Shipment(
        order_id=order_id,
        method_id=method_id,
        tracking_code=resolved_tracking_code,
        status=ShipmentStatus.PENDING,
        delivery_type=delivery_type,
        cod_amount_rial=cod_amount,
        pickup_point_id=pickup_point_id,
    )
    db.add(shipment)
    await db.flush()

    for item_data in items:
        shipment_item = ShipmentItem(
            shipment_id=shipment.id,
            order_item_id=item_data["order_item_id"],
            quantity=item_data["quantity"],
        )
        db.add(shipment_item)

    # Initial tracking timeline event (GAP-18)
    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=ShipmentStatus.PENDING,
            description="ثبت اولیه و ایجاد درخواست مرسوله پستی",
        )
    )

    await db.flush()

    # Reload with items
    await db.refresh(shipment, attribute_names=["items"])

    await logger.ainfo(
        "shipment_created",
        shipment_id=str(shipment.id),
        order_id=str(order_id),
        method_id=str(method_id),
        actor_id=str(actor_id),
        item_count=len(items),
    )

    return _build_shipment_response(shipment)


async def update_shipment_status(
    db: AsyncSession,
    shipment_id: uuid.UUID,
    status: str | None = None,
    tracking_code: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> ShipmentResponse:
    """Update a shipment's status and/or tracking code (admin operation)."""
    stmt = select(Shipment).options(selectinload(Shipment.items)).where(Shipment.id == shipment_id)
    result = await db.execute(stmt)
    shipment = result.scalar_one_or_none()

    if shipment is None:
        raise NotFoundError("Shipment")

    if status is not None:
        try:
            target = ShipmentStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in ShipmentStatus)
            raise ValidationError(
                f"Invalid shipment status '{status}'. Valid: {valid}",
                error_code="INVALID_SHIPMENT_STATUS",
            ) from None

        _validate_shipment_transition(shipment.status, target)

        old_status = shipment.status.value
        shipment.status = target

        # Auto-set timestamps
        now = datetime.now(UTC)
        if target == ShipmentStatus.SHIPPED and shipment.shipped_at is None:
            shipment.shipped_at = now
        if target == ShipmentStatus.DELIVERED and shipment.delivered_at is None:
            shipment.delivered_at = now

            # Synchronize order status to DELIVERED to activate statutory 7-day RMA window
            from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory

            order = await db.get(Order, shipment.order_id)
            if order and order.status != OrderStatus.DELIVERED:
                old_order_status = order.status.value
                order.status = OrderStatus.DELIVERED
                db.add(
                    OrderStatusHistory(
                        order_id=order.id,
                        from_status=old_order_status,
                        to_status=OrderStatus.DELIVERED.value,
                        changed_by=actor_id,
                        reason=(
                            f"تحویل مرسوله پستی به مشتری "
                            f"(کد رهگیری: {shipment.tracking_code or str(shipment.id)})"
                        ),
                    )
                )

        # Append shipment tracking event log (GAP-18)
        db.add(
            ShipmentTrackingEvent(
                shipment_id=shipment.id,
                status=target,
                description=f"تغییر وضعیت مرسوله به {target.value}",
            )
        )

        await logger.ainfo(
            "shipment_status_updated",
            shipment_id=str(shipment_id),
            from_status=old_status,
            to_status=target.value,
            actor_id=str(actor_id) if actor_id else None,
        )

    if tracking_code is not None:
        shipment.tracking_code = tracking_code
        await logger.ainfo(
            "shipment_tracking_updated",
            shipment_id=str(shipment_id),
            tracking_code=tracking_code,
        )

    db.add(shipment)
    await db.flush()
    await db.refresh(shipment, attribute_names=["items"])

    return _build_shipment_response(shipment)


async def get_shipment_tracking_timeline(
    db: AsyncSession,
    shipment_id: uuid.UUID,
) -> list[ShipmentTrackingEvent]:
    """Retrieve the full tracking timeline for a shipment (GAP-18)."""
    stmt = (
        select(ShipmentTrackingEvent)
        .where(ShipmentTrackingEvent.shipment_id == shipment_id)
        .order_by(ShipmentTrackingEvent.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_shipment(
    db: AsyncSession,
    shipment_id: uuid.UUID,
) -> ShipmentResponse:
    """Return a single shipment by ID."""
    stmt = select(Shipment).options(selectinload(Shipment.items)).where(Shipment.id == shipment_id)
    result = await db.execute(stmt)
    shipment = result.scalar_one_or_none()

    if shipment is None:
        raise NotFoundError("Shipment")

    return _build_shipment_response(shipment)


async def get_order_shipments(
    db: AsyncSession,
    order_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[ShipmentResponse]:
    """Return all shipments for a given order.

    When ``user_id`` is supplied (customer-facing route) the order must
    belong to that user; otherwise the order is reported as not found so a
    customer cannot enumerate another customer's shipments by order id.
    """
    if user_id is not None:
        from app.modules.orders.domain.models import Order

        owner_stmt = select(Order.user_id).where(Order.id == order_id)
        owner_id = (await db.execute(owner_stmt)).scalar_one_or_none()
        if owner_id is None or owner_id != user_id:
            raise NotFoundError("Order")

    stmt = (
        select(Shipment)
        .options(selectinload(Shipment.items))
        .where(Shipment.order_id == order_id)
        .order_by(Shipment.created_at)
    )
    result = await db.execute(stmt)
    shipments = result.scalars().all()

    return [_build_shipment_response(s) for s in shipments]


async def track_shipment_with_carrier(
    db: AsyncSession,
    shipment_id_or_code: str,
) -> dict[str, Any]:
    """Track shipment events using the designated carrier provider."""
    from app.modules.shipping.infrastructure.carrier_provider import ShippingProviderFactory

    shipment = None
    try:
        s_id = uuid.UUID(shipment_id_or_code)
        stmt_uuid = (
            select(Shipment).options(selectinload(Shipment.method)).where(Shipment.id == s_id)
        )
        res_uuid = await db.execute(stmt_uuid)
        shipment = res_uuid.scalar_one_or_none()
    except ValueError:
        pass

    if shipment is None:
        stmt = (
            select(Shipment)
            .options(selectinload(Shipment.method))
            .where(Shipment.tracking_code == shipment_id_or_code)
        )
        res = await db.execute(stmt)
        shipment = res.scalar_one_or_none()

    if shipment is None or not shipment.tracking_code:
        raise NotFoundError("Shipment")

    provider_name = "internal"
    if shipment.method and shipment.method.provider:
        provider_name = shipment.method.provider

    provider = ShippingProviderFactory.get_provider(provider_name)
    tracking_result = await provider.track_shipment(shipment.tracking_code)

    # This result is served by the public /track/{code} route, so internal
    # identifiers (shipment/order UUIDs) are deliberately omitted — the
    # caller already holds the one handle they are entitled to: the carrier
    # tracking code. Exposing the UUIDs let anyone holding a code enumerate
    # internal order/shipment ids.
    return {
        "tracking_code": tracking_result.tracking_code,
        "carrier": provider.provider_name,
        "status": tracking_result.status,
        "is_delivered": tracking_result.is_delivered,
        "events": [
            {
                "status": e.status,
                "location": e.location,
                "timestamp": e.timestamp.isoformat(),
                "description": e.description,
            }
            for e in tracking_result.events
        ],
    }


# -- Cancellation, cash-on-delivery, pickup points (ERP feature #32) --------


async def cancel_shipment(
    db: AsyncSession,
    shipment_id: uuid.UUID,
    *,
    reason: str,
    actor_id: uuid.UUID | None = None,
) -> ShipmentResponse:
    """Cancel a shipment that the carrier has not collected yet.

    Refused once the parcel is out (SHIPPED/IN_TRANSIT): at that point the
    only honest operation is a return, not a cancellation that would leave
    the carrier holding a parcel we claim does not exist. The carrier's own
    ``cancel_shipment`` is called too -- a tracking code that stays live at
    the carrier after we cancel locally is a support ticket waiting to happen.
    """
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise NotFoundError("Shipment")

    if shipment.status not in CANCELLABLE_STATUSES:
        raise ValidationError(
            f"مرسوله در وضعیت «{shipment.status.value}» قابل لغو نیست. "
            "لغو فقط تا پیش از تحویل به پست امکان‌پذیر است.",
            error_code="SHIPMENT_NOT_CANCELLABLE",
        )
    if not (reason or "").strip():
        raise ValidationError(
            "دلیل لغو مرسوله الزامی است",
            error_code="CANCELLATION_REASON_REQUIRED",
        )

    # Best-effort carrier-side cancellation: our record flips regardless, and
    # the failure is logged loudly because it means the carrier still expects
    # the parcel.
    if shipment.tracking_code:
        provider_name = "internal"
        if shipment.method and shipment.method.provider:
            provider_name = shipment.method.provider
        try:
            from app.modules.shipping.infrastructure.carrier_provider import (
                ShippingProviderFactory,
            )

            provider = ShippingProviderFactory.get_provider(provider_name)
            cancelled_at_carrier = await provider.cancel_shipment(shipment.tracking_code)
            if not cancelled_at_carrier:
                await logger.awarning(
                    "carrier_cancel_returned_false",
                    shipment_id=str(shipment_id),
                    tracking_code=shipment.tracking_code,
                    provider=provider_name,
                )
        except Exception:
            await logger.aexception(
                "carrier_cancel_failed",
                shipment_id=str(shipment_id),
                tracking_code=shipment.tracking_code,
                provider=provider_name,
            )

    shipment.status = ShipmentStatus.CANCELLED
    shipment.cancelled_at = datetime.now(UTC)
    shipment.cancelled_reason = reason.strip()

    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=ShipmentStatus.CANCELLED,
            description=f"لغو مرسوله — {reason.strip()}",
        )
    )
    await db.flush()

    await logger.ainfo(
        "shipment_cancelled",
        shipment_id=str(shipment_id),
        order_id=str(shipment.order_id),
        reason=reason.strip(),
        actor_id=str(actor_id) if actor_id else None,
    )
    return _build_shipment_response(shipment)


async def mark_cod_collected(
    db: AsyncSession,
    shipment_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> ShipmentResponse:
    """Record that the courier remitted the cash-on-delivery amount.

    Idempotent: a second call returns the shipment unchanged rather than
    double-crediting anything. The money itself is settled through the
    payment pipeline (a COD payment record); this only stamps the shipment.
    """
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise NotFoundError("Shipment")
    if shipment.delivery_type != DeliveryType.CASH_ON_DELIVERY:
        raise ValidationError(
            "این مرسوله پرداخت در محل نیست",
            error_code="NOT_CASH_ON_DELIVERY",
        )
    if shipment.cod_collected_at is not None:
        return _build_shipment_response(shipment)

    shipment.cod_collected_at = datetime.now(UTC)
    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=shipment.status,
            description="تسویه وجه پرداخت در محل با پیک",
        )
    )
    await db.flush()
    await logger.ainfo(
        "cod_collected",
        shipment_id=str(shipment_id),
        amount_rial=shipment.cod_amount_rial,
        actor_id=str(actor_id) if actor_id else None,
    )
    return _build_shipment_response(shipment)


async def list_pickup_points(
    db: AsyncSession,
    *,
    city: str | None = None,
    provider: str | None = None,
    active_only: bool = True,
) -> list[PickupPoint]:
    """List pickup points, optionally filtered by city and carrier."""
    stmt = select(PickupPoint).order_by(PickupPoint.city, PickupPoint.name)
    if city:
        stmt = stmt.where(PickupPoint.city == city)
    if provider:
        stmt = stmt.where(PickupPoint.provider == provider)
    if active_only:
        stmt = stmt.where(PickupPoint.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def upsert_pickup_point(
    db: AsyncSession,
    *,
    provider: str,
    external_id: str,
    name: str,
    city: str,
    address: str,
    province: str | None = None,
    postal_code: str | None = None,
    phone: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> PickupPoint:
    """Create or refresh a pickup point by (provider, external_id).

    Upsert rather than insert: carrier networks are re-imported periodically
    (addresses and phone numbers change), and a duplicate row would show the
    customer two entries for one physical shop.
    """
    existing = (
        await db.execute(
            select(PickupPoint).where(
                PickupPoint.provider == provider,
                PickupPoint.external_id == external_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        point = PickupPoint(
            provider=provider,
            external_id=external_id,
            name=name,
            city=city,
            address=address,
            province=province,
            postal_code=postal_code,
            phone=phone,
            latitude=latitude,
            longitude=longitude,
        )
        db.add(point)
        await db.flush()
        return point

    existing.name = name
    existing.city = city
    existing.address = address
    existing.province = province
    existing.postal_code = postal_code
    existing.phone = phone
    existing.latitude = latitude
    existing.longitude = longitude
    await db.flush()
    return existing


def cod_amount_for_order(order_total_rial: int, amount_already_paid_rial: int) -> int:
    """The cash a courier must collect: the order's unpaid balance.

    Pure function so the rule is testable: a COD shipment never collects more
    than is owed and never a negative amount (an over-paid order collects
    nothing at the door -- the difference is a refund, not a courier problem).
    """
    return max(0, int(order_total_rial) - int(amount_already_paid_rial))
