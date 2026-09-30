"""Pydantic contracts for procurement v1 (suppliers + purchase orders)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.procurement.domain.models import PurchaseOrderStatus


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    contact_info: dict[str, Any] = {}
    payment_terms_days: int = Field(0, ge=0)
    is_active: bool = True


class SupplierUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, min_length=1, max_length=50)
    contact_info: dict[str, Any] | None = None
    payment_terms_days: int | None = Field(None, ge=0)
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    contact_info: dict[str, Any]
    payment_terms_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
    page: int
    page_size: int


class SupplierPreferredSetRequest(BaseModel):
    variant_id: uuid.UUID
    supplier_sku: str | None = Field(None, max_length=100)
    last_unit_price_rial: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


class PurchaseOrderLineRequest(BaseModel):
    product_variant_id: uuid.UUID
    qty_ordered: int = Field(..., gt=0)
    unit_price_rial: int = Field(..., ge=0)
    tax_basis_points: int = Field(0, ge=0, le=10000)
    note: str | None = Field(None, max_length=500)


class PurchaseOrderCreateRequest(BaseModel):
    supplier_id: uuid.UUID
    lines: list[PurchaseOrderLineRequest] = Field(..., min_length=1)
    expected_at: datetime | None = None
    notes: str | None = Field(None, max_length=4000)
    warehouse_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _reject_duplicate_variants(self) -> "PurchaseOrderCreateRequest":
        ids = [line.product_variant_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product variant may occur only once")
        return self


class PurchaseOrderUpdateRequest(BaseModel):
    expected_at: datetime | None = None
    notes: str | None = Field(None, max_length=4000)
    warehouse_id: uuid.UUID | None = None
    lines: list[PurchaseOrderLineRequest] | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_variants(self) -> "PurchaseOrderUpdateRequest":
        if self.lines is not None:
            ids = [line.product_variant_id for line in self.lines]
            if len(ids) != len(set(ids)):
                raise ValueError("Each product variant may occur only once")
        return self


class PurchaseOrderReceiveLineRequest(BaseModel):
    line_id: uuid.UUID
    quantity: int = Field(..., gt=0)


class PurchaseOrderReceiveRequest(BaseModel):
    lines: list[PurchaseOrderReceiveLineRequest] = Field(..., min_length=1)
    notes: str | None = Field(None, max_length=4000)


class PurchaseOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_variant_id: uuid.UUID
    position: int
    qty_ordered: int
    qty_received: int
    qty_outstanding: int
    unit_price_rial: int
    tax_basis_points: int
    line_total_rial: int
    note: str | None

    @classmethod
    def from_line(cls, line: Any) -> "PurchaseOrderLineResponse":
        return cls(
            id=line.id,
            product_variant_id=line.product_variant_id,
            position=line.position,
            qty_ordered=line.qty_ordered,
            qty_received=line.qty_received,
            qty_outstanding=max(line.qty_ordered - line.qty_received, 0),
            unit_price_rial=line.unit_price_rial,
            tax_basis_points=line.tax_basis_points,
            line_total_rial=line.qty_ordered * line.unit_price_rial,
            note=line.note,
        )


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    supplier_code: str | None = None
    number: str | None
    status: PurchaseOrderStatus
    warehouse_id: uuid.UUID | None
    expected_at: datetime | None
    notes: str | None
    sent_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    subtotal_rial: int
    tax_rial: int
    total_rial: int
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineResponse] = []
    receipt_ids: list[uuid.UUID] = []

    @classmethod
    def from_po(
        cls, po: Any, *, receipt_ids: list[uuid.UUID] | None = None
    ) -> "PurchaseOrderResponse":
        supplier = getattr(po, "supplier", None)
        return cls(
            id=po.id,
            supplier_id=po.supplier_id,
            supplier_name=getattr(supplier, "name", None),
            supplier_code=getattr(supplier, "code", None),
            number=po.number,
            status=po.status,
            warehouse_id=po.warehouse_id,
            expected_at=po.expected_at,
            notes=po.notes,
            sent_at=po.sent_at,
            closed_at=po.closed_at,
            cancelled_at=po.cancelled_at,
            subtotal_rial=po.subtotal_rial,
            tax_rial=po.tax_rial,
            total_rial=po.total_rial,
            created_by=po.created_by,
            created_at=po.created_at,
            updated_at=po.updated_at,
            lines=[PurchaseOrderLineResponse.from_line(line) for line in getattr(po, "lines", [])],
            receipt_ids=receipt_ids or [],
        )


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Suggest endpoint
# ---------------------------------------------------------------------------


class SuggestedPOLine(BaseModel):
    variant_id: uuid.UUID
    warehouse_id: uuid.UUID
    available: int
    min_quantity: int
    suggested_qty: int
    unit_price_rial: int


class SuggestedPOGroup(BaseModel):
    supplier_id: uuid.UUID | None
    supplier_name: str | None = None
    lines: list[SuggestedPOLine]


class SuggestPOResponse(BaseModel):
    groups: list[SuggestedPOGroup]


class CreateSuggestedPORequest(BaseModel):
    supplier_id: uuid.UUID
    variant_ids: list[uuid.UUID] | None = None
    notes: str | None = Field(None, max_length=4000)
    idempotency_key: str | None = Field(None, max_length=255)
