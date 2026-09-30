"""Pydantic v2 schemas for the tax engine v1 admin API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Rules ────────────────────────────────────────────────────────────────────


class TaxRuleCreate(BaseModel):
    """Create a new effective-dated tax rule (versioning by insertion)."""

    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)
    rule_type: str = Field(description="vat | exempt | compound | withholding")
    scope: str = Field("default", description="default | category | product")
    category_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    rate_basis_points: int = Field(0, ge=0, le=10_000, description="900 = 9.00%")
    is_active: bool = True
    priority: int = 0
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    exempt_reason: str | None = Field(None, description="Recorded on exempt lines")
    description: str | None = None


class TaxRuleUpdate(BaseModel):
    """Partial update — allowed only before the rule becomes effective.

    Effective rules are immutable financial history; the sole permitted change
    is deactivation (is_active=false). Revise live rules by inserting a new
    effective-dated row.
    """

    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, min_length=1, max_length=50)
    rule_type: str | None = None
    scope: str | None = None
    category_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    rate_basis_points: int | None = Field(None, ge=0, le=10_000)
    is_active: bool | None = None
    priority: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    exempt_reason: str | None = None
    description: str | None = None


class TaxRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    rule_type: str
    scope: str
    category_id: uuid.UUID | None
    product_id: uuid.UUID | None
    rate_basis_points: int
    is_active: bool
    priority: int
    effective_from: datetime | None
    effective_to: datetime | None
    exempt_reason: str | None
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class TaxRuleListResponse(BaseModel):
    items: list[TaxRuleResponse]
    total: int


# ── Healthcheck ──────────────────────────────────────────────────────────────


class TaxHealthResponse(BaseModel):
    ok: bool
    has_active_default_rule: bool
    active_rules_count: int
    default_rule_code: str | None
    warnings: list[str] = []


# ── VAT report ───────────────────────────────────────────────────────────────


class TaxReportBucket(BaseModel):
    bucket: str = Field(description="period (YYYY-MM) | rule code | category id")
    order_count: int
    taxable_total_rial: int
    vat_total_rial: int
    withholding_total_rial: int
    tax_total_rial: int


class TaxReportResponse(BaseModel):
    date_from: datetime
    date_to: datetime
    group_by: str
    buckets: list[TaxReportBucket]
    vat_total_rial: int
    withholding_total_rial: int
    tax_total_rial: int
    order_count: int
