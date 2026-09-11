"""Authentication business-logic service.

Handles registration, login, OTP flow, token refresh, session management,
profile retrieval / update, and password changes.
"""

from __future__ import annotations

import random
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import structlog
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.core.security.password import hash_password, verify_dummy_password, verify_password
from app.core.security.rate_limiter import (
    brute_force_protector,
    otp_brute_force_protector,
)
from app.modules.audit.application.audit_service import log_action
from app.modules.rbac.domain.models import Role, RolePermission, Permission, UserRole
from app.modules.users.domain.models import (
    Address,
    OTPRequest,
    User,
    UserProfile,
    UserSession,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()
settings = get_settings()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP code."""
    return "".join(random.choices(string.digits, k=length))


async def _get_user_permissions(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Collect all permission slugs for a user through their roles."""
    stmt = (
        select(Permission.slug)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_user_role_slugs(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Return role slugs assigned to a user."""
    stmt = (
        select(Role.slug)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _create_token_pair(
    db: AsyncSession,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Build access + refresh tokens, persist a session row, and return them."""
    permissions = await _get_user_permissions(db, user.id)
    roles = await _get_user_role_slugs(db, user.id)

    if user.is_superuser:
        if "super_admin" not in roles:
            roles.append("super_admin")
        if "admin" not in roles:
            roles.append("admin")
        if "*" not in permissions:
            permissions.append("*")

    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "permissions": permissions,
            "roles": roles,
            "is_superuser": bool(user.is_superuser),
        },
    )
    refresh = create_refresh_token(subject=user.id)

    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session = UserSession(
        user_id=user.id,
        refresh_token=refresh,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


# ── Public API ───────────────────────────────────────────────────────────────


async def register(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    first_name: str,
    last_name: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Register a new user account.

    Steps:
    1. Check phone uniqueness
    2. Create ``User`` with hashed password
    3. Create ``UserProfile``
    4. Assign the *customer* role (create it if missing)
    5. Return a fresh token pair
    """
    # 1. Uniqueness check
    existing = await db.execute(select(User).where(User.phone == phone))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(detail="Phone number already registered")

    # 2. Create user
    user = User(
        phone=phone,
        password_hash=hash_password(password),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()  # materialise user.id

    # 3. Profile
    profile = UserProfile(
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
    )
    db.add(profile)

    # 4. Assign customer role
    role_result = await db.execute(select(Role).where(Role.slug == "customer"))
    role = role_result.scalar_one_or_none()
    if role is None:
        role = Role(name="Customer", slug="customer", is_system=True)
        db.add(role)
        await db.flush()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)
    await db.flush()

    # 5. Tokens
    tokens = await _create_token_pair(
        db, user, ip_address=ip_address, user_agent=user_agent,
    )

    # Audit
    await log_action(
        db,
        actor_id=user.id,
        action="user.register",
        resource="user",
        resource_id=user.id,
        after={"phone": phone, "first_name": first_name, "last_name": last_name},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    await logger.ainfo("user_registered", user_id=str(user.id), phone=phone)
    return tokens


async def login(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Authenticate with phone + password and return tokens."""
    # Check brute-force lockout first
    await brute_force_protector.check_lockout(phone)

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None:
        # Constant-time dummy computation to prevent user enumeration via timing
        verify_dummy_password(password)
        await brute_force_protector.record_failure(phone, ip=ip_address)
        raise UnauthorizedError(detail="Invalid phone or password")

    if not verify_password(password, user.password_hash):
        await brute_force_protector.record_failure(phone, ip=ip_address)
        await log_action(
            db,
            actor_id=None,
            action="user.login_failed",
            resource="user",
            after={"phone": phone, "reason": "invalid_password"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise UnauthorizedError(detail="Invalid phone or password")

    if not user.is_active:
        raise UnauthorizedError(detail="Account is deactivated")

    # Clear brute-force failure counter on successful authentication
    await brute_force_protector.record_success(phone)

    # Update last login
    user.last_login = datetime.now(UTC)
    await db.flush()

    tokens = await _create_token_pair(
        db, user, ip_address=ip_address, user_agent=user_agent,
    )

    await log_action(
        db,
        actor_id=user.id,
        action="user.login",
        resource="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    await logger.ainfo("user_logged_in", user_id=str(user.id))
    return tokens


async def request_otp(
    db: AsyncSession,
    *,
    phone: str,
    purpose: str = "login",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Generate a 6-digit OTP and persist it.

    In production this would dispatch the code via an SMS provider;
    in ``mock`` mode the code is returned in the response for testing.
    """
    # Rate-limit: check for recent unexpired OTPs
    cooldown_threshold = datetime.now(UTC) - timedelta(
        seconds=settings.OTP_COOLDOWN_SECONDS
    )
    recent_stmt = select(OTPRequest).where(
        OTPRequest.phone == phone,
        OTPRequest.purpose == purpose,
        OTPRequest.created_at >= cooldown_threshold,
        OTPRequest.is_used.is_(False),
    )
    recent = await db.execute(recent_stmt)
    if recent.scalar_one_or_none() is not None:
        raise RateLimitError(
            detail=f"Please wait {settings.OTP_COOLDOWN_SECONDS} seconds before requesting a new OTP"
        )

    code = _generate_otp(settings.OTP_LENGTH)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.OTP_EXPIRY_SECONDS)

    otp = OTPRequest(
        phone=phone,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
    )
    db.add(otp)
    await db.flush()

    # Mock SMS send – in production, dispatch via Kavenegar / Ghasedak
    response: dict[str, Any] = {
        "message": "OTP sent successfully",
        "expires_in": settings.OTP_EXPIRY_SECONDS,
    }
    if settings.SMS_PROVIDER == "mock":
        response["code"] = code  # only in dev/test

    await logger.ainfo("otp_requested", phone=phone, purpose=purpose)
    return response


async def verify_otp(
    db: AsyncSession,
    *,
    phone: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Verify an OTP code and return tokens.

    If the phone does not belong to an existing user, a new user is created
    (OTP-based registration).
    """
    # Check OTP brute-force lockout
    await otp_brute_force_protector.check_lockout(phone)

    now = datetime.now(UTC)
    stmt = (
        select(OTPRequest)
        .where(
            OTPRequest.phone == phone,
            OTPRequest.is_used.is_(False),
            OTPRequest.expires_at > now,
        )
        .order_by(OTPRequest.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    otp = result.scalar_one_or_none()

    if otp is None:
        raise UnauthorizedError(detail="No valid OTP found for this phone number")

    # Increment attempts
    otp.attempts += 1

    if otp.attempts > settings.OTP_MAX_ATTEMPTS:
        otp.is_used = True  # burn the OTP
        await db.flush()
        await otp_brute_force_protector.record_failure(phone, ip=ip_address)
        raise RateLimitError(detail="Maximum OTP verification attempts exceeded")

    if otp.code != code:
        await db.flush()
        await otp_brute_force_protector.record_failure(phone, ip=ip_address)
        raise UnauthorizedError(detail="Invalid OTP code")

    # OTP is valid - clear failure counter
    await otp_brute_force_protector.record_success(phone)

    # Mark as used
    otp.is_used = True
    await db.flush()

    # Find or create user
    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()

    if user is None:
        # OTP-based registration
        user = User(phone=phone, is_active=True, is_verified=True)
        db.add(user)
        await db.flush()

        profile = UserProfile(user_id=user.id)
        db.add(profile)

        # Assign customer role
        role_result = await db.execute(select(Role).where(Role.slug == "customer"))
        role = role_result.scalar_one_or_none()
        if role is None:
            role = Role(name="Customer", slug="customer", is_system=True)
            db.add(role)
            await db.flush()

        user_role = UserRole(user_id=user.id, role_id=role.id)
        db.add(user_role)
        await db.flush()

        await log_action(
            db,
            actor_id=user.id,
            action="user.register_otp",
            resource="user",
            resource_id=user.id,
            after={"phone": phone},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    else:
        # Mark as verified if not already
        if not user.is_verified:
            user.is_verified = True
        user.last_login = datetime.now(UTC)
        await db.flush()

    tokens = await _create_token_pair(
        db, user, ip_address=ip_address, user_agent=user_agent,
    )

    await log_action(
        db,
        actor_id=user.id,
        action="user.otp_verified",
        resource="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    await logger.ainfo("otp_verified", user_id=str(user.id), phone=phone)
    return tokens


async def refresh_token(
    db: AsyncSession,
    *,
    token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Rotate a refresh token: revoke the old session and issue a new pair."""
    payload = verify_token(token, expected_type="refresh")
    user_id = uuid.UUID(payload["sub"])

    # Find the session by refresh token
    stmt = select(UserSession).where(
        UserSession.refresh_token == token,
        UserSession.is_revoked.is_(False),
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise UnauthorizedError(detail="Invalid or revoked refresh token")

    if session.expires_at < datetime.now(UTC):
        session.is_revoked = True
        await db.flush()
        raise UnauthorizedError(detail="Refresh token has expired")

    # Revoke old session
    session.is_revoked = True
    await db.flush()

    # Fetch user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError(detail="User account not found or inactive")

    # Issue new pair
    tokens = await _create_token_pair(
        db, user, ip_address=ip_address, user_agent=user_agent,
    )

    await logger.ainfo("token_refreshed", user_id=str(user_id))
    return tokens


async def logout(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None = None,
    refresh_token_str: str | None = None,
) -> None:
    """Revoke a single session.

    Either ``session_id`` or ``refresh_token_str`` can be used to identify
    the session to revoke.
    """
    if session_id is not None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
    elif refresh_token_str is not None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.refresh_token == refresh_token_str,
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
    else:
        # Revoke the most recent active session
        sub = (
            select(UserSession.id)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .order_by(UserSession.created_at.desc())
            .limit(1)
        )
        result = await db.execute(sub)
        sid = result.scalar_one_or_none()
        if sid is None:
            return
        stmt = (
            update(UserSession)
            .where(UserSession.id == sid)
            .values(is_revoked=True)
        )

    await db.execute(stmt)
    await db.flush()

    await log_action(
        db,
        actor_id=user_id,
        action="user.logout",
        resource="user_session",
        resource_id=session_id,
    )

    await logger.ainfo("user_logged_out", user_id=str(user_id))


async def logout_all(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Revoke all active sessions for a user.  Returns count of revoked sessions."""
    stmt = (
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
        )
        .values(is_revoked=True)
    )
    result = await db.execute(stmt)
    await db.flush()

    count = result.rowcount  # type: ignore[union-attr]

    await log_action(
        db,
        actor_id=user_id,
        action="user.logout_all",
        resource="user_session",
        after={"revoked_count": count},
    )

    await logger.ainfo("user_logged_out_all", user_id=str(user_id), revoked=count)
    return count


async def get_me(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """Return the current user's data merged with their profile."""
    stmt = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(resource="User")

    profile = user.profile
    roles = await _get_user_role_slugs(db, user.id)

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
        "roles": roles,
        "created_at": user.created_at,
    }


async def update_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Update the authenticated user's profile fields."""
    # Separate user-level and profile-level fields
    user_fields = {}
    profile_fields = {}

    if "email" in data and data["email"] is not None:
        # Check uniqueness
        existing = await db.execute(
            select(User).where(User.email == data["email"], User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(detail="Email already in use")
        user_fields["email"] = data["email"]

    profile_keys = {"first_name", "last_name", "national_code", "birth_date", "avatar_url", "gender"}
    for key in profile_keys:
        if key in data and data[key] is not None:
            profile_fields[key] = data[key]

    # Fetch before snapshot
    before = await get_me(db, user_id=user_id)

    # Update user table
    if user_fields:
        await db.execute(
            update(User).where(User.id == user_id).values(**user_fields)
        )

    # Update or create profile
    if profile_fields:
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user_id, **profile_fields)
            db.add(profile)
        else:
            for key, value in profile_fields.items():
                setattr(profile, key, value)

    await db.flush()

    after_data = await get_me(db, user_id=user_id)

    await log_action(
        db,
        actor_id=user_id,
        action="user.profile_updated",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    await logger.ainfo("profile_updated", user_id=str(user_id))
    return after_data


async def change_password(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    old_password: str,
    new_password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Change the current user's password after verifying the old one."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(resource="User")

    if user.password_hash is None:
        raise ValidationError(
            detail="Cannot change password for OTP-only account. Set a password first."
        )

    if not verify_password(old_password, user.password_hash):
        raise UnauthorizedError(detail="Current password is incorrect")

    user.password_hash = hash_password(new_password)
    await db.flush()

    await log_action(
        db,
        actor_id=user_id,
        action="user.password_changed",
        resource="user",
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    await logger.ainfo("password_changed", user_id=str(user_id))


async def get_sessions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[UserSession]:
    """List all active (non-revoked) sessions for the current user."""
    stmt = (
        select(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
        )
        .order_by(UserSession.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    """Revoke a specific session belonging to the user."""
    stmt = (
        update(UserSession)
        .where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
        )
        .values(is_revoked=True)
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:  # type: ignore[union-attr]
        raise NotFoundError(resource="Session")

    await db.flush()

    await log_action(
        db,
        actor_id=user_id,
        action="user.session_revoked",
        resource="user_session",
        resource_id=session_id,
    )

    await logger.ainfo("session_revoked", user_id=str(user_id), session_id=str(session_id))
