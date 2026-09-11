"""Shipping application service — rate calculation, shipment lifecycle, and audit logging.

All monetary values are ``BigInteger`` (Rials).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.shipping.domain.models import (
    Shipment,
    ShipmentItem,
    ShipmentStatus,
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

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Shipment state machine ─────────────────────────────────────────────────

_SHIPMENT_TRANSITIONS: dict[ShipmentStatus, frozenset[ShipmentStatus]] = {
    ShipmentStatus.PENDING: frozenset({ShipmentStatus.PROCESSING, ShipmentStatus.SHIPPED}),
    ShipmentStatus.PROCESSING: frozenset({ShipmentStatus.SHIPPED}),
    ShipmentStatus.SHIPPED: frozenset({ShipmentStatus.IN_TRANSIT}),
    ShipmentStatus.IN_TRANSIT: frozenset({ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED}),
    ShipmentStatus.DELIVERED: frozenset(),  # terminal
    ShipmentStatus.RETURNED: frozenset(),  # terminal
}


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
            best_rate.min_order_amount is not None
            and order_amount >= best_rate.min_order_amount
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
) -> Optional[ShippingRate]:
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
    items: list[dict],
    actor_id: uuid.UUID,
    tracking_code: Optional[str] = None,
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
    status: Optional[str] = None,
    tracking_code: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
) -> ShipmentResponse:
    """Update a shipment's status and/or tracking code (admin operation)."""
    stmt = (
        select(Shipment)
        .options(selectinload(Shipment.items))
        .where(Shipment.id == shipment_id)
    )
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
            )

        _validate_shipment_transition(shipment.status, target)

        old_status = shipment.status.value
        shipment.status = target

        # Auto-set timestamps
        now = datetime.now(timezone.utc)
        if target == ShipmentStatus.SHIPPED and shipment.shipped_at is None:
            shipment.shipped_at = now
        if target == ShipmentStatus.DELIVERED and shipment.delivered_at is None:
            shipment.delivered_at = now

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


async def get_shipment(
    db: AsyncSession,
    shipment_id: uuid.UUID,
) -> ShipmentResponse:
    """Return a single shipment by ID."""
    stmt = (
        select(Shipment)
        .options(selectinload(Shipment.items))
        .where(Shipment.id == shipment_id)
    )
    result = await db.execute(stmt)
    shipment = result.scalar_one_or_none()

    if shipment is None:
        raise NotFoundError("Shipment")

    return _build_shipment_response(shipment)


async def get_order_shipments(
    db: AsyncSession,
    order_id: uuid.UUID,
) -> list[ShipmentResponse]:
    """Return all shipments for a given order."""
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
        stmt_uuid = select(Shipment).options(selectinload(Shipment.method)).where(Shipment.id == s_id)
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

    return {
        "shipment_id": str(shipment.id),
        "order_id": str(shipment.order_id),
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
