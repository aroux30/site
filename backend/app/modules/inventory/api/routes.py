"""Inventory management API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.inventory.api.digital_routes import router as digital_router
from app.modules.inventory.application import inventory_service
from app.modules.inventory.domain.models import TransactionType
from app.modules.inventory.schemas.inventory import (
    InventoryAdjustRequest,
    InventoryListResponse,
    InventoryResponse,
    InventoryTransactionResponse,
    LowStockAlert,
    TransactionListResponse,
)

router = APIRouter()


# ── Admin list ─────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=InventoryListResponse,
    summary="List all inventory items (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    low_stock_only: bool = Query(False),
    track_inventory: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> InventoryListResponse:
    items, total = await inventory_service.get_inventory_list(
        db,
        page=page,
        page_size=page_size,
        low_stock_only=low_stock_only,
        track_inventory=track_inventory,
    )
    return InventoryListResponse(
        items=[InventoryResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Low-stock (must be before /{variant_id} to avoid path collision) ──────


@router.get(
    "/low-stock",
    response_model=list[LowStockAlert],
    summary="List low-stock items (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def get_low_stock(
    threshold: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[LowStockAlert]:
    items, _ = await inventory_service.get_low_stock_items(
        db,
        threshold=threshold,
        page=page,
        page_size=page_size,
    )
    return [LowStockAlert.model_validate(i) for i in items]


# ── Single variant ─────────────────────────────────────────────────────────


@router.get(
    "/{variant_id}",
    response_model=InventoryResponse,
    summary="Get inventory for a variant",
)
async def get_variant_inventory(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InventoryResponse:
    item = await inventory_service.get_inventory(db, variant_id)
    return InventoryResponse.model_validate(item)


# ── Stock adjustment (admin) ──────────────────────────────────────────────


@router.post(
    "/{variant_id}/adjust",
    response_model=InventoryResponse,
    summary="Adjust stock for a variant (admin)",
    dependencies=[Depends(RequirePermissions("inventory:write"))],
)
async def adjust_stock(
    variant_id: uuid.UUID,
    body: InventoryAdjustRequest,
    db: AsyncSession = Depends(get_db),
) -> InventoryResponse:
    item = await inventory_service.adjust_stock(
        db,
        variant_id=variant_id,
        quantity=body.quantity,
        tx_type=body.type,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        notes=body.notes,
    )
    return InventoryResponse.model_validate(item)


# ── Transaction history (admin) ───────────────────────────────────────────


@router.get(
    "/{variant_id}/transactions",
    response_model=TransactionListResponse,
    summary="Get transaction history for a variant (admin)",
    dependencies=[Depends(RequirePermissions("inventory:read"))],
)
async def get_transactions(
    variant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: TransactionType | None = Query(None),  # noqa: A002  # API parameter name is the public contract
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    txns, total = await inventory_service.get_transactions(
        db,
        variant_id=variant_id,
        page=page,
        page_size=page_size,
        tx_type=type,
    )
    return TransactionListResponse(
        items=[InventoryTransactionResponse.model_validate(t) for t in txns],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Digital inventory sub-router (Karta Phase 1/2) ─────────────────────────
router.include_router(digital_router)
