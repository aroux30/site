"""Authentication Pydantic v2 schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from app.modules.auth.application.application_password_service import (
    DEFAULT_VALIDITY_DAYS as DEFAULT_APP_PASSWORD_VALIDITY_DAYS,
)

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
    # Optional. When supplied, a verification link is emailed and
    # ``users.is_verified`` stays false until it is clicked — the OTP flow
    # proves the phone, never the email, so an address typed here was
    # previously trusted without ever being checked.
    email: str | None = Field(
        None,
        max_length=255,
        description="Optional email; a verification link is sent when provided.",
    )
    referral_code: str | None = Field(
        None, max_length=50, description="Optional referral code from an invite link"
    )
    honeypot: str | None = Field(None, description="Anti-bot honeypot field. Must be empty.")

    @field_validator("honeypot")
    @classmethod
    def validate_honeypot(cls, v: str | None) -> str | None:
        if v:
            raise ValueError("Automated bot traffic detected")
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_iran_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        # Same shape check the profile update uses: a value with no "@" or no
        # dot after it is not an address, and accepting it would send a
        # verification link into the void.
        if v is None:
            return None
        candidate = v.strip()
        if not candidate:
            return None
        if "@" not in candidate or "." not in candidate.split("@")[-1]:
            raise ValueError("Invalid email format")
        return candidate

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
            raise ValueError(
                "این رمز عبور بسیار رایج و ناامن است. لطفاً از رمز عبور قوی‌تری استفاده کنید."
            )
        return v


class LoginRequest(BaseModel):
    """Login with phone + password."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=10, max_length=20, examples=["09123456789"])
    password: str = Field(..., min_length=1, max_length=128)
    totp_code: str | None = Field(
        None,
        min_length=6,
        max_length=8,
        description="TOTP second factor; required when the user has MFA enabled",
    )
    # "مرا به خاطر بسپار": opts *this* session into the longer refresh lifetime.
    # Per-session, not per-account, so a shared machine's "no" is not undone by
    # another device's "yes".
    remember_me: bool = Field(
        False,
        description="Keep this session signed in for the longer remember-me window.",
    )
    honeypot: str | None = Field(None, description="Anti-bot honeypot field. Must be empty.")

    @field_validator("honeypot")
    @classmethod
    def validate_honeypot(cls, v: str | None) -> str | None:
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

    refresh_token: str | None = Field(None, min_length=1)


def _validate_strong_password(v: str) -> str:
    """Shared password policy for every endpoint that sets one."""
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("Password must contain at least one letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    if is_weak_password(v):
        raise ValueError(
            "این رمز عبور بسیار رایج و ناامن است. لطفاً از رمز عبور قوی‌تری استفاده کنید."
        )
    return v


class ChangePasswordRequest(BaseModel):
    """Change the current user's password."""

    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_strong_password(v)


class PasswordResetRequest(BaseModel):
    """Ask for a reset link. The email must be an existing password account."""

    email: str = Field(..., min_length=3, max_length=255)


class PasswordResetConfirm(BaseModel):
    """Redeem a reset token and set a new password."""

    token: str = Field(..., min_length=10, max_length=512)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_strong_password(v)


# ── Response schemas ─────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """JWT token pair response. access_token is optional to support cookie-only auth."""

    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserProfileResponse(BaseModel):
    """Full user profile response including profile details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    #: The public-facing name, when set. Consumers fall back to first+last.
    display_name: str | None = None
    national_code: str | None = None
    birth_date: str | None = None
    avatar_url: str | None = None
    gender: str | None = None
    is_active: bool
    is_verified: bool
    is_superuser: bool = False
    roles: list[str] = []
    created_at: datetime

    @field_validator("national_code")
    @classmethod
    def mask_national_code_field(cls, v: str | None) -> str | None:
        if v:
            from app.core.security.data_protection import mask_national_code
            return mask_national_code(v)
        return v


class UserProfileUpdate(BaseModel):
    """Fields a user can update on their own profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    # The name shown publicly. Distinct from first/last on purpose: an author
    # under a pen name must not have their legal name published by a byline.
    display_name: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=255)
    national_code: str | None = Field(None, min_length=10, max_length=10)
    birth_date: str | None = Field(None, examples=["1370-01-15"])
    avatar_url: str | None = Field(None, max_length=500)
    gender: str | None = Field(None, max_length=10)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is not None and ("@" not in v or "." not in v.split("@")[-1]):
            raise ValueError("Invalid email format")
        return v

    @field_validator("national_code")
    @classmethod
    def validate_national_code(cls, v: str | None) -> str | None:
        if v is not None:
            from app.modules.users.application.validation_utils import (
                normalise_digits,
            )
            from app.modules.users.application.validation_utils import (
                validate_national_code as check_national_code,
            )

            clean = re.sub(r"\D", "", normalise_digits(v)).strip()
            if not check_national_code(clean):
                raise ValueError("کد ملی وارد شده معتبر نیست (کنترل رقم چک Modulo-11)")
            return clean
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


# ── Application passwords (WordPress parity) ───────────────────────────────


class ApplicationPasswordCreate(BaseModel):
    """Mint a credential for a personal API client."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Label shown in the revocation list, e.g. 'گوشی من'",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Allowed scopes; empty means full access (WordPress's default)",
    )
    expires_in_days: int | None = Field(
        DEFAULT_APP_PASSWORD_VALIDITY_DAYS,
        ge=1,
        le=3650,
        description="Lifetime in days; null = never expires",
    )


class ApplicationPasswordResponse(BaseModel):
    """A credential as listed for the user. Never carries the secret."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    scopes: list[str] = Field(default_factory=list)
    is_active: bool
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None


class ApplicationPasswordCreatedResponse(ApplicationPasswordResponse):
    """Returned once, at creation, with the plaintext attached.

    The only time the secret is ever available: the database stores a hash, so
    a forgotten token must be revoked and re-minted rather than looked up.
    """

    token: str = Field(..., description="Shown once — copy it now")
