"""Shipping API routes — public and admin endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.modules.shipping.application import shipping_service
from app.modules.shipping.schemas.shipping import (
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
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ShipmentResponse]:
    return await shipping_service.get_order_shipments(db, order_id)


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
        {"order_item_id": item.order_item_id, "quantity": item.quantity}
        for item in body.items
    ]
    return await shipping_service.create_shipment(
        db,
        order_id=body.order_id,
        method_id=body.method_id,
        items=items,
        actor_id=actor_id,
        tracking_code=body.tracking_code,
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
