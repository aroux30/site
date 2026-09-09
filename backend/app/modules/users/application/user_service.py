"""User CRUD service for address management and admin operations."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.audit.application.audit_service import log_action
from app.modules.rbac.domain.models import Role, UserRole
from app.modules.users.domain.models import Address, User, UserProfile

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Admin User CRUD ──────────────────────────────────────────────────────────


async def get_users(
    db: AsyncSession,
    *,
    search: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """List users with optional filters and pagination (admin).

    Returns ``(items, total_count)``.
    """
    stmt = select(User).options(selectinload(User.profile))
    count_stmt = select(func.count(User.id))

    if search is not None:
        pattern = f"%{search}%"
        search_filter = (
            User.phone.ilike(pattern)
            | User.email.ilike(pattern)
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
        count_stmt = count_stmt.where(User.is_active == is_active)

    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().unique().all()

    items = []
    for user in users:
        profile = user.profile
        items.append({
            "id": user.id,
            "phone": user.phone,
            "email": user.email,
            "first_name": profile.first_name if profile else None,
            "last_name": profile.last_name if profile else None,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "last_login": user.last_login,
        })

    return items, total


async def get_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Get detailed user information (admin)."""
    stmt = (
        select(User)
        .options(selectinload(User.profile), selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(resource="User")

    profile = user.profile
    role_slugs = [ur.role.slug for ur in user.roles if ur.role] if user.roles else []

    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "first_name": profile.first_name if profile else None,
        "last_name": profile.last_name if profile else None,
        "national_code": profile.national_code if profile else None,
        "birth_date": str(profile.birth_date) if profile and profile.birth_date else None,
        "avatar_url": profile.avatar_url if profile else None,
        "gender": profile.gender if profile else None,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login,
        "roles": role_slugs,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


async def update_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Admin update of a user's fields."""
    before = await get_user(db, user_id=user_id)

    user_fields = {}
    profile_fields = {}

    for key in ("email", "is_active", "is_verified"):
        if key in data and data[key] is not None:
            user_fields[key] = data[key]

    if "email" in user_fields:
        existing = await db.execute(
            select(User).where(User.email == user_fields["email"], User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(detail="Email already in use")

    for key in ("first_name", "last_name"):
        if key in data and data[key] is not None:
            profile_fields[key] = data[key]

    if user_fields:
        await db.execute(update(User).where(User.id == user_id).values(**user_fields))

    if profile_fields:
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user_id, **profile_fields)
            db.add(profile)
        else:
            for k, v in profile_fields.items():
                setattr(profile, k, v)

    await db.flush()

    after = await get_user(db, user_id=user_id)

    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_updated",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return after


# ── Address CRUD ─────────────────────────────────────────────────────────────


async def get_addresses(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[Address]:
    """List all addresses belonging to a user."""
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_address(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> Address:
    """Create a new address for a user."""
    # If this is marked as default, unset any existing default
    if data.get("is_default", False):
        await db.execute(
            update(Address)
            .where(Address.user_id == user_id, Address.is_default.is_(True))
            .values(is_default=False)
        )

    address = Address(user_id=user_id, **data)
    db.add(address)
    await db.flush()

    await logger.ainfo(
        "address_created",
        user_id=str(user_id),
        address_id=str(address.id),
    )
    return address


async def update_address(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
    data: dict[str, Any],
) -> Address:
    """Update an existing address."""
    stmt = select(Address).where(
        Address.id == address_id, Address.user_id == user_id
    )
    result = await db.execute(stmt)
    address = result.scalar_one_or_none()

    if address is None:
        raise NotFoundError(resource="Address")

    # Handle default flag
    if data.get("is_default", False):
        await db.execute(
            update(Address)
            .where(
                Address.user_id == user_id,
                Address.id != address_id,
                Address.is_default.is_(True),
            )
            .values(is_default=False)
        )

    for key, value in data.items():
        if value is not None:
            setattr(address, key, value)

    await db.flush()

    await logger.ainfo(
        "address_updated",
        user_id=str(user_id),
        address_id=str(address_id),
    )
    return address


async def delete_address(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
) -> None:
    """Delete an address belonging to a user."""
    stmt = select(Address).where(
        Address.id == address_id, Address.user_id == user_id
    )
    result = await db.execute(stmt)
    address = result.scalar_one_or_none()

    if address is None:
        raise NotFoundError(resource="Address")

    await db.delete(address)
    await db.flush()

    await logger.ainfo(
        "address_deleted",
        user_id=str(user_id),
        address_id=str(address_id),
    )
