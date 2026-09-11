"""RBAC service — role, permission, and assignment management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.audit.application.audit_service import log_action
from app.modules.rbac.domain.models import Permission, Role, RolePermission, UserRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Permission CRUD ──────────────────────────────────────────────────────────


async def list_permissions(
    db: AsyncSession,
    *,
    resource: str | None = None,
) -> tuple[list[Permission], int]:
    """List all permissions, optionally filtered by resource."""
    stmt = select(Permission)
    count_stmt = select(func.count(Permission.id))

    if resource is not None:
        stmt = stmt.where(Permission.resource == resource)
        count_stmt = count_stmt.where(Permission.resource == resource)

    stmt = stmt.order_by(Permission.resource, Permission.action)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def create_permission(
    db: AsyncSession,
    *,
    name: str,
    slug: str,
    description: str | None = None,
    resource: str,
    action: str,
    actor_id: uuid.UUID,
) -> Permission:
    """Create a new permission."""
    # Uniqueness checks
    existing = await db.execute(select(Permission).where(Permission.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(detail=f"Permission with slug '{slug}' already exists")

    existing_ra = await db.execute(
        select(Permission).where(Permission.resource == resource, Permission.action == action)
    )
    if existing_ra.scalar_one_or_none() is not None:
        raise ConflictError(
            detail=f"Permission for resource '{resource}' action '{action}' already exists"
        )

    perm = Permission(
        name=name,
        slug=slug,
        description=description,
        resource=resource,
        action=action,
    )
    db.add(perm)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.permission_created",
        resource="permission",
        resource_id=perm.id,
        after={"name": name, "slug": slug, "resource": resource, "action": action},
    )

    await logger.ainfo("permission_created", permission_id=str(perm.id), slug=slug)
    return perm


async def delete_permission(
    db: AsyncSession,
    *,
    permission_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Delete a permission."""
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    perm = result.scalar_one_or_none()
    if perm is None:
        raise NotFoundError(resource="Permission")

    await db.execute(delete(RolePermission).where(RolePermission.permission_id == permission_id))
    await db.delete(perm)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.permission_deleted",
        resource="permission",
        resource_id=permission_id,
        before={"slug": perm.slug},
    )

    await logger.ainfo("permission_deleted", permission_id=str(permission_id))


# ── Role CRUD ────────────────────────────────────────────────────────────────


async def list_roles(db: AsyncSession) -> tuple[list[Role], int]:
    """List all roles."""
    count = (await db.execute(select(func.count(Role.id)))).scalar() or 0
    result = await db.execute(select(Role).order_by(Role.name))
    items = list(result.scalars().all())
    return items, count


async def get_role(db: AsyncSession, *, role_id: uuid.UUID) -> dict[str, Any]:
    """Get a role with its permissions."""
    stmt = (
        select(Role)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(resource="Role")

    permissions = [
        {
            "id": rp.permission.id,
            "name": rp.permission.name,
            "slug": rp.permission.slug,
            "description": rp.permission.description,
            "resource": rp.permission.resource,
            "action": rp.permission.action,
            "created_at": rp.permission.created_at,
        }
        for rp in role.role_permissions
        if rp.permission
    ]

    return {
        "id": role.id,
        "name": role.name,
        "slug": role.slug,
        "description": role.description,
        "is_system": role.is_system,
        "permissions": permissions,
        "created_at": role.created_at,
    }


async def create_role(
    db: AsyncSession,
    *,
    name: str,
    slug: str,
    description: str | None = None,
    actor_id: uuid.UUID,
) -> Role:
    """Create a new role."""
    existing = await db.execute(select(Role).where(Role.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(detail=f"Role with slug '{slug}' already exists")

    role = Role(name=name, slug=slug, description=description, is_system=False)
    db.add(role)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.role_created",
        resource="role",
        resource_id=role.id,
        after={"name": name, "slug": slug},
    )

    await logger.ainfo("role_created", role_id=str(role.id), slug=slug)
    return role


async def update_role(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    data: dict[str, Any],
    actor_id: uuid.UUID,
) -> Role:
    """Update a role's name or description."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(resource="Role")

    if role.is_system:
        raise ValidationError(detail="System roles cannot be modified")

    for key, value in data.items():
        if value is not None:
            setattr(role, key, value)

    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.role_updated",
        resource="role",
        resource_id=role_id,
        after=data,
    )

    return role


async def delete_role(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Delete a non-system role."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if role is None:
        raise NotFoundError(resource="Role")

    if role.is_system:
        raise ValidationError(detail="System roles cannot be deleted")

    # Remove all role-permission and user-role associations
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    await db.execute(delete(UserRole).where(UserRole.role_id == role_id))
    await db.delete(role)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.role_deleted",
        resource="role",
        resource_id=role_id,
        before={"slug": role.slug, "name": role.name},
    )

    await logger.ainfo("role_deleted", role_id=str(role_id))


# ── Role-Permission Assignment ───────────────────────────────────────────────


async def assign_permissions_to_role(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
) -> None:
    """Assign one or more permissions to a role."""
    # Verify role exists
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    if role_result.scalar_one_or_none() is None:
        raise NotFoundError(resource="Role")

    for perm_id in permission_ids:
        # Verify permission exists
        perm_result = await db.execute(select(Permission).where(Permission.id == perm_id))
        if perm_result.scalar_one_or_none() is None:
            raise NotFoundError(resource="Permission", detail=f"Permission {perm_id} not found")

        # Check if already assigned
        existing = await db.execute(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm_id,
            )
        )
        if existing.scalar_one_or_none() is None:
            rp = RolePermission(role_id=role_id, permission_id=perm_id)
            db.add(rp)

    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.permissions_assigned",
        resource="role",
        resource_id=role_id,
        after={"permission_ids": [str(p) for p in permission_ids]},
    )

    await logger.ainfo(
        "permissions_assigned",
        role_id=str(role_id),
        count=len(permission_ids),
    )


async def remove_permissions_from_role(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
) -> None:
    """Remove permissions from a role."""
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    if role_result.scalar_one_or_none() is None:
        raise NotFoundError(resource="Role")

    await db.execute(
        delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id.in_(permission_ids),
        )
    )
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.permissions_removed",
        resource="role",
        resource_id=role_id,
        after={"permission_ids": [str(p) for p in permission_ids]},
    )


# ── User-Role Assignment ────────────────────────────────────────────────────


async def assign_roles_to_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
) -> list[Role]:
    """Assign one or more roles to a user."""
    from app.modules.users.domain.models import User

    user_result = await db.execute(select(User).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise NotFoundError(resource="User")

    for role_id in role_ids:
        role_result = await db.execute(select(Role).where(Role.id == role_id))
        if role_result.scalar_one_or_none() is None:
            raise NotFoundError(resource="Role", detail=f"Role {role_id} not found")

        existing = await db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        if existing.scalar_one_or_none() is None:
            ur = UserRole(user_id=user_id, role_id=role_id)
            db.add(ur)

    await db.flush()

    # Return current roles
    stmt = (
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    result = await db.execute(stmt)
    roles = list(result.scalars().all())

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.roles_assigned",
        resource="user",
        resource_id=user_id,
        after={"role_ids": [str(r) for r in role_ids]},
    )

    return roles


async def remove_roles_from_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
) -> list[Role]:
    """Remove roles from a user."""
    from app.modules.users.domain.models import User

    user_result = await db.execute(select(User).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise NotFoundError(resource="User")

    await db.execute(
        delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id.in_(role_ids))
    )
    await db.flush()

    # Return remaining roles
    stmt = (
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    result = await db.execute(stmt)
    roles = list(result.scalars().all())

    await log_action(
        db,
        actor_id=actor_id,
        action="rbac.roles_removed",
        resource="user",
        resource_id=user_id,
        after={"role_ids": [str(r) for r in role_ids]},
    )

    return roles


async def get_user_roles(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[Role]:
    """Get all roles assigned to a user."""
    stmt = (
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
