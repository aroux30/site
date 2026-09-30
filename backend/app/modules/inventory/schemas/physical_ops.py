"""Pydantic contracts for inventory physical operations v1."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.inventory.domain.models import (
    ReceiptStatus,
    StockCountScope,
    StockCountStatus,
    TransferStatus,
)


class PhysicalOperationLineRequest(BaseModel):
    """A positive integer SKU quantity for receipts and transfers."""

    product_variant_id: uuid.UUID
    quantity: int = Field(..., gt=0)


class StockCountCreateRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None
    scope: StockCountScope = StockCountScope.FULL
    scope_filter: dict[str, Any] | None = None


class StockCountLineEntryRequest(BaseModel):
    product_variant_id: uuid.UUID
    counted_qty: int = Field(..., ge=0)
    note: str | None = Field(None, max_length=2000)


class StockCountLinesEntryRequest(BaseModel):
    lines: list[StockCountLineEntryRequest] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_variants(self) -> "StockCountLinesEntryRequest":
        ids = [line.product_variant_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product variant may occur only once")
        return self


class StockCountLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    product_variant_id: uuid.UUID
    system_qty: int
    counted_qty: int | None = None
    variance: int | None = None
    note: str | None = None

    @classmethod
    def from_line(cls, line: Any) -> "StockCountLineResponse":
        return cls(
            id=line.id,
            product_variant_id=line.product_variant_id,
            system_qty=line.system_qty,
            counted_qty=line.counted_qty,
            variance=None if line.counted_qty is None else line.counted_qty - line.system_qty,
            note=line.note,
        )


class StockCountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    status: StockCountStatus
    scope: StockCountScope
    scope_filter: dict[str, Any]
    started_at: datetime | None = None
    posted_at: datetime | None = None
    created_by: uuid.UUID | None = None
    line_count: int
    counted_line_count: int
    variance_line_count: int
    variance_quantity: int
    created_at: datetime
    updated_at: datetime
    lines: list[StockCountLineResponse] = []

    @classmethod
    def from_count(cls, count: Any) -> "StockCountResponse":
        return cls(
            id=count.id,
            warehouse_id=count.warehouse_id,
            status=count.status,
            scope=count.scope,
            scope_filter=count.scope_filter or {},
            started_at=count.started_at,
            posted_at=count.posted_at,
            created_by=count.created_by,
            line_count=count.line_count,
            counted_line_count=count.counted_line_count,
            variance_line_count=count.variance_line_count,
            variance_quantity=count.variance_quantity,
            created_at=count.created_at,
            updated_at=count.updated_at,
            lines=[StockCountLineResponse.from_line(line) for line in getattr(count, "lines", [])],
        )


class StockCountListResponse(BaseModel):
    items: list[StockCountResponse]
    total: int
    page: int
    page_size: int


class TransferCreateRequest(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    lines: list[PhysicalOperationLineRequest] = Field(..., min_length=1)
    notes: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _validate_pair_and_lines(self) -> "TransferCreateRequest":
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("Source and destination warehouses must differ")
        ids = [line.product_variant_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product variant may occur only once")
        return self


class TransferLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    product_variant_id: uuid.UUID
    quantity: int


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    status: TransferStatus
    notes: str | None = None
    idempotency_key: str | None = None
    shipped_at: datetime | None = None
    received_at: datetime | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[TransferLineResponse] = []

    @classmethod
    def from_transfer(cls, transfer: Any) -> "TransferResponse":
        return cls(
            id=transfer.id,
            from_warehouse_id=transfer.from_warehouse_id,
            to_warehouse_id=transfer.to_warehouse_id,
            status=transfer.status,
            notes=transfer.notes,
            idempotency_key=transfer.idempotency_key,
            shipped_at=transfer.shipped_at,
            received_at=transfer.received_at,
            created_by=transfer.created_by,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at,
            lines=[TransferLineResponse.model_validate(line) for line in getattr(transfer, "lines", [])],
        )


class TransferListResponse(BaseModel):
    items: list[TransferResponse]
    total: int
    page: int
    page_size: int


class ReceiptCreateRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None
    lines: list[PhysicalOperationLineRequest] = Field(..., min_length=1)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("lines")
    @classmethod
    def _reject_duplicate_variants(
        cls, lines: list[PhysicalOperationLineRequest]
    ) -> list[PhysicalOperationLineRequest]:
        ids = [line.product_variant_id for line in lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product variant may occur only once")
        return lines


class ReceiptLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    product_variant_id: uuid.UUID
    quantity: int


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    status: ReceiptStatus
    notes: str | None = None
    received_at: datetime | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[ReceiptLineResponse] = []

    @classmethod
    def from_receipt(cls, receipt: Any) -> "ReceiptResponse":
        return cls(
            id=receipt.id,
            warehouse_id=receipt.warehouse_id,
            status=receipt.status,
            notes=receipt.notes,
            received_at=receipt.received_at,
            created_by=receipt.created_by,
            created_at=receipt.created_at,
            updated_at=receipt.updated_at,
            lines=[ReceiptLineResponse.model_validate(line) for line in getattr(receipt, "lines", [])],
        )


class ReceiptListResponse(BaseModel):
    items: list[ReceiptResponse]
    total: int
    page: int
    page_size: int
