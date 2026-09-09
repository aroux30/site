"""User-related Pydantic v2 schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Address schemas ──────────────────────────────────────────────────────────


class AddressCreate(BaseModel):
    """Create a new delivery address."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=100, examples=["خانه"])
    province: str = Field(..., min_length=1, max_length=100, examples=["تهران"])
    city: str = Field(..., min_length=1, max_length=100, examples=["تهران"])
    district: Optional[str] = Field(None, max_length=100)
    postal_code: str = Field(..., min_length=10, max_length=10, examples=["1234567890"])
    full_address: str = Field(..., min_length=5, max_length=1000)
    lat: Optional[float] = Field(None, ge=25.0, le=40.0, description="Latitude (Iran range)")
    lng: Optional[float] = Field(None, ge=44.0, le=64.0, description="Longitude (Iran range)")
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

    title: Optional[str] = Field(None, min_length=1, max_length=100)
    province: Optional[str] = Field(None, min_length=1, max_length=100)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, min_length=10, max_length=10)
    full_address: Optional[str] = Field(None, min_length=5, max_length=1000)
    lat: Optional[float] = Field(None, ge=25.0, le=40.0)
    lng: Optional[float] = Field(None, ge=44.0, le=64.0)
    is_default: Optional[bool] = None

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: Optional[str]) -> Optional[str]:
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
    district: Optional[str] = None
    postal_code: str
    full_address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ── User schemas ─────────────────────────────────────────────────────────────


class UserListItem(BaseModel):
    """Compact user representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


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
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_code: Optional[str] = None
    birth_date: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    is_active: bool
    is_verified: bool
    is_superuser: bool
    last_login: Optional[datetime] = None
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    """Fields an admin can update on any user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: Optional[str] = Field(None, max_length=255)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserSessionResponse(BaseModel):
    """User session information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    is_revoked: bool
