"""Pydantic schemas for the settings module."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

#: Key names whose values are credentials and must never be serialized.
#: Matched as whole words against ``_``-separated parts, not as substrings:
#: ``tokens`` (the design-token bag) and ``tokenize`` are not credentials, and a
#: substring match masked an entire theme's colour palette.
_SECRET_KEY_PARTS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secrets",
        "apikey",
        "accesskey",
        "privatekey",
        "token",
        "credential",
        "credentials",
        "merchantid",
        "passphrase",
    }
)

#: Two-part credential keys, matched after splitting on ``_``/``-``:
#: ``api_key`` → ``('api', 'key')``. Without these, splitting alone would miss
#: every two-word credential name.
_SECRET_KEY_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("api", "key"),
        ("api", "secret"),
        ("private", "key"),
        ("access", "key"),
        ("secret", "key"),
        ("merchant", "id"),
        ("client", "secret"),
        ("webhook", "secret"),
        ("signing", "key"),
        ("encryption", "key"),
    }
)

#: What a masked value is replaced with. A fixed marker, not a truncation: a
#: partial secret is still a foothold for guessing the rest.
_MASK = "********"


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    parts = lowered.replace("-", "_").split("_")
    if any(part in _SECRET_KEY_PARTS for part in parts):
        return True
    # Any adjacent pair counts, so `smtp_api_key` and `zarinpal_merchant_id`
    # both match even though the qualifier is unknown here.
    return any(
        (parts[i], parts[i + 1]) in _SECRET_KEY_PAIRS for i in range(len(parts) - 1)
    )


def mask_secrets(value: Any) -> Any:
    """Recursively replace credential values with a fixed marker.

    Applied on output only; the stored row is untouched, so the settings editor
    can still round-trip a value it did not change.
    """
    if isinstance(value, dict):
        return {
            k: (_MASK if _is_secret_key(str(k)) and v not in (None, "") else mask_secrets(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(v) for v in value]
    return value


class SettingResponse(BaseModel):
    """Setting output schema.

    Credential values are masked by the ``value`` serializer. Previously the
    raw value went out verbatim under ``settings:read``, and the editor role
    holds that permission — so any editor could read the SMTP password and the
    payment gateway's merchant id. WordPress makes the same call: the API keys
    endpoint masks them and only a capability-checked reveal returns the value.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: dict[str, Any] | None = None
    group: str | None = None
    description: str | None = None
    is_public: bool = False

    @field_serializer("value")
    def _mask_value(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if _is_secret_key(self.key):
            return None
        return mask_secrets(value)


class SettingCreateRequest(BaseModel):
    """Create setting payload."""

    key: str = Field(..., max_length=200)
    value: dict[str, Any] | None = None
    group: str | None = Field(None, max_length=100)
    description: str | None = None
    is_public: bool = False


class SettingUpdateRequest(BaseModel):
    """Update setting payload."""

    value: dict[str, Any] | None = None
    group: str | None = Field(None, max_length=100)
    description: str | None = None
    is_public: bool | None = None


class PublicSettingResponse(BaseModel):
    """Publicly visible setting."""

    key: str
    value: dict[str, Any] | None = None


# ── SMS Provider Schemas ─────────────────────────────────────────────────────


class SMSProviderItem(BaseModel):
    """SMS provider details and priority."""

    id: str
    name: str
    priority: int
    is_active: bool
    supports_patterns: bool


class SMSProvidersResponse(BaseModel):
    """Response model for SMS providers and failover order."""

    primary_provider: str
    failover_order: list[str]
    providers: list[SMSProviderItem]


class SMSTestRequest(BaseModel):
    """Payload to test SMS dispatch."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    phone: str | None = Field(None, min_length=10, max_length=15, examples=["09123456789"])
    mobile: str | None = Field(None, min_length=10, max_length=15, examples=["09123456789"])
    message: str | None = Field(
        None, min_length=1, max_length=500, examples=["تست ارسال پیامک سیستم"]
    )
    text: str | None = Field(
        None, min_length=1, max_length=500, examples=["تست ارسال پیامک سیستم"]
    )
    pattern: str | None = None


class SMSTestResponse(BaseModel):
    """Response model for test SMS dispatch."""

    success: bool
    provider: str | None = None
    to: str
    error: str | None = None


# ── Email (SMTP) Provider Schemas ─────────────────────────────────────────────


class SMTPEffectiveConfig(BaseModel):
    """Non-secret view of the effective SMTP configuration.

    Passwords are never returned — ``has_password`` is the only signal.
    """

    host: str
    port: int
    username: str
    use_tls: bool
    from_address: str
    from_name: str
    timeout_seconds: int
    has_password: bool
    is_configured: bool
    source: str  # "environment" | "site_settings" | "mixed"


class EmailTestRequest(BaseModel):
    """Payload to test SMTP dispatch."""

    model_config = ConfigDict(str_strip_whitespace=True)

    recipient: str = Field(..., min_length=5, max_length=320, examples=["admin@example.com"])
    message: str | None = Field(
        None, min_length=1, max_length=1000, examples=["این یک ایمیل آزمایشی از پنل مدیریت است."]
    )


class EmailTestResponse(BaseModel):
    """Response model for test email dispatch."""

    success: bool
    to: str
    provider: str
    attempts: int = 0
    error: str | None = None


class EmailDeliveryLogItem(BaseModel):
    """One row of the email delivery audit log (admin)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_id: uuid.UUID | None = None
    recipient: str
    subject: str
    template: str | None = None
    status: str
    provider: str
    provider_response: str | None = None
    error: str | None = None
    attempts: int
    sent_at: Any | None = None
    created_at: Any


class EmailDeliveryLogResponse(BaseModel):
    """Paginated delivery log for the admin settings page."""

    items: list[EmailDeliveryLogItem]
    total: int


# ── Telegram Bot Provider Schemas ──────────────────────────────────────────────


class TelegramEffectiveConfig(BaseModel):
    """Non-secret view of the effective Telegram bot configuration.

    The bot token is never returned — ``has_token`` and ``token_masked``
    are the only signals.
    """

    bot_username: str
    api_base_url: str
    timeout_seconds: int
    has_token: bool
    token_masked: str | None = None  # last 4 chars only
    is_configured: bool
    source: str  # "environment" | "site_settings" | "mixed"


class TelegramTestRequest(BaseModel):
    """Payload to test Telegram dispatch (admin)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    chat_id: str = Field(..., min_length=1, max_length=64, examples=["123456789"])
    message: str | None = Field(
        None, min_length=1, max_length=1000, examples=["این یک پیام آزمایشی از پنل مدیریت است."]
    )


class TelegramTestResponse(BaseModel):
    """Response model for test Telegram dispatch."""

    success: bool
    to: str
    provider: str
    attempts: int = 0
    error: str | None = None


class TelegramDeliveryLogItem(BaseModel):
    """One row of the telegram delivery audit log (admin)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_id: uuid.UUID | None = None
    recipient: str
    title: str
    status: str
    provider: str
    provider_response: str | None = None
    error: str | None = None
    attempts: int
    sent_at: Any | None = None
    created_at: Any


class TelegramDeliveryLogResponse(BaseModel):
    """Paginated telegram delivery log for the admin settings page."""

    items: list[TelegramDeliveryLogItem]
    total: int
