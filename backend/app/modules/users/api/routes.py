"""User API routes — address management and admin user CRUD."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user,
    get_current_user_id,
)
from app.modules.users.api.kyc_routes import router as kyc_router
from app.modules.users.application import user_service
from app.modules.users.schemas.user import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    AdminUserCreate,
    AdminUserUpdate,
    UserDetailResponse,
    UserListItem,
    UserListResponse,
)

router = APIRouter()


# ── Address endpoints (authenticated user) ───────────────────────────────────


@router.get(
    "/me/addresses",
    response_model=list[AddressResponse],
    summary="List my addresses",
)
async def list_addresses(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[AddressResponse]:
    addresses = await user_service.get_addresses(db, user_id=user_id)
    return [AddressResponse.model_validate(a) for a in addresses]


@router.post(
    "/me/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address",
)
async def create_address(
    body: AddressCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AddressResponse:
    address = await user_service.create_address(
        db,
        user_id=user_id,
        data=body.model_dump(),
    )
    return AddressResponse.model_validate(address)


@router.patch(
    "/me/addresses/{address_id}",
    response_model=AddressResponse,
    summary="Update an address",
)
async def update_address(
    address_id: uuid.UUID,
    body: AddressUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AddressResponse:
    address = await user_service.update_address(
        db,
        user_id=user_id,
        address_id=address_id,
        data=body.model_dump(exclude_unset=True),
    )
    return AddressResponse.model_validate(address)


@router.delete(
    "/me/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an address",
)
async def delete_address(
    address_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await user_service.delete_address(db, user_id=user_id, address_id=address_id)


# ── Admin security panel endpoints (Karta failed_attempts, P1.4) ─────────


@router.get(
    "/admin/security/failed-attempts",
    dependencies=[Depends(RequirePermissions("users:read"))],
    summary="List persisted failed login/OTP/KYC attempts (admin)",
)
async def list_failed_attempts(
    attempt_type: str | None = Query(None, description="otp | login | payment | kyc"),
    identifier: str | None = Query(None, description="Filter by phone/email/IP"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    total = await user_service.count_failed_attempts(
        db, attempt_type=attempt_type, identifier=identifier
    )
    rows = await user_service.list_failed_attempts(
        db,
        attempt_type=attempt_type,
        identifier=identifier,
        page=page,
        page_size=page_size,
    )
    return {"items": rows, "total": total}


@router.get(
    "/admin/kyc/trust-profiles",
    dependencies=[Depends(RequirePermissions("users:read"))],
    summary="List all user trust profiles for the anti-fraud panel (admin)",
)
async def list_trust_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.users.schemas.kyc import UserTrustProfileResponse

    rows, total = await user_service.list_trust_profiles(db, page=page, page_size=page_size)
    return {
        "items": [
            UserTrustProfileResponse.model_validate(r).model_dump(mode="json") for r in rows
        ],
        "total": total,
    }


# ── Admin user management ────────────────────────────────────────────────────


@router.get(
    "/admin/users",
    response_model=UserListResponse,
    dependencies=[Depends(RequirePermissions("users:read"))],
    summary="List all users (admin)",
)
async def list_users(
    search: str | None = Query(None, description="Search by phone or email"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    items, total = await user_service.get_users(
        db,
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return UserListResponse(
        items=[UserListItem(**i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=pages,
    )


@router.get(
    "/admin/users/{user_id}",
    response_model=UserDetailResponse,
    dependencies=[Depends(RequirePermissions("users:read"))],
    summary="Get user details (admin)",
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    data = await user_service.get_user(db, user_id=user_id)
    return UserDetailResponse(**data)


@router.patch(
    "/admin/users/{user_id}",
    response_model=UserDetailResponse,
    dependencies=[Depends(RequirePermissions("users:write"))],
    summary="Update a user (admin)",
)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    request: Request,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    data = await user_service.update_user(
        db,
        user_id=user_id,
        data=body.model_dump(exclude_unset=True),
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    return UserDetailResponse(**data)


@router.post(
    "/admin/users",
    response_model=UserDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("users:write"))],
    summary="Create a new user directly (admin)",
)
async def create_user(
    body: AdminUserCreate,
    request: Request,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    actor: dict[str, Any] = Depends(get_current_user),
) -> UserDetailResponse:
    if body.role_slugs:
        await RequirePermissions("rbac:write")(actor)

    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    user = await user_service.create_user_admin(
        db,
        data=body.model_dump(exclude_unset=True),
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return UserDetailResponse(**user)


@router.post(
    "/admin/users/{user_id}/block",
    response_model=UserDetailResponse,
    dependencies=[Depends(RequirePermissions("users:write"))],
    summary="Block a user and revoke active sessions (admin)",
)
async def block_user(
    user_id: uuid.UUID,
    request: Request,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    user = await user_service.block_user(
        db,
        user_id=user_id,
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return UserDetailResponse(**user)


@router.post(
    "/admin/users/{user_id}/unblock",
    response_model=UserDetailResponse,
    dependencies=[Depends(RequirePermissions("users:write"))],
    summary="Unblock a user (admin)",
)
async def unblock_user(
    user_id: uuid.UUID,
    request: Request,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    user = await user_service.unblock_user(
        db,
        user_id=user_id,
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return UserDetailResponse(**user)


@router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("users:write"))],
    summary="Soft-delete a user (admin)",
)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    await user_service.soft_delete_user(
        db,
        user_id=user_id,
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()


@router.post(
    "/admin/users/{user_id}/restore",
    response_model=UserDetailResponse,
    dependencies=[Depends(RequirePermissions("users:write"))],
    summary="Restore a soft-deleted user (admin)",
)
async def restore_user(
    user_id: uuid.UUID,
    request: Request,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    user = await user_service.restore_user(
        db,
        user_id=user_id,
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return UserDetailResponse(**user)


# ── KYC and anti-fraud sub-router (Karta Phase 1) ──────────────────────────
router.include_router(kyc_router)
