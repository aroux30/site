"""FastAPI dependencies for authentication and authorisation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security.actor_context import SOURCE_ADMIN, SOURCE_API, bind_actor
from app.core.security.jwt import verify_token

# auto_error=False so that missing Authorization header does not immediately 401;
# we fall back to the access_token cookie when the header is absent.
_bearer_scheme = HTTPBearer(auto_error=False)


def _looks_like_application_password(token: str) -> bool:
    """Whether a bearer token should be tried as an application password.

    A JWT is three dot-separated base64 segments; our application passwords are
    ``secrets.token_urlsafe`` output and contain no dots. Testing that first
    keeps the common case (a JWT) off the database entirely.
    """
    return "." not in token and len(token) >= 20


async def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    access_token: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Extract and validate the JWT.

    Resolution order:
    1. ``Authorization: Bearer <token>`` header  (API clients / mobile apps)
    2. ``access_token`` HttpOnly cookie          (browser sessions)

    Also enforces the server-side revocation denylist: a user deactivated
    (or security-suspended) is rejected immediately even while their access
    token is still inside its TTL. One Redis GET per authenticated request,
    fail-open on cache outage (see app/core/security/revocation.py).
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

    # An application password is not a JWT, so it must be recognised before
    # verify_token tries (and fails) to decode it. This is the path a phone app
    # or a personal script uses instead of the account password.
    if _looks_like_application_password(token):
        from app.core.database.session import async_session_factory
        from app.modules.auth.application.application_password_service import (
            verify_application_password,
        )
        from app.core.security import revocation

        async with async_session_factory() as db:
            app_payload = await verify_application_password(db, token)
        if app_payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Application password is invalid, revoked, or expired",
                headers={"WWW-Authenticate": 'Bearer realm="application-password"'},
            )
        # The account behind the credential must still be in good standing; a
        # valid application password is not a licence around a disabled user.
        if await revocation.is_user_denied(uuid.UUID(app_payload["sub"])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        return app_payload

    payload = verify_token(token, expected_type="access")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return payload  # let downstream sub-claim validation handle it

    from app.core.security import revocation

    jti = payload.get("jti")
    if jti and await revocation.is_jti_denied(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if await revocation.is_user_denied(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Bind identity to the ambient actor context (see actor_context module):
    # this is the single point every authenticated route passes through, and
    # the audit module's change capture reads it from inside a DB flush where
    # the request object is unreachable.
    bind_actor(user_id, source=SOURCE_API)

    return payload


async def _extract_optional_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    access_token: str | None = Cookie(default=None),
) -> dict[str, Any] | None:
    """Like ``_extract_token`` but anonymous callers get ``None``.

    For public endpoints where identity is an *enrichment* (guest comments,
    personalized-but-public reads): an absent token is not an error, but a
    **present-and-invalid** token still is — a forged or expired credential
    must never silently downgrade to the guest path, or an attacker could
    shed their identity by corrupting their own token.
    """
    if credentials is None and not access_token:
        return None
    return await _extract_token(request, credentials, access_token)


async def get_current_user_optional(
    payload: dict[str, Any] | None = Depends(_extract_optional_token),
) -> dict[str, Any] | None:
    """The caller's token payload, or ``None`` for anonymous requests."""
    return payload


async def get_current_user_id(
    payload: dict[str, Any] = Depends(_extract_token),
) -> uuid.UUID:
    """Return the authenticated user's UUID from the access token ``sub`` claim.

    Also binds the identity into the ambient actor context so code with no
    access to the request — notably the audit module's SQLAlchemy change
    capture, which fires inside ``after_flush`` — can attribute what it records.
    """
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing or invalid 'sub' claim",
        ) from exc
    bind_actor(user_id, source=SOURCE_API)
    return user_id


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
        # An application password is a per-app credential, not a session: its
        # payload carries ``scopes`` and deliberately no ``permissions`` (a
        # scoped credential must not be able to compute the full set). Reading
        # only ``permissions`` therefore 403'd every guarded route for a valid
        # credential, while the routes that *are* reachable ignored its scopes
        # entirely — so ``scopes: ["read"]`` behaved as full access.
        # ``has_scope`` is the single place that knows the app-password rules:
        # an empty list means full access (WordPress's default), a non-empty
        # one is a strict allow-list.
        if payload.get("auth_method") == "application_password":
            from app.modules.auth.application.application_password_service import (
                has_scope,
            )

            missing = {
                required
                for required in self.required_permissions
                if not has_scope(payload, required)
            }
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Application password is missing these permissions: "
                        f"{', '.join(sorted(missing))}"
                    ),
                )
            self._rebind_admin(payload)
            return payload

        user_permissions: set[str] = set(payload.get("permissions", []))
        if "*" in user_permissions or "super_admin" in payload.get("roles", []):
            self._rebind_admin(payload)
            return payload
        missing = self.required_permissions - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(sorted(missing))}",
            )
        self._rebind_admin(payload)
        return payload

    @staticmethod
    def _rebind_admin(payload: dict[str, Any]) -> None:
        """Re-bind the actor as an admin-surface change.

        Every permission-gated route is a back-office surface, so a change it
        makes is recorded with ``source="admin"`` rather than the generic
        ``api`` the token dependency bound. Only the source moves — the actor
        id stays exactly the authenticated user (no escalation of identity).
        """
        subject = payload.get("sub")
        if not subject:
            return
        try:
            user_id = uuid.UUID(str(subject))
        except (TypeError, ValueError):
            return
        from app.core.security.actor_context import get_actor

        ctx = get_actor()
        bind_actor(
            ctx.actor_id if ctx is not None and ctx.actor_id is not None else user_id,
            source=SOURCE_ADMIN,
        )


# Backward-compatible alias for singular naming
RequirePermission = RequirePermissions
