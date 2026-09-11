"""FastAPI dependencies for authentication and authorisation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security.jwt import verify_token

# auto_error=False so that missing Authorization header does not immediately 401;
# we fall back to the access_token cookie when the header is absent.
_bearer_scheme = HTTPBearer(auto_error=False)


async def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    access_token: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Extract and validate the JWT.

    Resolution order:
    1. ``Authorization: Bearer <token>`` header  (API clients / mobile apps)
    2. ``access_token`` HttpOnly cookie          (browser sessions)
    """
    token: str | None = None

    if credentials is not None:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(token, expected_type="access")


async def get_current_user_id(
    payload: dict[str, Any] = Depends(_extract_token),
) -> uuid.UUID:
    """Return the authenticated user's UUID from the access token ``sub`` claim."""
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing or invalid 'sub' claim",
        ) from exc


async def get_current_user(
    payload: dict[str, Any] = Depends(_extract_token),
) -> dict[str, Any]:
    """Return the full decoded token payload for the current user.

    Downstream handlers can use this to inspect extra claims (roles, permissions, etc.)
    without a database round-trip for lightweight checks.
    """
    if "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub' claim",
        )
    return payload


async def get_current_active_user(
    payload: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Ensure the user account is active.

    In a full implementation this would load the user from the database and
    check ``is_active``.  For the base dependency we trust the token – the
    token is not issued for inactive users.
    """
    if payload.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return payload


class RequirePermissions:
    """Dependency class that enforces a set of required permissions.

    Usage::

        @router.get("/admin/users", dependencies=[Depends(RequirePermissions("users:read"))])
        async def list_users(): ...

        @router.delete(
            "/admin/users/{user_id}",
            dependencies=[Depends(RequirePermissions("users:delete", "admin:access"))],
        )
        async def delete_user(user_id: uuid.UUID): ...
    """

    def __init__(self, *required: str) -> None:
        self.required_permissions = set(required)

    async def __call__(
        self,
        payload: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        user_permissions: set[str] = set(payload.get("permissions", []))
        if "*" in user_permissions or "super_admin" in payload.get("roles", []):
            return payload
        missing = self.required_permissions - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(sorted(missing))}",
            )
        return payload
