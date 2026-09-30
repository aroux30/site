"""RBAC (Role-Based Access Control) Pydantic v2 schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Permission schemas ───────────────────────────────────────────────────────


class PermissionCreate(BaseModel):
    """Create a new permission."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100, examples=["Read Users"])
    slug: str = Field(..., min_length=1, max_length=100, examples=["users:read"])
    description: str | None = Field(None, max_length=500)
    resource: str = Field(..., min_length=1, max_length=100, examples=["users"])
    action: str = Field(..., min_length=1, max_length=50, examples=["read"])


class PermissionResponse(BaseModel):
    """Permission response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    resource: str
    action: str
    created_at: datetime


class PermissionListResponse(BaseModel):
    """List of permissions."""

    items: list[PermissionResponse]
    total: int


# ── Role schemas ─────────────────────────────────────────────────────────────


class RoleCreate(BaseModel):
    """Create a new role."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100, examples=["Admin"])
    slug: str = Field(..., min_length=1, max_length=100, examples=["admin"])
    description: str | None = Field(None, max_length=500)


class RoleUpdate(BaseModel):
    """Update a role."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoleResponse(BaseModel):
    """Role response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    is_system: bool
    created_at: datetime


class RoleDetailResponse(BaseModel):
    """Role with its assigned permissions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    is_system: bool
    permissions: list[PermissionResponse] = []
    created_at: datetime


class RoleListResponse(BaseModel):
    """List of roles."""

    items: list[RoleResponse]
    total: int


# ── Role-Permission assignment ───────────────────────────────────────────────


class RolePermissionAssign(BaseModel):
    """Assign permissions to a role."""

    permission_ids: list[uuid.UUID] = Field(..., min_length=1)


class RolePermissionRemove(BaseModel):
    """Remove permissions from a role."""

    permission_ids: list[uuid.UUID] = Field(..., min_length=1)


# ── User-Role assignment ────────────────────────────────────────────────────


class UserRoleAssign(BaseModel):
    """Assign roles to a user."""

    role_ids: list[uuid.UUID] = Field(..., min_length=1)


class UserRoleRemove(BaseModel):
    """Remove roles from a user."""

    role_ids: list[uuid.UUID] = Field(..., min_length=1)


class UserRoleResponse(BaseModel):
    """User-role assignment response."""

    user_id: uuid.UUID
    roles: list[RoleResponse]


# ── User permission overrides (WordPress add_cap/remove_cap parity) ─────────


class PermissionOverrideCreate(BaseModel):
    """Grant or deny a single permission directly to a user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    permission: str = Field(..., min_length=1, max_length=100, examples=["blog:write"])
    effect: str = Field("grant", pattern="^(grant|deny)$")


class PermissionOverrideResponse(BaseModel):
    """One per-user capability override."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    permission: str
    effect: str
    created_by: uuid.UUID | None = None
    created_at: datetime


class PermissionOverrideListResponse(BaseModel):
    """All capability overrides held by a user."""

    user_id: uuid.UUID
    items: list[PermissionOverrideResponse]
    total: int


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
