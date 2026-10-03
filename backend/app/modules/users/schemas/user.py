"""User-related Pydantic v2 schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

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
    display_name: str | None = None
    is_active: bool
    is_verified: bool
    #: True while the account waits for an operator's approval, so the admin
    #: table can badge it and offer approve/reject.
    pending_approval: bool = False
    created_at: datetime
    last_login: datetime | None = None
    deleted_at: datetime | None = None
    #: Role names this user holds. A user holds a *set* of roles, never a
    #: single one — the admin table and its filter both read this list, so
    #: omitting it made every row read as a plain customer.
    #:
    #: Slugs, not display names. The admin table filters with
    #: ``roles.includes("super_admin")`` and renders the same slug; sending
    #: ``ur.role.name`` (a Persian label) meant the filter matched nothing and
    #: the "system admin" badge never appeared on any row.
    roles: list[str] = []
    #: The superuser flag the admin table reads for its badge. Absent here, so
    #: every row rendered without it.
    is_superuser: bool = False


class UserListResponse(BaseModel):
    """Paginated list of users (admin view).

    Field names follow the platform-wide inline pagination convention
    ({items, total, page, page_size, total_pages}) used by the media, blog,
    catalog and other list endpoints (Phase 3 API-consistency fix).
    """

    items: list[UserListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserDetailResponse(BaseModel):
    """Detailed user information for admin view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    pending_approval: bool = False
    national_code: str | None = None
    birth_date: str | None = None
    avatar_url: str | None = None
    gender: str | None = None
    is_b2b: bool = False
    company_name: str | None = None
    tax_exemption_certificate_no: str | None = None
    is_active: bool
    is_verified: bool
    is_superuser: bool
    last_login: datetime | None = None
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class AdminUserCreate(BaseModel):
    """Payload to create a new user directly by an administrator."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=10, max_length=15, examples=["09123456789"])
    email: str | None = Field(None, max_length=255)
    password: str | None = Field(None, min_length=8, max_length=128)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    national_code: str | None = Field(None, min_length=10, max_length=10)
    is_active: bool = True
    is_verified: bool = True
    role_slugs: list[str] = []


class AdminUserUpdate(BaseModel):
    """Fields an admin can update on any user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str | None = Field(None, max_length=255)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    display_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    is_verified: bool | None = None
    is_b2b: bool | None = None
    company_name: str | None = Field(None, max_length=200)
    tax_exemption_certificate_no: str | None = Field(None, max_length=200)


class AdminBulkUserAction(BaseModel):
    """One action over many accounts. Ids are capped so a single request cannot
    fan out unbounded — the same limit the blog bulk route uses."""

    model_config = ConfigDict(str_strip_whitespace=True)

    #: Which action to run. A body field rather than a path segment: a
    #: ``/bulk/{action}`` path would be shadowed by the single-account
    #: ``/{user_id}/block`` routes, which match the same shape.
    action: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="block | unblock | delete | restore | set_role",
    )
    ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="User ids to act on (max 200 per request)",
    )
    #: Required only for action="set_role"; ignored otherwise. A slug, not an id,
    #: so the caller names the role the same way the list filter and the row
    #: badge do.
    role_slug: str | None = Field(
        None,
        max_length=100,
        description="Role slug to assign, for action='set_role'.",
    )


class AdminBulkUserActionResponse(BaseModel):
    """Per-account outcomes, so a partial success is not reported as a success.

    ``failed`` counts the accounts a guard refused (self, superuser, last admin)
    as well as any that genuinely errored; the operator sees which, from
    ``results``.
    """

    action: str
    ok: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=0)
    results: list[dict[str, Any]]


class ApplicationPasswordAdminResponse(BaseModel):
    """An account's API credential, as an operator sees it.

    Deliberately a distinct model from the self-service response rather than a
    reuse: this one is rendered on a page an operator looks at while helping
    someone, and the security boundary is that **no secret material crosses
    it**. There is no field for the hash and none for the one-time plaintext —
    a response model that simply happens to omit them would be one careless
    field away from leaking; one that cannot hold them cannot leak them.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    #: First characters of the secret, so an operator and the user can agree
    #: on *which* credential a ticket is about without either side holding it.
    token_prefix: str
    scopes: list[str] = []
    is_active: bool
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None


class PasswordResetIssuedResponse(BaseModel):
    """Whether an admin-initiated password reset actually issued a link.

    ``sent`` is a real answer rather than a courtesy. An OTP-only account has no
    password to reset and no address to send to, and a response that said "done"
    either way would leave the operator watching an inbox for a message that was
    never going to be written.
    """

    sent: bool
    detail: str


class UserDeleteResultResponse(BaseModel):
    """What a soft-delete actually did, including to the content.

    Returned rather than a bare 204, because the outcome the operator cannot see
    is the one that matters: seven columns point at ``users`` with ``ON DELETE
    SET NULL``, so a delete with no heir leaves every post, page and comment those
    people wrote attributed to nobody. An operator who is told only "deleted"
    cannot tell that from the case where nothing was owned.
    """

    owned_before: dict[str, int]
    reassigned: dict[str, int]
    summary: str


class ReassignPreviewResponse(BaseModel):
    """What a user owns, before anyone decides who inherits it."""

    owned: dict[str, int]
    total: int
    summary: str


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
