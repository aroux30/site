"""Authentication API routes."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_active_user,
    get_current_user,
    get_current_user_id,
)
from app.core.security.mfa import (
    get_webauthn_registration_challenge,
)
from app.core.security.rate_limiter import limiter
from app.modules.auth.application import auth_service
from app.modules.auth.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    ApplicationPasswordCreate,
    ApplicationPasswordCreatedResponse,
    ApplicationPasswordResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    OTPRequestSchema,
    OTPVerifySchema,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter()

# The application-password endpoints call `logger.ainfo(...)` but this module
# never defined a logger, so issuing or revoking a password raised NameError
# and 500'd. Declared here to match the convention used by the other route
# modules.
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_settings = get_settings()


def _is_secure_request(request: Request | None) -> bool:
    if request is not None:
        proto = request.headers.get("x-forwarded-proto", "")
        if proto == "https" or request.url.scheme == "https":
            return True
        if proto == "http" or request.url.scheme == "http":
            return False
    return _settings.ENVIRONMENT == "production"


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    request: Request | None = None,
) -> None:
    """Set auth cookies on root path.

    Both cookies are HttpOnly: JavaScript never needs to read them because
    the login/refresh responses carry the tokens in the body, and session
    detection on the client is driven by /auth/me responses — not by cookie
    presence. An XSS that can read cookies is strictly worse than one that
    cannot, so JS-readability was not granted.
    """
    is_secure = _is_secure_request(request)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
        max_age=_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
        max_age=_settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def _clear_auth_cookies(response: Response, request: Request | None = None) -> None:
    """Clear auth cookies by setting max_age=0."""
    is_secure = _is_secure_request(request)
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
        max_age=0,
    )
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
        max_age=0,
    )


def _client_ip(request: Request) -> str | None:
    """Extract client IP from the request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _client_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


# ── Registration & Login ─────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=TokenResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@limiter.limit(_settings.RATE_LIMIT_REGISTER)
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.register(
        db,
        phone=body.phone,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        referral_code=body.referral_code,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"], request)
    tokens.pop("access_token", None)
    return TokenResponse(**tokens)


@router.post(
    "/login",
    response_model=TokenResponse,
    response_model_exclude_none=True,
    summary="Login with phone and password",
)
@limiter.limit(_settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.login(
        db,
        phone=body.phone,
        password=body.password,
        totp_code=body.totp_code,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"], request)
    tokens.pop("access_token", None)
    return TokenResponse(**tokens)


# ── SSO (OIDC) ───────────────────────────────────────────────────────────────


@router.get(
    "/sso/google",
    summary="Start Google SSO login (redirects to Google consent)",
)
@limiter.limit("10/minute")
async def sso_google_start(
    request: Request,
    return_url: str | None = None,
) -> Response:
    from fastapi.responses import RedirectResponse

    from app.modules.auth.application import sso_service

    url = await sso_service.start_google_login(return_url)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/sso/google/callback",
    summary="Google SSO callback (code + state)",
)
@limiter.limit("20/minute")
async def sso_google_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.modules.auth.application import sso_service

    tokens, return_url = await sso_service.complete_google_login(
        db,
        code=code,
        state=state,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"], request)

    # Google always delivers the user back in a browser — land on a
    # storefront route carrying the auth cookies, never on bare JSON.
    from fastapi.responses import RedirectResponse

    redirect = RedirectResponse(return_url, status_code=status.HTTP_302_FOUND)
    _set_auth_cookies(redirect, tokens["access_token"], tokens["refresh_token"], request)
    return redirect


# ── OTP ──────────────────────────────────────────────────────────────────────


@router.post(
    "/otp/request",
    status_code=status.HTTP_200_OK,
    summary="Request a one-time password",
)
@limiter.limit(_settings.RATE_LIMIT_OTP_REQUEST)
async def otp_request(
    request: Request,
    body: OTPRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await auth_service.request_otp(
        db,
        phone=body.phone,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )


@router.post(
    "/otp/verify",
    response_model=TokenResponse,
    summary="Verify OTP and get tokens",
)
@limiter.limit(_settings.RATE_LIMIT_OTP_VERIFY)
async def otp_verify(
    request: Request,
    body: OTPVerifySchema,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.verify_otp(
        db,
        phone=body.phone,
        code=body.code,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"], request)
    return TokenResponse(**tokens)


# ── Token Management ─────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
@limiter.limit(_settings.RATE_LIMIT_REFRESH)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshTokenRequest | None = None,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> TokenResponse:
    token = (body.refresh_token if body and body.refresh_token else None) or refresh_token
    if not token:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
        )
    tokens = await auth_service.refresh_token(
        db,
        token=token,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"], request)
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (revoke current session)",
)
async def logout(
    request: Request,
    response: Response,
    payload: dict[str, Any] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.core.security.revocation import denylist_jti

    user_id = uuid.UUID(payload["sub"])
    jti = payload.get("jti")
    if jti:
        await denylist_jti(jti)

    # ``sid`` identifies *this* device's session. Without it the service
    # revoked the most recent session, so logging out on a second device
    # killed the first one's session and left the caller's own refresh token
    # alive — they silently refreshed straight back in.
    session_id = payload.get("sid")
    session_uuid: uuid.UUID | None = None
    if session_id:
        try:
            session_uuid = uuid.UUID(str(session_id))
        except (ValueError, AttributeError, TypeError):
            # A malformed or non-string claim is ignored rather than fatal:
            # logout must always clear the cookie, even for a token minted
            # before this claim existed.
            session_uuid = None

    await auth_service.logout(db, user_id=user_id, session_id=session_uuid)
    _clear_auth_cookies(response, request)
    return MessageResponse(message="Logged out successfully")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Logout from all sessions",
)
async def logout_all(
    payload: dict[str, Any] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.core.security.revocation import denylist_user

    user_id = uuid.UUID(payload["sub"])
    await denylist_user(user_id)
    count = await auth_service.logout_all(db, user_id=user_id)
    return MessageResponse(message=f"Revoked {count} session(s)")


# ── Current User (Me) ────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    data = await auth_service.get_me(db, user_id=user_id)
    return UserProfileResponse(**data)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user profile",
)
async def update_me(
    body: UserProfileUpdate,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    update_data = body.model_dump(exclude_unset=True)
    data = await auth_service.update_profile(
        db,
        user_id=user_id,
        data=update_data,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return UserProfileResponse(**data)


@router.post(
    "/me/email/confirm",
    summary="Confirm an email change with the token from the confirmation link",
)
async def confirm_email_change(
    body: dict[str, str],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Redeem a confirmation link and move the account's address.

    Not authenticated on purpose. The token is the credential: it arrives by
    email to the *new* address, which is exactly the proof being asked for, and
    requiring a login first would break the flow for a user whose session has
    expired since they requested the change. The token is single-use, hashed at
    rest and short-lived, so possession of it is the authorisation.

    Every failure answers 400 with a specific reason, because "invalid link" for
    an expired one and an already-used one leaves the user re-clicking something
    that can never work.
    """
    from fastapi import HTTPException as _HTTPException

    from app.modules.users.application.email_change_service import (
        EmailChangeError,
        confirm_email_change as _confirm,
    )

    token = (body.get("token") or "").strip()
    if not token:
        raise _HTTPException(status_code=400, detail="توکن تأیید ارسال نشده است.")

    try:
        return await _confirm(db, token=token)
    except EmailChangeError as exc:
        raise _HTTPException(status_code=400, detail=exc.message) from exc


@router.get(
    "/me/email/pending",
    summary="The outstanding email-change proposal, if any",
)
async def pending_email_change(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Lets the account screen say "we sent a link to x@y.com" after a refresh."""
    from app.modules.users.application.email_change_service import (
        get_pending_email_change,
    )

    return await get_pending_email_change(db, user_id=user_id)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change current user password",
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.change_password(
        db,
        user_id=user_id,
        old_password=body.old_password,
        new_password=body.new_password,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return MessageResponse(message="Password changed successfully")


# ── Password reset (lost password) ──────────────────────────────────────────


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Request a password reset link",
)
@limiter.limit(_settings.RATE_LIMIT_PASSWORD_RESET_REQUEST)
async def forgot_password(
    request: Request,
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Always answers the same way, whether or not the address exists.

    A different answer (or a different status) would turn this endpoint into a
    membership oracle for registered email addresses.
    """
    await auth_service.request_password_reset(
        db,
        email=body.email,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return MessageResponse(
        message="اگر این ایمیل در سامانه ثبت شده باشد، پیوند بازیابی ارسال شد."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Redeem a reset token and set a new password",
)
@limiter.limit(_settings.RATE_LIMIT_PASSWORD_RESET_CONFIRM)
async def reset_password(
    request: Request,
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.reset_password(
        db,
        token=body.token,
        new_password=body.new_password,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return MessageResponse(
        message="رمز عبور تغییر کرد. لطفاً دوباره وارد شوید."
    )


# ── Session Management ───────────────────────────────────────────────────────


@router.get(
    "/sessions",
    summary="List active sessions",
)
async def list_sessions(
    payload: dict[str, Any] = Depends(get_current_user),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    sessions = await auth_service.get_sessions(db, user_id=user_id)
    current_sid = payload.get("sid")
    return [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "device_info": s.device_info,
            # The client renders a "this device" marker off this, and without
            # it a user cannot tell which row to leave alone. The sid comes from
            # the access token, so it identifies the caller's own session
            # exactly — a token minted before the claim existed simply has none
            # and every row reads as "not current".
            "is_current": bool(current_sid) and str(s.id) == str(current_sid),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            # The column is never written, so this is always null; the client
            # type declares it. Kept explicit rather than dropped so the two
            # sides stay visibly in step.
            "last_active_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
    summary="Revoke a specific session",
)
async def delete_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.revoke_session(db, user_id=user_id, session_id=session_id)
    return MessageResponse(message="Session revoked successfully")


# ── Multi-Factor Authentication (MFA / TOTP / Passkeys) ─────────────────────


@router.post(
    "/mfa/totp/setup",
    response_model=MFASetupResponse,
    summary="Start TOTP enrollment: generate and persist a pending secret",
)
async def setup_totp(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MFASetupResponse:
    result = await auth_service.setup_totp(db, user_id=user_id)
    return MFASetupResponse(
        secret=result["secret"],
        otpauth_uri=result["otpauth_uri"],
        backup_codes=[],
    )


@router.post(
    "/mfa/totp/verify",
    response_model=MessageResponse,
    summary="Confirm a pending TOTP enrollment with a valid code",
)
async def verify_totp(
    body: MFAVerifyRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.confirm_totp(db, user_id=user_id, code=body.code)
    return MessageResponse(message="TOTP verification successful")


@router.post(
    "/mfa/totp/disable",
    response_model=MessageResponse,
    summary="Disable TOTP MFA (requires current code and password)",
)
async def disable_totp(
    body: MFADisableRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.disable_totp(db, user_id=user_id, code=body.code, password=body.password)
    return MessageResponse(message="TOTP MFA disabled")


@router.post(
    "/mfa/passkey/register/options",
    summary="Generate WebAuthn registration options challenge",
)
async def passkey_register_options(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    return get_webauthn_registration_challenge(
        user_id=str(user_id),
        username=str(user_id),
    )


# ── Security Posture & Defense Status ────────────────────────────────────────


@router.get(
    "/security-status",
    summary="Get active defense systems and security posture status",
    # Defense-inventory details (engines, limits, lockout windows) are an
    # attacker's roadmap — superuser eyes only.
    dependencies=[Depends(RequirePermissions("admin:access"))],
)
async def get_security_status() -> dict[str, Any]:
    from app.core.security.casbin_enforcer import get_casbin_enforcer
    from app.core.security.rate_limiter import brute_force_protector

    casbin_active = False
    try:
        e = get_casbin_enforcer()
        casbin_active = e is not None
    except Exception:
        casbin_active = False

    return {
        "status": "healthy",
        "active_defenses": {
            "rate_limiter": {
                "engine": "SlowAPI + Redis moving-window",
                "status": "active",
            },
            "brute_force_protector": {
                "engine": "Multi-Key Redis Sliding Window",
                "max_attempts": brute_force_protector.max_attempts,
                "lockout_seconds": brute_force_protector.lockout_seconds,
                "progressive_delay": "active (0.5s - 2.5s backoff)",
            },
            "casbin_rbac_abac": {
                "status": "active" if casbin_active else "inactive",
                "model": "rbac_model.conf",
                "policy_file": "rbac_policy.csv",
            },
            "mfa_passkeys": {
                "totp_2fa": "available (PyOTP) — per-user enrollment via /auth/mfa/totp/setup",
                # Only /mfa/passkey/register/options is implemented, and it
                # returns a random challenge that nothing ever verifies. There
                # is no credential storage and no assertion path, so passkeys
                # are a non-functional stub — do not advertise them as active.
                "fido2_webauthn": "not implemented (registration options challenge only; no verification or credential storage)",
            },
            "anti_bot": {
                "honeypot_field": "active on Register & Login",
                "nginx_bad_bot_map": "active (SQLMap, Nikto, DirBuster blocked)",
                "connection_limit": "active (30 conn/ip)",
            },
            "data_protection": {
                "password_hashing": "Argon2id (64MB memory, 4 rounds)",
                "weak_password_blacklist": "active",
                "xss_sanitization": "DOMPurify active",
                "csrf_origin_check": "active in Next.js middleware",
            },
        },
    }


# ── Application passwords (WordPress parity) ────────────────────────────────
# A personal API client (phone app, script) authenticates with one of these
# instead of the account password, so the real password never leaves the
# password field and each client is revoked on its own.


@router.get(
    "/application-passwords",
    response_model=list[ApplicationPasswordResponse],
    summary="List the current user's application passwords",
)
async def list_application_passwords(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationPasswordResponse]:
    from app.modules.auth.application.application_password_service import (
        list_application_passwords as _list,
    )

    rows = await _list(db, user_id=user_id)
    return [ApplicationPasswordResponse.model_validate(r) for r in rows]


@router.post(
    "/application-passwords",
    response_model=ApplicationPasswordCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an application password",
)
async def create_application_password(
    body: ApplicationPasswordCreate,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApplicationPasswordCreatedResponse:
    from app.modules.auth.application.application_password_service import (
        create_application_password as _create,
    )

    row, token = await _create(
        db,
        user_id=user_id,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
    )
    await logger.ainfo(
        "application_password_issued",
        actor_id=str(user_id),
        ip_address=_client_ip(request),
    )
    return ApplicationPasswordCreatedResponse(
        **ApplicationPasswordResponse.model_validate(row).model_dump(),
        token=token,
    )


@router.post(
    "/application-passwords/revoke-all",
    summary="Revoke every application password for the current user",
)
async def revoke_all_application_passwords(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    from app.modules.auth.application.application_password_service import (
        revoke_all_application_passwords as _revoke_all,
    )

    count = await _revoke_all(db, user_id=user_id)
    await logger.ainfo(
        "application_passwords_revoked_all",
        actor_id=str(user_id),
        ip_address=_client_ip(request),
        revoked=count,
    )
    return {"revoked": count}


@router.delete(
    "/application-passwords/{app_password_id}",
    response_model=ApplicationPasswordResponse,
    summary="Revoke an application password",
)
async def revoke_application_password(
    app_password_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApplicationPasswordResponse:
    from app.modules.auth.application.application_password_service import (
        revoke_application_password as _revoke,
    )

    row = await _revoke(db, user_id=user_id, app_password_id=app_password_id)
    return ApplicationPasswordResponse.model_validate(row)

