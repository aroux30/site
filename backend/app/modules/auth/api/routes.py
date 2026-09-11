"""Authentication API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.auth.application import auth_service
from app.modules.auth.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    OTPRequestSchema,
    OTPVerifySchema,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter()

_settings = get_settings()


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly Secure cookies for both tokens."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=_settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies by setting max_age=0."""
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=0,
    )
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        secure=True,
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
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.register(
        db,
        phone=body.phone,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with phone and password",
)
@limiter.limit("5/minute")
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
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return TokenResponse(**tokens)


# ── OTP ──────────────────────────────────────────────────────────────────────


@router.post(
    "/otp/request",
    status_code=status.HTTP_200_OK,
    summary="Request a one-time password",
)
@limiter.limit("3/minute")
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
async def otp_verify(
    body: OTPVerifySchema,
    request: Request,
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
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return TokenResponse(**tokens)


# ── Token Management ─────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
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
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (revoke current session)",
)
async def logout(
    response: Response,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout(db, user_id=user_id)
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Logout from all sessions",
)
async def logout_all(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
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


# ── Session Management ───────────────────────────────────────────────────────


@router.get(
    "/sessions",
    summary="List active sessions",
)
async def list_sessions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    sessions = await auth_service.get_sessions(db, user_id=user_id)
    return [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "device_info": s.device_info,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
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
