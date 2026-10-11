"""Pydantic schemas for the settings module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

#: Key names whose values are credentials and must never be serialized.
#: Matched as whole words against ``_``-separated parts, not as substrings:
#: ``tokens`` (the design-token bag) and ``tokenize`` are not credentials, and a
#: substring match once masked an entire colour palette.
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

    ``value`` is ``Any``, not ``dict``: the column is JSONB and the writers
    are not all object-shaped. The WordPress-parity content card stores plain
    scalars through ``/settings/admin/site-options`` (``posts_per_page`` →
    ``"10"``, ``media_watermark_opacity`` → ``"0.35"``), and the routes that
    accept a scalar have always had a ``str`` branch for them. A ``dict``-only
    schema made every row in that table unreadable at once: one scalar value
    anywhere in ``site_settings`` turned ``GET /settings`` into a 500, so the
    whole admin settings page — including the SMTP form — died on a
    configuration a current writer legitimately produced.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: Any = None
    group: str | None = None
    description: str | None = None
    is_public: bool = False

    @field_serializer("value")
    def _mask_value(self, value: Any) -> Any:
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
    """Publicly visible setting.

    ``value`` is ``Any`` for the same reason ``SettingResponse.value`` is:
    the JSONB column holds scalars as well as objects, and a public scalar
    option would otherwise raise during construction — a 500 on the public
    route over data a current writer produces.
    """

    key: str
    value: Any = None


# ── Maintenance Mode Schemas ─────────────────────────────────────────────────


class MaintenanceStateResponse(BaseModel):
    """Whether the store is down for maintenance, and why.

    Read by the storefront *before* it renders anything, which is what lets a
    client-rendered shell show the maintenance page instead of a blank frame with
    a network error in the console. ``minutes`` is the time *left* rather than
    the duration asked for, because an operator reading it wants to know when the
    store comes back, not what they typed.
    """

    active: bool
    reason: str = ""
    minutes: int = 0
    expires_at: datetime | None = None


class MaintenanceSetRequest(BaseModel):
    """Turn maintenance on or off."""

    active: bool
    #: How long, in minutes. The floor of ten and the ceiling of 72 hours are
    #: enforced in the service as well as here, because the service is reachable
    #: from a script and a script does not go through validation.
    minutes: int = Field(10, ge=1, le=4320)
    reason: str = Field("", max_length=500)


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


# ── Email (SMTP) Provider Schemas — removed 2026-10-07 ────────────────────────
# SMTPEffectiveConfig, EmailTestRequest, EmailTestResponse, EmailDeliveryLogItem
# and EmailDeliveryLogResponse were removed with the rest of the email feature.

