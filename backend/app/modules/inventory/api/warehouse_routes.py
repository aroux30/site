"""Warehouse CRUD and stock-by-warehouse admin endpoints.

Permission convention: these are *catalogue* endpoints, so they follow the
generic inventory split rather than the physical-ops ``inventory:counts``
grant — reads need ``inventory:read``, every mutation needs ``inventory:write``
(the same pair the adjust and reorder-rule endpoints already use). Counting,
transferring, and receiving stock stay on ``inventory:counts``.

Mounted under ``/api/v1/admin/inventory/warehouses/*`` via ``admin_router``.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.inventory.application import warehouse_service
from app.modules.inventory.schemas.warehouse import (
    VariantStockListResponse,
    VariantStockRow,
    WarehouseCreateRequest,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseStockListResponse,
    WarehouseStockRow,
    WarehouseStockSummary,
    WarehouseUpdateRequest,
)

router = APIRouter()

_require_read = Depends(RequirePermissions("inventory:read"))
_require_write = Depends(RequirePermissions("inventory:write"))


def _summary(buckets: dict[str, int]) -> WarehouseStockSummary:
    return WarehouseStockSummary.from_buckets(
        variant_count=buckets.get("variant_count", 0),
        available=buckets.get("available", 0),
        reserved=buckets.get("reserved", 0),
        committed=buckets.get("committed", 0),
        damaged=buckets.get("damaged", 0),
        incoming=buckets.get("incoming", 0),
    )


# ── Static paths first (they must not be shadowed by /{warehouse_id}) ──────


@router.get(
    "/warehouses/stock",
    response_model=WarehouseStockListResponse,
    summary="Current stock aggregated per warehouse (admin)",
    dependencies=[_require_read],
)
async def list_stock_by_warehouse(
    db: AsyncSession = Depends(get_db),
) -> WarehouseStockListResponse:
    """Stock levels per warehouse, plus a grand total across all of them."""
    rows: list[dict[str, Any]] = await warehouse_service.list_stock_by_warehouse(db)
    items = [
        WarehouseStockRow(
            warehouse_id=row["warehouse_id"],
            name=row["name"],
            code=row["code"],
            is_default=row["is_default"],
            is_active=row["is_active"],
            is_registered=row["is_registered"],
            stock=_summary(row["stock"]),
        )
        for row in rows
    ]
    totals = WarehouseStockSummary.from_buckets(
        variant_count=sum(item.stock.variant_count for item in items),
        available=sum(item.stock.available for item in items),
        reserved=sum(item.stock.reserved for item in items),
        committed=sum(item.stock.committed for item in items),
        damaged=sum(item.stock.damaged for item in items),
        incoming=sum(item.stock.incoming for item in items),
    )
    return WarehouseStockListResponse(items=items, total=len(items), totals=totals)


@router.get(
    "/warehouses/default",
    response_model=WarehouseResponse | None,
    summary="The warehouse currently flagged as default (admin)",
    dependencies=[_require_read],
)
async def get_default_warehouse(db: AsyncSession = Depends(get_db)) -> WarehouseResponse | None:
    """``null`` when no catalogue row is flagged default yet.

    The ledger's own fallback remains the fixed sentinel warehouse; this
    endpoint reports the *catalogue* flag only.
    """
    warehouse = await warehouse_service.get_default_warehouse(db)
    if warehouse is None:
        return None
    buckets = await warehouse_service.get_stock_summary(db, warehouse.id)
    return WarehouseResponse.from_warehouse(warehouse, stock=_summary(buckets))


# ── Collection ─────────────────────────────────────────────────────────────


@router.get(
    "/warehouses",
    response_model=WarehouseListResponse,
    summary="List warehouses (admin)",
    dependencies=[_require_read],
)
async def list_warehouses(
    is_active: bool | None = Query(None),
    include_stock: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> WarehouseListResponse:
    rows = await warehouse_service.list_warehouses(
        db, is_active=is_active, include_stock=include_stock
    )
    return WarehouseListResponse(
        items=[
            WarehouseResponse.from_warehouse(warehouse, stock=_summary(buckets))
            for warehouse, buckets in rows
        ],
        total=len(rows),
    )


@router.post(
    "/warehouses",
    response_model=WarehouseResponse,
    status_code=201,
    summary="Create a warehouse (admin)",
    dependencies=[_require_write],
)
async def create_warehouse(
    body: WarehouseCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> WarehouseResponse:
    warehouse = await warehouse_service.create_warehouse(
        db,
        name=body.name,
        code=body.code,
        address=body.address,
        is_default=body.is_default,
    )
    return WarehouseResponse.from_warehouse(warehouse)


# ── Single warehouse ───────────────────────────────────────────────────────


@router.get(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Get a warehouse with its stock summary (admin)",
    dependencies=[_require_read],
)
async def get_warehouse(
    warehouse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WarehouseResponse:
    warehouse = await warehouse_service.get_warehouse(db, warehouse_id)
    buckets = await warehouse_service.get_stock_summary(db, warehouse.id)
    return WarehouseResponse.from_warehouse(warehouse, stock=_summary(buckets))


@router.patch(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Update a warehouse (admin)",
    dependencies=[_require_write],
)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    body: WarehouseUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> WarehouseResponse:
    """Edit name/code/address, and optionally promote this warehouse to default.

    ``address`` is passed through only when the client sent the key at all, so
    an omitted address is left untouched while an explicit ``null`` clears it.
    """
    fields = body.model_dump(exclude_unset=True)
    warehouse = await warehouse_service.update_warehouse(
        db,
        warehouse_id,
        name=fields.get("name"),
        code=fields.get("code"),
        address=fields.get("address", warehouse_service.UNSET),
        is_default=fields.get("is_default"),
    )
    buckets = await warehouse_service.get_stock_summary(db, warehouse.id)
    return WarehouseResponse.from_warehouse(warehouse, stock=_summary(buckets))


@router.post(
    "/warehouses/{warehouse_id}/deactivate",
    response_model=WarehouseResponse,
    summary="Deactivate a warehouse that holds no stock or history (admin)",
    dependencies=[_require_write],
)
async def deactivate_warehouse(
    warehouse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WarehouseResponse:
    warehouse = await warehouse_service.deactivate_warehouse(db, warehouse_id)
    return WarehouseResponse.from_warehouse(warehouse)


@router.post(
    "/warehouses/{warehouse_id}/reactivate",
    response_model=WarehouseResponse,
    summary="Return a deactivated warehouse to service (admin)",
    dependencies=[_require_write],
)
async def reactivate_warehouse(
    warehouse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WarehouseResponse:
    warehouse = await warehouse_service.reactivate_warehouse(db, warehouse_id)
    return WarehouseResponse.from_warehouse(warehouse)


@router.get(
    "/warehouses/stock/variants/{variant_id}",
    response_model=VariantStockListResponse,
    summary="One variant's stock across warehouses (admin, transfer helper)",
    dependencies=[_require_read],
)
async def get_variant_stock(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VariantStockListResponse:
    """Per-warehouse breakdown for a single variant, every warehouse included.

    Deliberately not filtered by one warehouse: the transfer form needs the
    full list to pick both a source and a destination.
    """
    rows = await warehouse_service.get_stock_by_variant(db, variant_id)
    items = [
        VariantStockRow(
            warehouse_id=row["warehouse_id"],
            name=row["name"],
            code=row["code"],
            is_active=row["is_active"],
            is_registered=row["is_registered"],
            available=row["available"],
            reserved=row["reserved"],
            committed=row["committed"],
            damaged=row["damaged"],
            incoming=row["incoming"],
            low_stock_threshold=row["low_stock_threshold"],
        )
        for row in rows
    ]
    return VariantStockListResponse(
        variant_id=variant_id,
        items=items,
        total_available=sum(item.available for item in items),
        total_on_hand=sum(
            item.available + item.reserved + item.committed + item.damaged for item in items
        ),
    )
