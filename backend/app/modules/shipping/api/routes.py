"""Shipping API routes — public and admin endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_active_user,
    get_current_user_id,
)
from app.modules.shipping.application import shipping_service
from app.modules.shipping.schemas.shipping import (
    PickupPointResponse,
    PickupPointUpsertRequest,
    ShipmentCancelRequest,
    ShipmentCreateRequest,
    ShipmentResponse,
    ShipmentUpdateRequest,
    ShippingMethodResponse,
    ShippingQuoteRequest,
    ShippingQuoteResponse,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════
# Public endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/methods",
    response_model=list[ShippingMethodResponse],
    summary="List active shipping methods",
)
async def list_shipping_methods(
    db: AsyncSession = Depends(get_db),
) -> list[ShippingMethodResponse]:
    return await shipping_service.get_shipping_methods(db)


@router.post(
    "/quote",
    response_model=ShippingQuoteResponse,
    summary="Calculate shipping cost for given parameters",
)
async def get_shipping_quote(
    body: ShippingQuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> ShippingQuoteResponse:
    return await shipping_service.calculate_shipping(
        db,
        province=body.province,
        weight=body.weight,
        order_amount=body.order_amount,
    )


@router.get(
    "/orders/{order_id}/shipments",
    response_model=list[ShipmentResponse],
    summary="Get shipments for an order",
)
async def get_order_shipments(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ShipmentResponse]:
    return await shipping_service.get_order_shipments(db, order_id, user_id=user_id)


@router.get(
    "/track/{tracking_code}",
    summary="Track a shipment using carrier integration",
)
async def track_shipment(
    tracking_code: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await shipping_service.track_shipment_with_carrier(db, tracking_code)


# ══════════════════════════════════════════════════════════════════════════
# Admin endpoints
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/admin/shipments",
    response_model=ShipmentResponse,
    summary="Admin — create a shipment for an order",
    dependencies=[Depends(RequirePermissions("shipping:write"))],
)
async def admin_create_shipment(
    body: ShipmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ShipmentResponse:
    items = [
        {"order_item_id": item.order_item_id, "quantity": item.quantity} for item in body.items
    ]
    return await shipping_service.create_shipment(
        db,
        order_id=body.order_id,
        method_id=body.method_id,
        items=items,
        actor_id=actor_id,
        tracking_code=body.tracking_code,
        delivery_type=body.delivery_type,
        pickup_point_id=body.pickup_point_id,
    )


@router.patch(
    "/admin/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    summary="Admin — update shipment status or tracking code",
    dependencies=[Depends(RequirePermissions("shipping:write"))],
)
async def admin_update_shipment(
    shipment_id: uuid.UUID,
    body: ShipmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ShipmentResponse:
    return await shipping_service.update_shipment_status(
        db,
        shipment_id=shipment_id,
        status=body.status,
        tracking_code=body.tracking_code,
        actor_id=actor_id,
    )



# -- Cancellation, pickup points, cash-on-delivery (ERP feature #32) --------


@router.post(
    "/admin/shipments/{shipment_id}/cancel",
    response_model=ShipmentResponse,
    status_code=200,
    summary="Cancel a pre-pickup shipment (admin)",
    dependencies=[Depends(RequirePermissions("shipping:write"))],
)
async def admin_cancel_shipment(
    shipment_id: uuid.UUID,
    body: ShipmentCancelRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ShipmentResponse:
    """Cancel a shipment the carrier has not collected yet.

    Refused once the parcel is out; the carrier is notified best-effort.
    """
    return await shipping_service.cancel_shipment(
        db, shipment_id, reason=body.reason, actor_id=actor_id
    )


@router.post(
    "/admin/shipments/{shipment_id}/cod-collected",
    response_model=ShipmentResponse,
    summary="Record cash-on-delivery remittance (admin)",
    dependencies=[Depends(RequirePermissions("shipping:write"))],
)
async def admin_mark_cod_collected(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ShipmentResponse:
    """Stamp a COD shipment as settled. Idempotent."""
    return await shipping_service.mark_cod_collected(db, shipment_id, actor_id=actor_id)


@router.get(
    "/pickup-points",
    response_model=list[PickupPointResponse],
    summary="List pickup points (public)",
)
async def get_pickup_points(
    db: AsyncSession = Depends(get_db),
    city: str | None = Query(None, description="Filter by city"),
    provider: str | None = Query(None, description="Filter by carrier"),
) -> list[PickupPointResponse]:
    """Pickup locations offered at checkout, optionally filtered."""
    points = await shipping_service.list_pickup_points(db, city=city, provider=provider)
    return [PickupPointResponse.model_validate(p) for p in points]


@router.post(
    "/admin/pickup-points",
    response_model=PickupPointResponse,
    status_code=201,
    summary="Create or refresh a pickup point (admin)",
    dependencies=[Depends(RequirePermissions("shipping:write"))],
)
async def admin_upsert_pickup_point(
    body: PickupPointUpsertRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_active_user),
) -> PickupPointResponse:
    """Upsert by (provider, external_id) -- carrier networks are re-imported."""
    point = await shipping_service.upsert_pickup_point(db, **body.model_dump())
    await db.commit()
    return PickupPointResponse.model_validate(point)
