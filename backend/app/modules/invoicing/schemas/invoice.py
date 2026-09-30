"""Pydantic schemas for the invoicing admin & customer APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    product_name: str
    sku: str | None = None
    quantity: int
    unit_price: int
    total_price: int


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    type: str
    status: str
    number: str | None = None
    fiscal_period: str | None = None
    issued_at: datetime | None = None
    posted_at: datetime | None = None
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    totals: dict[str, Any]
    customer: dict[str, Any]
    hash: str | None = None
    previous_hash: str | None = None
    credit_for_id: uuid.UUID | None = None
    credit_reason: str | None = None
    has_archive: bool = False
    lines: list[InvoiceLineResponse] = Field(default_factory=list)
    created_at: datetime | None = None

    @classmethod
    def from_invoice(cls, inv: Any) -> "InvoiceResponse":
        return cls(
            id=inv.id,
            order_id=inv.order_id,
            type=inv.type.value if hasattr(inv.type, "value") else str(inv.type),
            status=inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            number=inv.number,
            fiscal_period=inv.fiscal_period,
            issued_at=inv.issued_at,
            posted_at=inv.posted_at,
            paid_at=inv.paid_at,
            cancelled_at=inv.cancelled_at,
            cancel_reason=inv.cancel_reason,
            totals=inv.totals or {},
            customer=inv.customer or {},
            hash=inv.hash,
            previous_hash=inv.previous_hash,
            credit_for_id=inv.credit_for_id,
            credit_reason=inv.credit_reason,
            has_archive=bool(getattr(inv, "archive_path", None)),
            lines=[InvoiceLineResponse.model_validate(ln) for ln in (inv.lines or [])],
            created_at=inv.created_at,
        )


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class CancelInvoiceRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ChainBrokenLink(BaseModel):
    invoice_id: str
    number: str | None = None
    fiscal_period: str | None = None
    type: str
    previous_hash_ok: bool
    own_hash_ok: bool


class ChainVerificationResponse(BaseModel):
    valid: bool
    documents_checked: int
    first_broken: ChainBrokenLink | None = None
