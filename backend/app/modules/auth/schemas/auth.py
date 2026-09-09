"""Authentication Pydantic v2 schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Iranian phone regex ─────────────────────────────────────────────────────
_IRAN_PHONE_RE = re.compile(r"^09\d{9}$")


def _validate_iran_phone(v: str) -> str:
    """Validate and normalise an Iranian mobile number (09xxxxxxxxx)."""
    v = v.strip()
    if not _IRAN_PHONE_RE.match(v):
        raise ValueError("Phone must be a valid Iranian mobile number (09xxxxxxxxx)")
    return v


# ── Request schemas ──────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Register a new user with phone + password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=11, max_length=11, examples=["09123456789"])
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Login with phone + password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=11, max_length=11, examples=["09123456789"])
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)


class OTPRequestSchema(BaseModel):
    """Request a one-time password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=11, max_length=11, examples=["09123456789"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)


class OTPVerifySchema(BaseModel):
    """Verify an OTP code."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=11, max_length=11, examples=["09123456789"])
    code: str = Field(..., min_length=4, max_length=10, examples=["123456"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)


class RefreshTokenRequest(BaseModel):
    """Refresh an access token using a refresh token.

    The ``refresh_token`` field is optional because browser clients send
    the token via an HttpOnly cookie instead of the request body.
    """

    refresh_token: Optional[str] = Field(None, min_length=1)


class ChangePasswordRequest(BaseModel):
    """Change the current user's password."""

    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


# ── Response schemas ─────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserProfileResponse(BaseModel):
    """Full user profile response including profile details."""

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
    created_at: datetime


class UserProfileUpdate(BaseModel):
    """Fields a user can update on their own profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    national_code: Optional[str] = Field(None, min_length=10, max_length=10)
    birth_date: Optional[str] = Field(None, examples=["1370-01-15"])
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[str] = Field(None, max_length=10)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if "@" not in v or "." not in v.split("@")[-1]:
                raise ValueError("Invalid email format")
        return v

    @field_validator("national_code")
    @classmethod
    def validate_national_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not re.match(r"^\d{10}$", v):
                raise ValueError("National code must be exactly 10 digits")
        return v


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
