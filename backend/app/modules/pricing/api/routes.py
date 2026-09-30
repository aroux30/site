"""Price list admin API (Odoo product.pricelist concept, clean-room)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions
from app.modules.pricing.application import pricelist_admin_service
from app.modules.pricing.schemas.pricing import (
    PriceListCreate,
    PriceListDetailResponse,
    PriceListListResponse,
    PriceListResponse,
)

router = APIRouter()

_require_pricing_write = Depends(RequirePermissions("pricing:write"))
_require_pricing_read = Depends(RequirePermissions("pricing:read"))


@router.get(
    "/price-lists",
    response_model=PriceListListResponse,
    summary="List price lists (admin)",
    dependencies=[_require_pricing_read],
)
async def list_price_lists(
    db: AsyncSession = Depends(get_db),
) -> PriceListListResponse:
    lists = await pricelist_admin_service.list_price_lists(db)
    return PriceListListResponse(
        items=[PriceListResponse.model_validate(p) for p in lists],
        total=len(lists),
    )


@router.post(
    "/price-lists",
    response_model=PriceListDetailResponse,
    status_code=201,
    summary="Create a price list with rules (admin)",
    dependencies=[_require_pricing_write],
)
async def create_price_list(
    body: PriceListCreate,
    db: AsyncSession = Depends(get_db),
) -> PriceListDetailResponse:
    price_list = await pricelist_admin_service.create_price_list(db, body)
    return PriceListDetailResponse.model_validate(price_list)


@router.get(
    "/price-lists/{price_list_id}",
    response_model=PriceListDetailResponse,
    summary="Get a price list with its rules (admin)",
    dependencies=[_require_pricing_read],
)
async def get_price_list(
    price_list_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PriceListDetailResponse:
    price_list = await pricelist_admin_service.get_price_list(db, price_list_id)
    if price_list is None:
        raise NotFoundError(resource="PriceList", detail=f"Price list {price_list_id} not found")
    return PriceListDetailResponse.model_validate(price_list)
