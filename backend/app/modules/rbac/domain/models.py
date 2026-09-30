"""RBAC (Role-Based Access Control) domain models."""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.users.domain.models import User


class Role(BaseModel):
    """User roles for access control."""

    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", lazy="select"
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="role", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, slug={self.slug})>"


class Permission(BaseModel):
    """Granular permissions for resources and actions."""

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
        Index("ix_permissions_slug", "slug"),
        Index("ix_permissions_resource", "resource"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, slug={self.slug})>"


class RolePermission(BaseModel):
    """Many-to-many association between roles and permissions."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
        # Reverse of the composite unique: auth and RBAC flows look up a
        # permission's roles, and deleting a permission scans by this column.
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(
        "Permission", back_populates="role_permissions"
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"


class UserRole(BaseModel):
    """Many-to-many association between users and roles."""

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
        # The composite unique serves WHERE user_id = ?; this serves the
        # reverse lookup used by role-management and auth flows.
        Index("ix_user_roles_role_id", "role_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")

    def __repr__(self) -> str:
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


class OverrideEffect(str, enum.Enum):
    """Effect of a per-user permission override (WordPress add_cap/remove_cap)."""

    GRANT = "grant"
    DENY = "deny"


class UserPermissionOverride(BaseModel):
    """Per-user direct capability override (WordPress add_cap/remove_cap parity).

    Resolution order for a user's effective permission set:

    1. ``deny`` overrides win outright — the permission is removed even when
       every role the user holds grants it (and even when the JWT carries the
       ``*`` wildcard).
    2. ``grant`` overrides add the permission without touching any role —
       the WordPress "specific capability" an operator hands to one user.
    3. Role-derived permissions (unchanged behaviour) fill the remainder.

    One row per (user, permission): granting a second time flips the effect
    rather than duplicating the row. Permission strings must exist in
    ``permission_catalog.PERMISSION_CATALOG`` — unknown codenames are
    rejected with 422 at the API boundary.
    """

    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "permission", name="uq_user_permission_overrides_user_perm"),
        # Reverse lookup: audit ("who is denied X") and cascade scans.
        Index("ix_user_permission_overrides_permission", "permission"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    effect: Mapped[OverrideEffect] = mapped_column(
        Enum(
            OverrideEffect,
            name="user_permission_override_effect_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<UserPermissionOverride(user_id={self.user_id}, "
            f"permission={self.permission}, effect={self.effect})>"
        )
