"""Pydantic v2 schemas for the Multi-Vendor / Marketplace module."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Vendor Schemas ─────────────────────────────────────────────────────────


class VendorRegisterRequest(BaseModel):
    """Schema for a registered user applying as a marketplace vendor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str = Field(..., min_length=2, max_length=200, examples=["فروشگاه پارس"])
    slug: str | None = Field(None, min_length=2, max_length=250, examples=["pars-store"])
    logo_url: str | None = Field(None, max_length=500)
    banner_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=5000)
    national_id: str | None = Field(None, min_length=10, max_length=20, examples=["0012345678"])
    iban_number: str | None = Field(None, max_length=50, examples=["IR120120000000001234567890"])
    contact_phone: str | None = Field(None, max_length=30, examples=["09121234567"])

    @field_validator("iban_number")
    @classmethod
    def validate_iban(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.replace(" ", "").upper()
        if not cleaned.startswith("IR"):
            cleaned = f"IR{cleaned}"
        if not re.match(r"^IR\d{24}$", cleaned):
            raise ValueError("Iranian IBAN must start with IR followed by 24 digits")
        return cleaned

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not re.match(r"^\d{10,14}$", cleaned):
            raise ValueError("National ID must be between 10 and 14 digits")
        return cleaned


class VendorUpdateRequest(BaseModel):
    """Schema for a vendor updating their storefront profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str | None = Field(None, min_length=2, max_length=200)
    logo_url: str | None = Field(None, max_length=500)
    banner_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=5000)
    national_id: str | None = Field(None, min_length=10, max_length=20)
    iban_number: str | None = Field(None, max_length=50)
    contact_phone: str | None = Field(None, max_length=30)

    @field_validator("iban_number")
    @classmethod
    def validate_iban(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.replace(" ", "").upper()
        if not cleaned.startswith("IR"):
            cleaned = f"IR{cleaned}"
        if not re.match(r"^IR\d{24}$", cleaned):
            raise ValueError("Iranian IBAN must start with IR followed by 24 digits")
        return cleaned

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not re.match(r"^\d{10,14}$", cleaned):
            raise ValueError("National ID must be between 10 and 14 digits")
        return cleaned


class VendorAdminUpdateRequest(BaseModel):
    """Schema for platform administrator modifying vendor attributes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str | None = Field(None, min_length=2, max_length=200)
    logo_url: str | None = Field(None, max_length=500)
    banner_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=5000)
    commission_rate: int | None = Field(
        None, ge=0, le=10000, description="Basis points (1000 = 10%)"
    )
    is_verified: bool | None = None
    is_active: bool | None = None
    national_id: str | None = Field(None, min_length=10, max_length=20)
    iban_number: str | None = Field(None, max_length=50)
    contact_phone: str | None = Field(None, max_length=30)
    rating: float | None = Field(None, ge=0.0, le=5.0)


class VendorVerifyRequest(BaseModel):
    """Admin verification request payload."""

    verified: bool = Field(True, description="Approval or rejection of vendor verification")


class VendorResponse(BaseModel):
    """Full vendor profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    store_name: str
    slug: str
    logo_url: str | None = None
    banner_url: str | None = None
    description: str | None = None
    commission_rate: int = 1000
    is_verified: bool = False
    is_active: bool = True
    national_id: str | None = None
    iban_number: str | None = None
    contact_phone: str | None = None
    rating: float = 5.0
    total_sales_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VendorListResponse(BaseModel):
    """Paginated list of vendors."""

    model_config = ConfigDict(from_attributes=True)

    items: list[VendorResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


# ── Settlement Schemas ─────────────────────────────────────────────────────


class VendorSettlementCreate(BaseModel):
    """Schema for generating a settlement / payout for a vendor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: int = Field(..., ge=1, description="Payout amount in Rials")
    period_start: datetime | None = Field(None, description="Start date of the settlement cycle")
    period_end: datetime | None = Field(None, description="End date of the settlement cycle")
    payment_reference: str | None = Field(
        None, max_length=100, description="Bank tracking code / Paya reference"
    )


class VendorSettlementResponse(BaseModel):
    """Vendor settlement details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    amount: int
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: str
    payment_reference: str | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VendorSettlementListResponse(BaseModel):
    """Paginated list of settlements."""

    model_config = ConfigDict(from_attributes=True)

    items: list[VendorSettlementResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


# ── Earnings Schemas ───────────────────────────────────────────────────────


class VendorEarningsResponse(BaseModel):
    """Financial breakdown and settlement status for a vendor."""

    model_config = ConfigDict(from_attributes=True)

    vendor_id: uuid.UUID
    store_name: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    total_sales: int = Field(ge=0, description="Gross sales in Rials")
    total_orders: int = Field(ge=0, description="Total order count")
    total_items: int = Field(ge=0, description="Total items sold")
    commission_rate: int = Field(ge=0, description="Commission basis points")
    commission_amount: int = Field(ge=0, description="Platform commission taken in Rials")
    net_earnings: int = Field(
        ge=0, description="Net earnings due to vendor (gross - commission) in Rials"
    )
    settled_amount: int = Field(ge=0, description="Total already settled and paid in Rials")
    pending_settlement: int = Field(ge=0, description="Unsettled payable balance in Rials")
