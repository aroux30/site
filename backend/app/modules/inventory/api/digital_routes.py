"""API endpoints for digital cards, bulk import, and tiered pricing (Karta Phase 1/2)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.inventory.application import (
    card_service,
    import_service,
    pricing_service,
)
from app.modules.inventory.domain.digital_models import DigitalDeliveryType
from app.modules.inventory.schemas.digital import (
    BulkImportSummaryResponse,
    DeliveredCardResponse,
    DigitalCardCreateRequest,
    DigitalCardResponse,
    DynamicPriceCalculationResponse,
    MarkCardReadResponse,
    PriceTierCreateRequest,
    PriceTierResponse,
)

router = APIRouter(prefix="/digital", tags=["inventory-digital"])


# ── Customer Endpoints ────────────────────────────────────────────────────


@router.get(
    "/orders/{order_id}/cards",
    response_model=list[DeliveredCardResponse],
    summary="Get delivered decrypted cards for an order (customer view)",
)
async def get_order_cards(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[DeliveredCardResponse]:
    # Ownership guard: decrypted PINs may only be read by the buyer.
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")
    cards = await card_service.get_delivered_cards_for_order(db, order_id=order_id)
    return [DeliveredCardResponse.model_validate(c) for c in cards]


@router.post(
    "/cards/{card_id}/viewed",
    response_model=MarkCardReadResponse,
    summary="Mark card PIN as viewed (Karta legal reading audit flag)",
)
async def mark_card_read(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MarkCardReadResponse:
    card = await card_service.mark_card_viewed(db, card_id=card_id, user_id=user_id)
    return MarkCardReadResponse(id=card.id, reading_at=card.reading_at)


@router.get(
    "/products/{product_id}/price",
    response_model=DynamicPriceCalculationResponse,
    summary="Calculate tiered volume price for a product quantity (Karta findPrice)",
)
async def calculate_price(
    product_id: uuid.UUID,
    quantity: int = Query(..., ge=1),
    base_price: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_db),
) -> DynamicPriceCalculationResponse:
    calc = await pricing_service.calculate_dynamic_price(
        db, product_id=product_id, quantity=quantity, base_unit_price=base_price
    )
    return DynamicPriceCalculationResponse.model_validate(calc)


# ── Admin Endpoints ───────────────────────────────────────────────────────


@router.post(
    "/cards",
    response_model=DigitalCardResponse,
    summary="Add a single digital card to inventory (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def create_single_card(
    body: DigitalCardCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> DigitalCardResponse:
    card = await card_service.add_single_card(
        db,
        product_id=body.product_id,
        pin=body.pin,
        serial_number=body.serial_number,
        delivery_type=body.delivery_type,
        max_uses=body.max_uses,
        expire_at=body.expire_at,
        file_path=body.file_path,
    )
    return DigitalCardResponse.model_validate(card)


@router.post(
    "/cards/import",
    response_model=BulkImportSummaryResponse,
    summary="Bulk import cards from Excel (.xlsx/.xls) or CSV (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def bulk_import(
    product_id: uuid.UUID = Form(...),
    delivery_type: DigitalDeliveryType = Form(DigitalDeliveryType.UNIQUE),
    max_uses: int = Form(1),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> BulkImportSummaryResponse:
    content = await file.read()
    result = await import_service.bulk_import_cards(
        db,
        product_id=product_id,
        file_bytes=content,
        filename=file.filename or "cards.csv",
        delivery_type=delivery_type,
        max_uses=max_uses,
    )
    return BulkImportSummaryResponse.model_validate(result)


@router.post(
    "/pricing-tiers",
    response_model=PriceTierResponse,
    summary="Create a volume pricing tier for a product (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def create_price_tier(
    body: PriceTierCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> PriceTierResponse:
    tier = await pricing_service.set_price_tier(
        db,
        product_id=body.product_id,
        from_qty=body.from_qty,
        to_qty=body.to_qty,
        unit_price=body.unit_price,
    )
    return PriceTierResponse.model_validate(tier)


@router.get(
    "/products/{product_id}/pricing-tiers",
    response_model=list[PriceTierResponse],
    summary="List volume pricing tiers for a product",
)
async def get_price_tiers(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[PriceTierResponse]:
    tiers = await pricing_service.list_price_tiers(db, product_id=product_id)
    return [PriceTierResponse.model_validate(t) for t in tiers]
