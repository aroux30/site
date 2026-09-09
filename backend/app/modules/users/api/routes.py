"""User API routes — address management and admin user CRUD."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.users.application import user_service
from app.modules.users.schemas.user import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
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
        db, user_id=user_id, data=body.model_dump(),
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


# ── Admin user management ────────────────────────────────────────────────────


@router.get(
    "/admin/users",
    response_model=UserListResponse,
    dependencies=[Depends(RequirePermissions("users:read"))],
    summary="List all users (admin)",
)
async def list_users(
    search: Optional[str] = Query(None, description="Search by phone or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    items, total = await user_service.get_users(
        db, search=search, is_active=is_active, page=page, page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return UserListResponse(
        items=[UserListItem(**i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
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
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    data = await user_service.update_user(
        db,
        user_id=user_id,
        data=body.model_dump(exclude_unset=True),
        actor_id=actor_id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    return UserDetailResponse(**data)
