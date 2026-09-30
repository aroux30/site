"""User CRUD service for address management and admin operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
)
from app.modules.audit.application.audit_service import log_action
from app.modules.rbac.domain.models import UserRole
from app.modules.users.domain.models import Address, User, UserProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
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
    # The role links are eager-loaded on purpose: the admin users table has a
    # role column and a role filter, and without this the API returned no role
    # names at all, so every row rendered as "مشتری عادی" and the filter matched
    # nothing. A repair of the frontend alone could not have fixed it — the field
    # was never on the wire.
    stmt = select(User).options(selectinload(User.profile), selectinload(User.roles).selectinload(UserRole.role))
    count_stmt = select(func.count(User.id))

    if search is not None:
        pattern = f"%{search}%"
        search_filter = User.phone.ilike(pattern) | User.email.ilike(pattern)
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
        items.append(
            {
                "id": user.id,
                "phone": user.phone,
                "email": user.email,
                "first_name": profile.first_name if profile else None,
                "last_name": profile.last_name if profile else None,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at,
                "last_login": user.last_login,
                # Slugs, not the Persian display name: the admin table filters
                # and badges on ``super_admin``/``vendor``, so a display name
                # made the role filter match nothing.
                "roles": [ur.role.slug for ur in user.roles if ur.role is not None],
                "is_superuser": bool(user.is_superuser),
            }
        )

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
        "is_b2b": bool(getattr(profile, "is_b2b", False)) if profile else False,
        "company_name": getattr(profile, "company_name", None) if profile else None,
        "tax_exemption_certificate_no": (
            getattr(profile, "tax_exemption_certificate_no", None) if profile else None
        ),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login,
        "roles": role_slugs,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "deleted_at": user.deleted_at,
    }


async def create_user_admin(
    db: AsyncSession,
    *,
    data: dict[str, Any],
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Admin direct creation of a new platform user."""
    from app.core.security.password import hash_password
    from app.modules.rbac.domain.models import Role, UserRole

    phone = data["phone"]
    email = data.get("email")
    password = data.get("password")

    existing_phone = await db.execute(select(User).where(User.phone == phone))
    if existing_phone.scalar_one_or_none() is not None:
        raise ConflictError(detail="Phone number already registered")

    if email:
        existing_email = await db.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none() is not None:
            raise ConflictError(detail="Email already registered")

    pwd_hash = hash_password(password) if password else None

    user = User(
        phone=phone,
        email=email,
        password_hash=pwd_hash,
        is_active=data.get("is_active", True),
        is_verified=data.get("is_verified", True),
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        national_code=data.get("national_code"),
    )
    db.add(profile)

    role_slugs = data.get("role_slugs", [])
    if role_slugs:
        roles_res = await db.execute(select(Role).where(Role.slug.in_(role_slugs)))
        for r in roles_res.scalars().all():
            db.add(UserRole(user_id=user.id, role_id=r.id, assigned_by=actor_id))

    await db.flush()
    created = await get_user(db, user_id=user.id)

    # Tell the account holder. An operator creating a staff or customer account
    # left it completely silent: the address was stored, the password was set,
    # and the new owner had no idea the account existed until they tried to
    # log in and failed. Sent after the row is flushed so the id exists, and
    # through the same path as every other transactional mail in the app.
    #
    # Best-effort: a mail outage must not roll back a user the operator just
    # created, so the failure is logged and swallowed, exactly as in
    # ``_send_password_reset`` and ``email_change_service``.
    if email:
        try:
            from app.modules.notifications.application.email_service import send_email

            await send_email(
                db,
                recipient=email,
                subject="حساب شما ایجاد شد",
                html_body=(
                    '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                    "<p>حساب کاربری شما در فروشگاه ایجاد شد.</p>"
                    "<p>اگر این حساب را شما درخواست نکرده‌اید، "
                    "همین حالا با پشتیبانی تماس بگیرید.</p>"
                    "</div>"
                ),
                text_body=(
                    "حساب کاربری شما در فروشگاه ایجاد شد.\n"
                    "اگر این حساب را شما درخواست نکرده‌اید، "
                    "همین حالا با پشتیبانی تماس بگیرید."
                ),
            )
        except Exception:
            logger.exception("admin_user_created_email_failed", user_id=str(user.id))

    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_created",
        resource="user",
        resource_id=user.id,
        after=created,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return created


def _check_admin_target_guard(user: User, actor_id: uuid.UUID) -> None:
    """An admin must not neutralize their own account or a superuser's.

    Self-block would instantly revoke the acting admin's own sessions and
    denylist their token; blocking a superuser would let a mere ``users:write``
    holder disable the most privileged account (and, if it is the last active
    admin, permanently lock out administration). Mirrors the self-escalation
    guard in rbac_service.
    """
    from app.core.exceptions.handlers import ForbiddenError

    if user.id == actor_id:
        raise ForbiddenError(detail="You cannot perform this action on your own account")
    if user.is_superuser:
        raise ForbiddenError(detail="A superuser account cannot be modified by this action")


async def block_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Block user, revoke all active sessions, and denylist tokens in Redis."""
    from app.core.security.revocation import denylist_user
    from app.modules.users.domain.models import UserSession

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    before = await get_user(db, user_id=user_id)
    user.is_active = False

    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await denylist_user(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_blocked",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


async def unblock_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Unblock user and remove from token denylist."""
    from app.core.security.revocation import remove_from_denylist

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    before = await get_user(db, user_id=user_id)
    user.is_active = True
    await remove_from_denylist(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_unblocked",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


async def soft_delete_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Soft-delete user by setting deleted_at timestamp and revoking access."""
    from datetime import UTC, datetime

    from app.core.security.revocation import denylist_user
    from app.modules.users.domain.models import UserSession

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    before = await get_user(db, user_id=user_id)
    user.deleted_at = datetime.now(UTC)
    user.is_active = False

    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await denylist_user(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_deleted",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def restore_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Restore a soft-deleted user."""
    from app.core.security.revocation import remove_from_denylist

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    before = await get_user(db, user_id=user_id)
    user.deleted_at = None
    user.is_active = True
    await remove_from_denylist(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_restored",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


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
    # Same guard as block/unblock/soft_delete/restore. Without it this path was
    # the only admin route on the user that could rewrite a superuser's fields,
    # including their email — which is a takeover path, since the next password
    # reset goes to the address the attacker chose.
    target = await db.get(User, user_id)
    if target is None:
        raise NotFoundError(resource="User", detail=f"User {user_id} not found")
    _check_admin_target_guard(target, actor_id)

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

    # B2B / مالیات تکلیفی fields (tax engine v1) — additive; only mapped when
    # explicitly provided so existing admin updates keep working untouched.
    for key in ("is_b2b", "company_name", "tax_exemption_certificate_no"):
        if key in data:
            profile_fields[key] = data[key]

    if user_fields:
        await db.execute(update(User).where(User.id == user_id).values(**user_fields))

    # Deactivation must take effect immediately (audit R4): kill refresh
    # sessions and put the user on the access-token denylist so live JWTs
    # are rejected for the rest of their TTL.
    if user_fields.get("is_active") is False:
        from app.core.security.revocation import denylist_user
        from app.modules.users.domain.models import UserSession

        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
            .values(is_revoked=True)
        )
        await denylist_user(user_id)
        await logger.ainfo("admin_user_deactivated_access_revoked", user_id=str(user_id))
    elif user_fields.get("is_active") is True:
        from app.core.security.revocation import remove_from_denylist

        await remove_from_denylist(user_id)

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
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
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
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
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


async def list_failed_attempts(
    db: AsyncSession,
    *,
    attempt_type: str | None = None,
    identifier: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """Persisted failed login/OTP/KYC attempts for the admin panel (Karta failed_attempts).

    The search term is bound as a parameter via ``contains(autoescape=True)``;
    user-supplied LIKE wildcards are escaped, never concatenated (P1.4).
    """
    from app.modules.users.domain.kyc_models import AttemptType, FailedAttempt

    stmt = select(FailedAttempt).order_by(FailedAttempt.created_at.desc())
    if attempt_type:
        stmt = stmt.where(FailedAttempt.attempt_type == AttemptType(attempt_type))
    if identifier:
        stmt = stmt.where(FailedAttempt.identifier.contains(identifier, autoescape=True))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "identifier": r.identifier,
            "attempt_type": (
                r.attempt_type.value if hasattr(r.attempt_type, "value") else str(r.attempt_type)
            ),
            "ip_address": r.ip_address,
            "user_agent": r.user_agent,
            "created_at": r.created_at,
        }
        for r in rows
    ]


async def count_failed_attempts(
    db: AsyncSession,
    *,
    attempt_type: str | None = None,
    identifier: str | None = None,
) -> int:
    """Count failed attempts matching the admin panel filters."""
    from app.modules.users.domain.kyc_models import AttemptType, FailedAttempt

    stmt = select(func.count()).select_from(FailedAttempt)
    if attempt_type:
        stmt = stmt.where(FailedAttempt.attempt_type == AttemptType(attempt_type))
    if identifier:
        stmt = stmt.where(FailedAttempt.identifier.contains(identifier, autoescape=True))
    return int((await db.execute(stmt)).scalar_one() or 0)


async def list_trust_profiles(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Any], int]:
    """All user trust profiles, riskiest first (anti-fraud admin panel)."""
    from app.modules.users.domain.kyc_models import UserTrustProfile

    total_result = await db.execute(select(func.count()).select_from(UserTrustProfile))
    total = int(total_result.scalar_one() or 0)
    rows = (
        (
            await db.execute(
                select(UserTrustProfile)
                .order_by(UserTrustProfile.risk_score.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total
