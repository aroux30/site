"""RBAC admin API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user,
    get_current_user_id,
)
from app.modules.rbac.application import override_service, rbac_service

# Request-time enforcement of per-user permission overrides: wraps the
# security dependencies once, at route import (app startup). Idempotent and
# fail-safe — see app/modules/rbac/application/override_enforcement.py.
from app.modules.rbac.application.override_enforcement import install as _install_overrides
from app.modules.rbac.schemas.rbac import (
    MessageResponse,
    PermissionCreate,
    PermissionListResponse,
    PermissionOverrideCreate,
    PermissionOverrideListResponse,
    PermissionOverrideResponse,
    PermissionResponse,
    RoleCreate,
    RoleDetailResponse,
    RoleListResponse,
    RolePermissionAssign,
    RolePermissionRemove,
    RoleResponse,
    RoleUpdate,
    UserRoleAssign,
    UserRoleRemove,
    UserRoleResponse,
)

_install_overrides()

router = APIRouter()


# ── Permission endpoints ─────────────────────────────────────────────────────


@router.get(
    "/admin/permissions",
    response_model=PermissionListResponse,
    dependencies=[Depends(RequirePermissions("rbac:read"))],
    summary="List all permissions",
)
async def list_permissions(
    resource: str | None = Query(None, description="Filter by resource"),
    db: AsyncSession = Depends(get_db),
) -> PermissionListResponse:
    items, total = await rbac_service.list_permissions(db, resource=resource)
    return PermissionListResponse(
        items=[PermissionResponse.model_validate(p) for p in items],
        total=total,
    )


@router.post(
    "/admin/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Create a permission",
)
async def create_permission(
    body: PermissionCreate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PermissionResponse:
    perm = await rbac_service.create_permission(
        db,
        name=body.name,
        slug=body.slug,
        description=body.description,
        resource=body.resource,
        action=body.action,
        actor_id=actor_id,
    )
    return PermissionResponse.model_validate(perm)


@router.delete(
    "/admin/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Delete a permission",
)
async def delete_permission(
    permission_id: uuid.UUID,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await rbac_service.delete_permission(
        db,
        permission_id=permission_id,
        actor_id=actor_id,
    )


# ── Role endpoints ───────────────────────────────────────────────────────────


@router.get(
    "/admin/roles",
    response_model=RoleListResponse,
    dependencies=[Depends(RequirePermissions("rbac:read"))],
    summary="List all roles",
)
async def list_roles(
    db: AsyncSession = Depends(get_db),
) -> RoleListResponse:
    items, total = await rbac_service.list_roles(db)
    return RoleListResponse(
        items=[RoleResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get(
    "/admin/roles/{role_id}",
    response_model=RoleDetailResponse,
    dependencies=[Depends(RequirePermissions("rbac:read"))],
    summary="Get role details with permissions",
)
async def get_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RoleDetailResponse:
    data = await rbac_service.get_role(db, role_id=role_id)
    return RoleDetailResponse(**data)


@router.post(
    "/admin/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Create a role",
)
async def create_role(
    body: RoleCreate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    role = await rbac_service.create_role(
        db,
        name=body.name,
        slug=body.slug,
        description=body.description,
        actor_id=actor_id,
    )
    return RoleResponse.model_validate(role)


@router.patch(
    "/admin/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Update a role",
)
async def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    role = await rbac_service.update_role_details(
        db,
        role_id=role_id,
        name=body.name,
        description=body.description,
        actor_id=actor_id,
    )
    return RoleResponse.model_validate(role)


@router.delete(
    "/admin/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Delete a role",
)
async def delete_role(
    role_id: uuid.UUID,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await rbac_service.delete_role(db, role_id=role_id, actor_id=actor_id)


# ── Role-Permission assignment ───────────────────────────────────────────────


@router.post(
    "/admin/roles/{role_id}/permissions",
    response_model=MessageResponse,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Assign permissions to a role",
)
async def assign_permissions(
    role_id: uuid.UUID,
    body: RolePermissionAssign,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await rbac_service.assign_permissions_to_role(
        db,
        role_id=role_id,
        permission_ids=body.permission_ids,
        actor_id=actor_id,
        actor_payload=current_user,
    )
    return MessageResponse(message="Permissions assigned successfully")


@router.delete(
    "/admin/roles/{role_id}/permissions",
    response_model=MessageResponse,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Remove permissions from a role",
)
async def remove_permissions(
    role_id: uuid.UUID,
    body: RolePermissionRemove,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await rbac_service.remove_permissions_from_role(
        db,
        role_id=role_id,
        permission_ids=body.permission_ids,
        actor_id=actor_id,
    )
    return MessageResponse(message="Permissions removed successfully")


# ── User-Role assignment ────────────────────────────────────────────────────


@router.get(
    "/admin/users/{user_id}/roles",
    response_model=UserRoleResponse,
    dependencies=[Depends(RequirePermissions("rbac:read"))],
    summary="Get roles assigned to a user",
)
async def get_user_roles(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserRoleResponse:
    roles = await rbac_service.get_user_roles(db, user_id=user_id)
    return UserRoleResponse(
        user_id=user_id,
        roles=[RoleResponse.model_validate(r) for r in roles],
    )


@router.post(
    "/admin/users/{user_id}/roles",
    response_model=UserRoleResponse,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Assign roles to a user",
)
async def assign_user_roles(
    user_id: uuid.UUID,
    body: UserRoleAssign,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRoleResponse:
    roles = await rbac_service.assign_roles_to_user(
        db,
        user_id=user_id,
        role_ids=body.role_ids,
        actor_id=actor_id,
        actor_payload=current_user,
    )
    return UserRoleResponse(
        user_id=user_id,
        roles=[RoleResponse.model_validate(r) for r in roles],
    )


@router.delete(
    "/admin/users/{user_id}/roles",
    response_model=UserRoleResponse,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Remove roles from a user",
)
async def remove_user_roles(
    user_id: uuid.UUID,
    body: UserRoleRemove,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserRoleResponse:
    roles = await rbac_service.remove_roles_from_user(
        db,
        user_id=user_id,
        role_ids=body.role_ids,
        actor_id=actor_id,
    )
    return UserRoleResponse(
        user_id=user_id,
        roles=[RoleResponse.model_validate(r) for r in roles],
    )


# ── User permission overrides (WordPress add_cap/remove_cap parity) ─────────


@router.get(
    "/admin/users/{user_id}/permission-overrides",
    response_model=PermissionOverrideListResponse,
    dependencies=[Depends(RequirePermissions("rbac:read"))],
    summary="List a user's direct permission overrides",
)
async def list_user_permission_overrides(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PermissionOverrideListResponse:
    overrides = await override_service.list_overrides(db, user_id=user_id)
    return PermissionOverrideListResponse(
        user_id=user_id,
        items=[PermissionOverrideResponse.model_validate(o) for o in overrides],
        total=len(overrides),
    )


@router.post(
    "/admin/users/{user_id}/permission-overrides",
    response_model=PermissionOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Grant (or deny) a permission directly to a user",
)
async def grant_user_permission_override(
    user_id: uuid.UUID,
    body: PermissionOverrideCreate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PermissionOverrideResponse:
    """Upsert one override row: deny beats role grants, grant adds without a role."""
    override = await override_service.grant_override(
        db,
        user_id=user_id,
        permission=body.permission,
        effect=body.effect,
        created_by=actor_id,
        actor_payload=current_user,
    )
    return PermissionOverrideResponse.model_validate(override)


@router.delete(
    "/admin/users/{user_id}/permission-overrides/{permission}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("rbac:write"))],
    summary="Revoke a user's direct permission override",
)
async def revoke_user_permission_override(
    user_id: uuid.UUID,
    permission: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await override_service.revoke_override(db, user_id=user_id, permission=permission)
