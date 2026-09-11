"""Authentication Pydantic v2 schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security.password import is_weak_password

# ── Iranian phone regex ─────────────────────────────────────────────────────
_IRAN_PHONE_RE = re.compile(r"^09\d{9}$")


def _validate_iran_phone(v: str) -> str:
    """Validate and normalise an Iranian mobile number (09xxxxxxxxx)."""
    if not isinstance(v, str):
        raise ValueError("Phone must be a string")
    # Strip hidden bidi marks, whitespace, hyphens, dots, parentheses
    cleaned = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E\s\-\(\)\.]+", "", v).strip()
    # Convert Persian/Arabic digits to English digits
    persian_arabic = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    cleaned = cleaned.translate(persian_arabic)
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if cleaned.startswith("0098"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("98") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]
    elif cleaned.startswith("9") and len(cleaned) == 10:
        cleaned = "0" + cleaned
    if not _IRAN_PHONE_RE.match(cleaned):
        raise ValueError("Phone must be a valid Iranian mobile number (09xxxxxxxxx)")
    return cleaned


# ── Request schemas ──────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Register a new user with phone + password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=10, max_length=20, examples=["09123456789"])
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    honeypot: Optional[str] = Field(None, description="Anti-bot honeypot field. Must be empty.")

    @field_validator("honeypot")
    @classmethod
    def validate_honeypot(cls, v: Optional[str]) -> Optional[str]:
        if v:
            raise ValueError("Automated bot traffic detected")
        return v

    @field_validator("phone", mode="before")
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
        if is_weak_password(v):
            raise ValueError("این رمز عبور بسیار رایج و ناامن است. لطفاً از رمز عبور قوی‌تری استفاده کنید.")
        return v


class LoginRequest(BaseModel):
    """Login with phone + password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=10, max_length=20, examples=["09123456789"])
    password: str = Field(..., min_length=1, max_length=128)
    honeypot: Optional[str] = Field(None, description="Anti-bot honeypot field. Must be empty.")

    @field_validator("honeypot")
    @classmethod
    def validate_honeypot(cls, v: Optional[str]) -> Optional[str]:
        if v:
            raise ValueError("Automated bot traffic detected")
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)


class OTPRequestSchema(BaseModel):
    """Request a one-time password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=10, max_length=20, examples=["09123456789"])

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)


class OTPVerifySchema(BaseModel):
    """Verify an OTP code."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=10, max_length=20, examples=["09123456789"])
    code: str = Field(..., min_length=4, max_length=10, examples=["123456"])

    @field_validator("phone", mode="before")
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
        if is_weak_password(v):
            raise ValueError("این رمز عبور بسیار رایج و ناامن است. لطفاً از رمز عبور قوی‌تری استفاده کنید.")
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
    is_superuser: bool = False
    roles: list[str] = []
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


class MFASetupResponse(BaseModel):
    """Response returned when initiating TOTP MFA enrollment."""

    secret: str
    otpauth_uri: str
    backup_codes: list[str]


class MFAVerifyRequest(BaseModel):
    """Payload to verify TOTP code."""

    code: str = Field(..., min_length=6, max_length=8)


class MFADisableRequest(BaseModel):
    """Payload to disable MFA requires both password and current TOTP code."""

    code: str = Field(..., min_length=6, max_length=8)
    password: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
