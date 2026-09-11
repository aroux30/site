"""User-related Pydantic v2 schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Address schemas ──────────────────────────────────────────────────────────


class AddressCreate(BaseModel):
    """Create a new delivery address."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=100, examples=["خانه"])
    province: str = Field(..., min_length=1, max_length=100, examples=["تهران"])
    city: str = Field(..., min_length=1, max_length=100, examples=["تهران"])
    district: str | None = Field(None, max_length=100)
    postal_code: str = Field(..., min_length=10, max_length=10, examples=["1234567890"])
    full_address: str = Field(..., min_length=5, max_length=1000)
    lat: float | None = Field(None, ge=25.0, le=40.0, description="Latitude (Iran range)")
    lng: float | None = Field(None, ge=44.0, le=64.0, description="Longitude (Iran range)")
    is_default: bool = False

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        if not re.match(r"^\d{10}$", v):
            raise ValueError("Postal code must be exactly 10 digits")
        return v


class AddressUpdate(BaseModel):
    """Update an existing delivery address."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=100)
    province: str | None = Field(None, min_length=1, max_length=100)
    city: str | None = Field(None, min_length=1, max_length=100)
    district: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, min_length=10, max_length=10)
    full_address: str | None = Field(None, min_length=5, max_length=1000)
    lat: float | None = Field(None, ge=25.0, le=40.0)
    lng: float | None = Field(None, ge=44.0, le=64.0)
    is_default: bool | None = None

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\d{10}$", v):
            raise ValueError("Postal code must be exactly 10 digits")
        return v


class AddressResponse(BaseModel):
    """Delivery address response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    province: str
    city: str
    district: str | None = None
    postal_code: str
    full_address: str
    lat: float | None = None
    lng: float | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ── User schemas ─────────────────────────────────────────────────────────────


class UserListItem(BaseModel):
    """Compact user representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: datetime | None = None


class UserListResponse(BaseModel):
    """Paginated list of users (admin view)."""

    items: list[UserListItem]
    total: int
    page: int
    page_size: int
    pages: int


class UserDetailResponse(BaseModel):
    """Detailed user information for admin view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    national_code: str | None = None
    birth_date: str | None = None
    avatar_url: str | None = None
    gender: str | None = None
    is_active: bool
    is_verified: bool
    is_superuser: bool
    last_login: datetime | None = None
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    """Fields an admin can update on any user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str | None = Field(None, max_length=255)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None
    is_verified: bool | None = None


class UserSessionResponse(BaseModel):
    """User session information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    device_info: str | None = None
    created_at: datetime
    expires_at: datetime
    is_revoked: bool
