"""Authentication business-logic service.

Handles registration, login, OTP flow, token refresh, session management,
profile retrieval / update, and password changes.
"""

from __future__ import annotations

import hashlib
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import CursorResult, func, select, update
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
from app.core.security.mfa import generate_totp_secret, get_totp_uri, verify_totp_code
from app.core.security.password import hash_password, verify_dummy_password, verify_password
from app.core.security.rate_limiter import (
    brute_force_protector,
    otp_brute_force_protector,
)
from app.modules.audit.application.audit_service import log_action
from app.modules.rbac.domain.models import Permission, Role, RolePermission, UserRole
from app.modules.users.domain.models import (
    OTPRequest,
    PasswordResetToken,
    User,
    UserProfile,
    UserSession,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.domain.kyc_models import AttemptType

logger: structlog.stdlib.BoundLogger = structlog.get_logger()
settings = get_settings()


async def _persist_failed_attempt(
    db: AsyncSession,
    identifier: str,
    attempt_type: Any,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Write a persistent ``failed_attempts`` row for security monitoring.

    Complements the Redis brute-force lockout (Karta failed_attempts, P1.4):
    the admin panel reads these rows. Best-effort — an audit-write failure
    must never break the authentication flow.
    """
    try:
        from app.modules.users.application.kyc_service import record_failed_attempt
        from app.modules.users.domain.kyc_models import AttemptType

        safe_type = (
            attempt_type if isinstance(attempt_type, AttemptType) else AttemptType(attempt_type)
        )
        await record_failed_attempt(
            db,
            identifier=identifier,
            attempt_type=safe_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        await logger.awarning(
            "failed_attempt_persist_skipped",
            identifier=identifier,
            attempt_type=str(attempt_type),
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP code."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


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


def _hash_refresh_token(token: str) -> str:
    """SHA-256 of a refresh token.

    Sessions persist only the hash: the raw token is the credential, so a
    database leak must not yield usable sessions. Lookup is by hash — the
    token entropy is high, so a fast digest is appropriate (no bcrypt).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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

    refresh = create_refresh_token(subject=user.id)

    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session = UserSession(
        user_id=user.id,
        refresh_token=_hash_refresh_token(refresh),
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(session)
    # Flush before minting the access token so the row's id exists: the claim
    # below is the only thing that lets ``/auth/logout`` know *which* session
    # the caller is ending. Without it the handler fell back to revoking the
    # most recent session, so logging out of an older device killed somebody
    # else's session and left the caller's refresh token alive.
    await db.flush()

    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "permissions": permissions,
            "roles": roles,
            "is_superuser": bool(user.is_superuser),
            "sid": str(session.id),
        },
    )

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
    referral_code: str | None = None,
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

    # 4b. Record the referral relationship when a valid invite code was used.
    # A bad/expired code never fails registration — the account is still
    # created, the referral is simply not recorded.
    if referral_code:
        try:
            from app.modules.referrals.application.referral_service import (
                ReferralService,
            )

            referrer_id = await ReferralService.resolve_referrer_by_code(db, referral_code)
            if referrer_id is not None and referrer_id != user.id:
                await ReferralService.track_referral(
                    db,
                    referrer_id=referrer_id,
                    referred_id=user.id,
                    code=referral_code.upper().strip(),
                )
        except Exception as exc:
            await logger.awarning(
                "referral_tracking_skipped",
                error=str(exc),
                user_id=str(user.id),
            )

    # 5. Tokens
    tokens = await _create_token_pair(
        db,
        user,
        ip_address=ip_address,
        user_agent=user_agent,
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

    # Automation rules (fire-and-forget): registration must never fail on
    # the automation engine, so enqueue failures are logged and dropped.
    try:
        from app.modules.automation.application.tasks import queue_automation_trigger

        queue_automation_trigger(
            "user_registered",
            {
                "user_id": str(user.id),
                "phone": phone,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
    except Exception as exc:
        await logger.awarning("automation_trigger_dispatch_skipped", error=str(exc))

    await logger.ainfo("user_registered", user_id=str(user.id), phone=phone)
    return tokens


async def login(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    totp_code: str | None = None,
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
        await _persist_failed_attempt(
            db, phone, AttemptType.LOGIN, ip_address, user_agent
        )
        raise UnauthorizedError(detail="Invalid phone or password")

    if not verify_password(password, user.password_hash):
        await brute_force_protector.record_failure(phone, ip=ip_address)
        await _persist_failed_attempt(
            db, phone, AttemptType.LOGIN, ip_address, user_agent
        )
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

    # TOTP second factor: when enabled, a valid code is part of the same
    # login request. The brute-force protector above also throttles code
    # guessing (6 digits + password possession required).
    code_ok = bool(
        totp_code and user.totp_secret and verify_totp_code(user.totp_secret, totp_code)
    )
    if user.totp_enabled and not code_ok:
        await brute_force_protector.record_failure(phone, ip=ip_address)
        await _persist_failed_attempt(
            db, phone, AttemptType.LOGIN, ip_address, user_agent
        )
        raise ValidationError(
            detail="کد دو مرحله‌ای (TOTP) الزامی است یا نامعتبر است",
            error_code="MFA_CODE_REQUIRED",
        )

    if not user.is_active:
        raise UnauthorizedError(detail="Account is deactivated")

    # Clear brute-force failure counter on successful authentication
    await brute_force_protector.record_success(phone)

    # Update last login
    user.last_login = datetime.now(UTC)
    await db.flush()

    tokens = await _create_token_pair(
        db,
        user,
        ip_address=ip_address,
        user_agent=user_agent,
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
    cooldown_threshold = datetime.now(UTC) - timedelta(seconds=settings.OTP_COOLDOWN_SECONDS)
    recent_stmt = select(OTPRequest).where(
        OTPRequest.phone == phone,
        OTPRequest.purpose == purpose,
        OTPRequest.created_at >= cooldown_threshold,
        OTPRequest.is_used.is_(False),
    )
    recent = await db.execute(recent_stmt)
    if recent.scalar_one_or_none() is not None:
        raise RateLimitError(
            detail=f"Please wait {settings.OTP_COOLDOWN_SECONDS} seconds before requesting a new OTP"  # noqa: E501
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
        await _persist_failed_attempt(
            db, phone, AttemptType.OTP, ip_address, user_agent
        )
        raise RateLimitError(detail="Maximum OTP verification attempts exceeded")

    if otp.code != code:
        await db.flush()
        await otp_brute_force_protector.record_failure(phone, ip=ip_address)
        await _persist_failed_attempt(
            db, phone, AttemptType.OTP, ip_address, user_agent
        )
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
        # A blocked (is_active=False) or soft-deleted user must not be able
        # to mint a fresh token via OTP — the password login path enforces
        # the same gate (see login), and the admin block feature depends on
        # it: revocation is only as strong as the DB state, not just Redis.
        if not user.is_active:
            raise UnauthorizedError(detail="Account is deactivated")

        # Mark as verified if not already
        if not user.is_verified:
            user.is_verified = True
        user.last_login = datetime.now(UTC)
        await db.flush()

    tokens = await _create_token_pair(
        db,
        user,
        ip_address=ip_address,
        user_agent=user_agent,
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

    # Find the session by refresh token (revoked included: presenting a
    # revoked token is a reuse event, not just an invalid one).
    stmt = select(UserSession).where(UserSession.refresh_token == _hash_refresh_token(token))
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise UnauthorizedError(detail="Invalid or revoked refresh token")

    # ── Refresh-token reuse detection (TASK P11-04) ────────────────────
    # A revoked token being presented again means either a stolen token
    # whose rotation already happened, or a replay. Defensive response:
    # revoke every active session of the user and raise a security event.
    if session.is_revoked:
        revoke_stmt = select(UserSession).where(
            UserSession.user_id == session.user_id,
            UserSession.is_revoked.is_(False),
        )
        active_sessions = (await db.execute(revoke_stmt)).scalars().all()
        for active in active_sessions:
            active.is_revoked = True
        await db.flush()
        from app.core.logging.security_audit import log_security_event

        log_security_event(
            event="auth.refresh_token_reuse_detected",
            ip_address=ip_address,
            identifier=str(session.user_id),
            success=False,
            reason="revoked refresh token replayed; all sessions revoked",
            user_agent=user_agent,
        )
        await logger.aerror(
            "refresh_token_reuse_detected",
            user_id=str(session.user_id),
        )
        raise UnauthorizedError(
            detail="Refresh token reuse detected; all sessions have been revoked"
        )

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
        db,
        user,
        ip_address=ip_address,
        user_agent=user_agent,
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
    the session to revoke. The access token carries its session id in the
    ``sid`` claim for exactly this reason — without one of the two, the only
    available choice was the most recent session, which is the wrong one
    whenever the caller is on an older device.
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
                UserSession.refresh_token == _hash_refresh_token(refresh_token_str),
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
        stmt = update(UserSession).where(UserSession.id == sid).values(is_revoked=True)

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
    result = cast("CursorResult[Any]", await db.execute(stmt))
    await db.flush()

    count = int(result.rowcount or 0)

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
    stmt = select(User).options(selectinload(User.profile)).where(User.id == user_id)
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
        "totp_enabled": user.totp_enabled,
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

    profile_keys = {
        "first_name",
        "last_name",
        "national_code",
        "birth_date",
        "avatar_url",
        "gender",
    }
    for key in profile_keys:
        if key in data and data[key] is not None:
            profile_fields[key] = data[key]

    # Fetch before snapshot
    before = await get_me(db, user_id=user_id)

    # Update user table
    if user_fields:
        await db.execute(update(User).where(User.id == user_id).values(**user_fields))

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

    # Email is deliberately NOT written above. Password reset travels by email,
    # so replacing the address inline was a takeover path: point the account at
    # an inbox you control, then trigger a reset. The change is proposed here
    # and a confirmation link goes to the *new* address; `User.email` moves only
    # when that link is redeemed, so a reset issued in the meantime still goes to
    # the address the account really owns.
    #
    # Run after the profile write so a mail failure cannot roll back the name
    # change the user also asked for.
    email_change: dict[str, Any] | None = None
    if "email" in data and data["email"] is not None:
        from app.modules.users.application.email_change_service import (
            EmailChangeError,
            request_email_change,
        )

        try:
            email_change = await request_email_change(
                db,
                user_id=user_id,
                new_email=data["email"],
                request_ip=ip_address,
            )
        except EmailChangeError as exc:
            # The profile edits above are already staged. Commit them, then
            # report the email problem: silently discarding a name change because
            # the address was taken would be its own kind of wrong.
            await db.commit()
            raise ConflictError(detail=exc.message) from exc

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
    if email_change is not None:
        # Surfaced so the client can say "check your inbox" instead of showing
        # the old address as if nothing had happened.
        after_data = {**after_data, "email_change": email_change}
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

    # Security: a password rotation must invalidate every existing session —
    # otherwise a stolen refresh token survives the rotation. The user signs
    # in again on all devices, including the current one.
    revoked_sessions = await logout_all(db, user_id=user_id)

    await log_action(
        db,
        actor_id=user_id,
        action="user.password_changed",
        resource="user",
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        after={"revoked_sessions": revoked_sessions},
    )

    await logger.ainfo("password_changed", user_id=str(user_id), revoked_sessions=revoked_sessions)


# ── TOTP MFA enrollment ───────────────────────────────────────────────────


async def setup_totp(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, str]:
    """Start (or restart) TOTP enrollment: store a pending secret.

    The secret only starts gating logins once ``confirm_totp`` succeeds, so
    an abandoned setup can never lock the account out.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(resource="User")
    if user.totp_enabled:
        raise ConflictError(detail="TOTP از قبل فعال است؛ ابتدا آن را غیرفعال کنید")

    secret = generate_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = False
    await db.flush()

    account_name = user.phone or str(user_id)
    return {"secret": secret, "otpauth_uri": get_totp_uri(secret, account_name=account_name)}


async def confirm_totp(db: AsyncSession, *, user_id: uuid.UUID, code: str) -> None:
    """Confirm a pending TOTP enrollment with a valid code, enabling MFA."""
    from app.core.security.rate_limiter import totp_brute_force_protector

    totp_key = f"totp:{user_id}"
    await totp_brute_force_protector.check_lockout(totp_key)

    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(resource="User")
    if user.totp_enabled:
        raise ConflictError(detail="TOTP از قبل فعال است")
    if not user.totp_secret:
        raise ValidationError(
            detail="ابتدا راه‌اندازی TOTP را آغاز کنید",
            error_code="MFA_NOT_SETUP",
        )
    if not verify_totp_code(user.totp_secret, code):
        await totp_brute_force_protector.record_failure(totp_key)
        raise ValidationError(detail="کد TOTP نامعتبر است", error_code="MFA_CODE_INVALID")

    await totp_brute_force_protector.record_success(totp_key)
    user.totp_enabled = True
    await db.flush()
    await log_action(
        db,
        actor_id=user_id,
        action="user.mfa_enabled",
        resource="user",
        resource_id=user_id,
    )
    await logger.ainfo("totp_mfa_enabled", user_id=str(user_id))


async def disable_totp(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    code: str,
    password: str,
) -> None:
    """Disable TOTP MFA; requires both the current code and the password."""
    from app.core.security.rate_limiter import totp_brute_force_protector

    totp_key = f"totp:{user_id}"
    await totp_brute_force_protector.check_lockout(totp_key)

    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(resource="User")
    if not user.totp_enabled:
        raise ValidationError(detail="TOTP فعال نیست", error_code="MFA_NOT_ENABLED")
    if user.password_hash is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError(detail="Current password is incorrect")
    if not user.totp_secret or not verify_totp_code(user.totp_secret, code):
        await totp_brute_force_protector.record_failure(totp_key)
        raise ValidationError(detail="کد TOTP نامعتبر است", error_code="MFA_CODE_INVALID")

    await totp_brute_force_protector.record_success(totp_key)
    user.totp_enabled = False
    user.totp_secret = None
    await db.flush()
    await log_action(
        db,
        actor_id=user_id,
        action="user.mfa_disabled",
        resource="user",
        resource_id=user_id,
    )
    await logger.ainfo("totp_mfa_disabled", user_id=str(user_id))


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
    result = cast("CursorResult[Any]", await db.execute(stmt))
    if (result.rowcount or 0) == 0:
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


# ── Password reset (lost password) ──────────────────────────────────────────

#: How long a reset link stays usable. WordPress default is 24h; the shorter
#: window here matches the OTP flow and limits the value of a leaked inbox.
PASSWORD_RESET_TTL_MINUTES = 30


def _hash_reset_token(token: str) -> str:
    """SHA-256 of a reset token. The plaintext is never stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _reset_link(token: str) -> str:
    return f"{settings.STOREFRONT_BASE_URL.rstrip('/')}/reset-password?token={token}"


async def request_password_reset(
    db: AsyncSession,
    *,
    email: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Email a reset link when the address belongs to a password account.

    Returns None whether or not a mail was sent: the caller always answers
    with the same response, so this endpoint cannot be used to enumerate which
    addresses have accounts. The timing is padded by the caller-side rate
    limit rather than by an artificial delay here.
    """
    normalized = (email or "").strip().lower()
    if not normalized:
        return

    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized)
    )
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        # No account, or an OTP-only account that has no password to reset.
        logger.info("password_reset_noop", reason="no_password_account")
        return

    # Any previously issued token is voided: only the newest link works, so an
    # older email sitting in an inbox cannot be replayed. The UPDATE is flushed
    # before the new row is added — an unflushed ORM identity map would leave
    # the old row readable in this same transaction.
    now = datetime.now(UTC)
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    await db.flush()

    token = secrets.token_urlsafe(48)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(token),
            expires_at=now + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
            request_ip=ip_address,
        )
    )
    await db.flush()

    try:
        from app.modules.notifications.application.email_service import send_email

        await send_email(
            db,
            recipient=normalized,
            subject="بازیابی رمز عبور",
            text_body=(
                "برای بازنشانی رمز عبور خود روی پیوند زیر کلیک کنید:\n\n"
                f"{_reset_link(token)}\n\n"
                f"این پیوند تا {PASSWORD_RESET_TTL_MINUTES} دقیقه معتبر است. "
                "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
            ),
            html_body=(
                "<p>برای بازنشانی رمز عبور خود روی پیوند زیر کلیک کنید:</p>"
                f'<p><a href="{_reset_link(token)}">بازیابی رمز عبور</a></p>'
                f"<p>این پیوند تا {PASSWORD_RESET_TTL_MINUTES} دقیقه معتبر است. "
                "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید.</p>"
            ),
        )
    except Exception as exc:  # a mail outage must not 500 the request
        logger.warning("password_reset_email_failed", user_id=str(user.id), error=str(exc))

    await log_action(
        db,
        actor_id=user.id,
        action="user.password_reset_requested",
        resource="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await logger.ainfo("password_reset_requested", user_id=str(user.id))


async def reset_password(
    db: AsyncSession,
    *,
    token: str,
    new_password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Consume a reset token and set a new password.

    The token is marked used before the password is written, and every session
    is revoked: whoever prompted the reset must not keep an old session alive,
    and a stolen token cannot be replayed after one successful use.
    """
    if not token:
        raise ValidationError(detail="توکن بازیابی نامعتبر است")

    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_reset_token(token)
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(UTC)

    if row is None or row.used_at is not None or row.expires_at <= now:
        raise UnauthorizedError(detail="توکن بازیابی نامعتبر یا منقضی شده است")

    user_result = await db.execute(select(User).where(User.id == row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(resource="User")

    row.used_at = now
    user.password_hash = hash_password(new_password)
    await db.flush()

    revoked_sessions = await logout_all(db, user_id=user.id)

    await log_action(
        db,
        actor_id=user.id,
        action="user.password_reset",
        resource="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        after={"revoked_sessions": revoked_sessions},
    )
    await logger.ainfo("password_reset_completed", user_id=str(user.id))
