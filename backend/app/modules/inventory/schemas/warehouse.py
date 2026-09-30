"""Pydantic contracts for the warehouse catalogue (multi-warehouse v1).

All quantities are integers — the inventory ledger stores whole units and the
platform's integer-money rule has a quantity twin: nothing here rounds.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WarehouseCreateRequest(BaseModel):
    """Create a stocking location. ``is_default`` promotes it immediately."""

    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=50)
    address: str | None = Field(None, max_length=2000)
    is_default: bool = False


class WarehouseUpdateRequest(BaseModel):
    """Partial edit. Omitted fields are left untouched."""

    name: str | None = Field(None, min_length=1, max_length=150)
    code: str | None = Field(None, min_length=1, max_length=50)
    address: str | None = Field(None, max_length=2000)
    # Promotion only: sending ``false`` for the current default is refused, so
    # the catalogue can never end up with zero defaults.
    is_default: bool | None = None


class WarehouseStockSummary(BaseModel):
    """Aggregated stock for one warehouse (integers only)."""

    variant_count: int = 0
    available: int = 0
    reserved: int = 0
    committed: int = 0
    damaged: int = 0
    incoming: int = 0
    total_on_hand: int = 0

    @classmethod
    def from_buckets(
        cls,
        *,
        variant_count: int = 0,
        available: int = 0,
        reserved: int = 0,
        committed: int = 0,
        damaged: int = 0,
        incoming: int = 0,
    ) -> WarehouseStockSummary:
        return cls(
            variant_count=int(variant_count),
            available=int(available),
            reserved=int(reserved),
            committed=int(committed),
            damaged=int(damaged),
            incoming=int(incoming),
            # Physical units on hand: sellable + held + sold-awaiting-shipment
            # + unsellable. ``incoming`` is deliberately excluded — it has not
            # physically arrived yet.
            total_on_hand=int(available) + int(reserved) + int(committed) + int(damaged),
        )


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    address: str | None = None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stock: WarehouseStockSummary | None = None

    @classmethod
    def from_warehouse(
        cls, warehouse: Any, *, stock: WarehouseStockSummary | None = None
    ) -> WarehouseResponse:
        return cls(
            id=warehouse.id,
            name=warehouse.name,
            code=warehouse.code,
            address=warehouse.address,
            is_default=bool(warehouse.is_default),
            is_active=bool(warehouse.is_active),
            created_at=warehouse.created_at,
            updated_at=warehouse.updated_at,
            stock=stock,
        )


class WarehouseListResponse(BaseModel):
    items: list[WarehouseResponse]
    total: int


class WarehouseStockRow(BaseModel):
    """Stock held in one warehouse, aggregated across its SKUs.

    ``is_registered`` is false for warehouse ids that carry stock but have no
    catalogue row (ids minted before the warehouses table existed, or by a
    direct ledger write). Such rows are surfaced rather than hidden: dropping
    them would make the totals on this screen disagree with the ledger.
    """

    warehouse_id: uuid.UUID
    name: str
    code: str
    is_default: bool
    is_active: bool
    is_registered: bool
    stock: WarehouseStockSummary


class WarehouseStockListResponse(BaseModel):
    items: list[WarehouseStockRow]
    total: int
    totals: WarehouseStockSummary


class VariantStockRow(BaseModel):
    """One variant's quantities inside a single warehouse."""

    warehouse_id: uuid.UUID
    name: str
    code: str
    is_active: bool
    is_registered: bool
    available: int
    reserved: int
    committed: int
    damaged: int
    incoming: int
    low_stock_threshold: int


class VariantStockListResponse(BaseModel):
    variant_id: uuid.UUID
    items: list[VariantStockRow]
    total_available: int
    total_on_hand: int
