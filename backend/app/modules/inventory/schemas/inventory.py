"""Pydantic v2 schemas for the inventory module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventory.domain.models import ReservationStatus, TransactionType


# ── Inventory ──────────────────────────────────────────────────────────────


class InventoryResponse(BaseModel):
    """Public representation of inventory levels for a variant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    available: int = Field(description="Quantity available for sale")
    reserved: int = Field(description="Quantity held by active reservations")
    committed: int = Field(description="Quantity committed to confirmed orders")
    damaged: int = Field(description="Quantity marked as damaged / unsellable")
    incoming: int = Field(description="Quantity expected from suppliers")
    low_stock_threshold: int
    backorder_allowed: bool
    track_inventory: bool
    created_at: datetime
    updated_at: datetime

    @property
    def total_on_hand(self) -> int:
        return self.available + self.reserved + self.committed

    @property
    def is_low_stock(self) -> bool:
        return self.available <= self.low_stock_threshold

    @property
    def available_toman(self) -> str:
        """Human-readable display — not stored; computed on read."""
        return f"{self.available:,}"


class InventoryAdjustRequest(BaseModel):
    """Admin request to manually adjust stock levels."""

    quantity: int = Field(..., description="Positive to add, negative to remove")
    type: TransactionType = Field(
        ..., description="Reason for adjustment (received, damaged, adjusted, etc.)"
    )
    reference_type: Optional[str] = Field(
        None,
        max_length=50,
        description="External reference category (e.g. 'purchase_order', 'return')",
    )
    reference_id: Optional[uuid.UUID] = Field(
        None, description="External reference identifier"
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Free-text note")


# ── Transactions ───────────────────────────────────────────────────────────


class InventoryTransactionResponse(BaseModel):
    """A single inventory movement record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity: int
    type: TransactionType
    reference_type: Optional[str] = None
    reference_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_at: datetime


# ── Reservations ───────────────────────────────────────────────────────────


class ReservationResponse(BaseModel):
    """Representation of an inventory reservation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    order_id: Optional[uuid.UUID] = None
    cart_id: Optional[uuid.UUID] = None
    quantity: int
    expires_at: datetime
    status: ReservationStatus
    created_at: datetime


# ── Low-stock alert ────────────────────────────────────────────────────────


class LowStockAlert(BaseModel):
    """Alert payload for variants whose available stock is at or below threshold."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    available: int
    low_stock_threshold: int
    reserved: int
    committed: int


# ── List / pagination helpers ──────────────────────────────────────────────


class InventoryListResponse(BaseModel):
    items: list[InventoryResponse]
    total: int
    page: int
    page_size: int


class TransactionListResponse(BaseModel):
    items: list[InventoryTransactionResponse]
    total: int
    page: int
    page_size: int
