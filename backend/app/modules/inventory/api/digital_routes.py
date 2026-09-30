"""API endpoints for digital cards, bulk import, and tiered pricing (Karta Phase 1/2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.inventory.application import (
    card_admin_queries,
    card_service,
    import_service,
    pricing_service,
)
from app.modules.inventory.domain.digital_models import (
    DigitalCard,
    DigitalCardStatus,
    DigitalDeliveryType,
)
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

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

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
    reading_at = card.reading_at  # mark_card_viewed guarantees a timestamp
    assert reading_at is not None
    return MarkCardReadResponse(id=card.id, reading_at=reading_at)


@router.get(
    "/cards/{card_id}/file",
    summary="Securely download a file-type digital card (authenticated buyer only)",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_card_file(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve a file-type card to its buyer (Karta file_to_cards).

    Authenticated + ownership-checked + expiry-checked + audit-logged; the
    raw storage path is never exposed in API responses (P0.6).
    """
    card, resolved_path = await card_service.get_card_file_for_owner(
        db, card_id=card_id, user_id=user_id
    )
    download_name = card.serial_number or f"license-{card.id.hex[:12]}"
    return FileResponse(
        resolved_path,
        filename=download_name,
        media_type="application/octet-stream",
    )


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
    "/file-assets",
    response_model=dict[str, Any],
    summary="Upload a file asset for file-type digital products (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def upload_file_asset(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Store a license/config file in the secure (non-public) assets dir.

    Returns the server-side path to attach to FILE-type card rows; the raw
    path is never exposed to customers — downloads go through the
    authenticated ``/cards/{id}/file`` endpoint (P0.6).
    """
    import re as _re
    from pathlib import Path as _Path

    from app.core.config.settings import get_settings

    settings = get_settings()
    original = file.filename or "asset.bin"
    safe_name = _re.sub(r"[^A-Za-z0-9._-]", "_", original)[-80:] or "asset.bin"
    ext = _Path(safe_name).suffix.lower()
    allowed = {".pdf", ".zip", ".txt", ".jpg", ".jpeg", ".png", ".webp", ".conf", ".yaml", ".yml"}
    if ext not in allowed:
        raise NotFoundError(resource="FileAsset", detail=f"پسوند فایل مجاز نیست: {ext}")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise NotFoundError(resource="FileAsset", detail="حجم فایل بیش از ۲۰ مگابایت است")

    assets_dir = _Path(settings.UPLOAD_DIR) / "digital_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}-{safe_name}"
    target = assets_dir / stored_name
    target.write_bytes(content)

    await logger.ainfo("digital_file_asset_uploaded", stored=str(target), bytes=len(content))
    return {"file_path": str(target), "original_name": original, "size": len(content)}


@router.post(
    "/cards/file",
    response_model=dict[str, Any],
    summary="Stock N sellable copies of one file asset (admin, Karta file_to_cards)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def create_file_cards(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    product_id = uuid.UUID(str(body.get("product_id")))
    copies = int(body.get("copies", 1))
    expire_at = body.get("expire_at")
    parsed_expire = (
        datetime.fromisoformat(str(expire_at).replace("Z", "+00:00")) if expire_at else None
    )
    cards = await card_service.add_file_cards(
        db,
        product_id=product_id,
        file_path=str(body.get("file_path") or ""),
        copies=copies,
        expire_at=parsed_expire,
    )
    return {"created": len(cards), "product_id": str(product_id)}


@router.patch(
    "/cards/batch",
    response_model=dict[str, Any],
    summary="Batch edit digital cards (status / expiry) — Karta batch edit",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def batch_edit_cards(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    card_ids = [uuid.UUID(str(cid)) for cid in (body.get("card_ids") or [])]
    if not card_ids or len(card_ids) > 1000:
        raise NotFoundError(resource="DigitalCard", detail="بین ۱ تا ۱۰۰۰ کارت انتخاب کنید")

    status_value = body.get("status")
    expire_at = body.get("expire_at")
    clear_expire = bool(body.get("clear_expire"))
    if not status_value and not expire_at and not clear_expire:
        raise NotFoundError(
            resource="DigitalCard", detail="حداقل یک فیلد برای ویرایش گروهی لازم است"
        )

    from sqlalchemy import select as _select

    stmt = _select(DigitalCard).where(DigitalCard.id.in_(card_ids)).with_for_update()
    cards = list((await db.execute(stmt)).scalars().all())

    updated = 0
    for card in cards:
        if status_value:
            card.status = DigitalCardStatus(status_value)
        if clear_expire:
            card.expire_at = None
        elif expire_at:
            card.expire_at = datetime.fromisoformat(str(expire_at).replace("Z", "+00:00"))
        updated += 1
    await db.flush()
    await logger.ainfo("digital_cards_batch_edited", requested=len(card_ids), updated=updated)
    return {"requested": len(card_ids), "updated": updated}


@router.post(
    "/rekey",
    response_model=dict[str, Any],
    summary="Re-encrypt all card payloads with the active key (key rotation sweep)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def rekey_cards(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await card_service.reencrypt_all_cards(db)



@router.get(
    "/cards",
    response_model=dict[str, Any],
    summary="List digital cards, newest first (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def list_cards(
    status: str | None = Query(None, description="Filter by card status"),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    status_enum = DigitalCardStatus(status) if status else None
    rows = await card_admin_queries.list_cards_for_admin(
        db, status=status_enum, limit=limit
    )
    items = [DigitalCardResponse.model_validate(row) for row in rows]
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "count": len(items),
    }


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
    description=(
        "B2B/wholesale only: tiers are applied by the reseller order pipeline, "
        "never at retail checkout."
    ),
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
