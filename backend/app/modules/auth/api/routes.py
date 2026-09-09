"""Authentication API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
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
    return TokenResponse(**tokens)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with phone and password",
)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.login(
        db,
        phone=body.phone,
        password=body.password,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return TokenResponse(**tokens)


# ── OTP ──────────────────────────────────────────────────────────────────────


@router.post(
    "/otp/request",
    status_code=status.HTTP_200_OK,
    summary="Request a one-time password",
)
async def otp_request(
    body: OTPRequestSchema,
    request: Request,
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
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.verify_otp(
        db,
        phone=body.phone,
        code=body.code,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return TokenResponse(**tokens)


# ── Token Management ─────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await auth_service.refresh_token(
        db,
        token=body.refresh_token,
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (revoke current session)",
)
async def logout(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout(db, user_id=user_id)
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
