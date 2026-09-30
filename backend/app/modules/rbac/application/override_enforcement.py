"""Request-time enforcement of per-user permission overrides.

``RequirePermissions`` (and the legacy ``RequireCasbinPolicy``) resolve the
caller's permissions from the JWT ``permissions`` claim, which is built once
at token issuance from role grants. Per-user overrides must apply at *request*
time — an operator granting or denying a capability takes effect on the next
request, not after the user re-authenticates.

The enforcement dependencies live in ``app.core.security.dependencies`` and
``app.core.security.casbin_enforcer`` and are deliberately not modified; this
module installs a thin, idempotent wrapper around their ``__call__`` when the
RBAC API routes are imported (i.e. at app startup, before any request is
served). Each wrapper keeps the exact signature FastAPI dependency-injects
against (``payload`` from ``get_current_active_user``).

Semantics (identical to the unwrapped dependency when a user has no override
rows):

* ``is_superuser`` accounts bypass everything, exactly as before.
* deny override  >  grant override  >  role-derived claim (incl. ``*``).
* Every override lookup is fail-open on *infrastructure* errors: if the
  overrides table cannot be read (e.g. migration not yet applied), the
  original claim-based behaviour is preserved rather than 500-ing every
  guarded route.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import Depends, HTTPException, status

from app.modules.rbac.domain.models import OverrideEffect

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_installed = False


async def load_overrides(user_id: uuid.UUID) -> list[tuple[str, str]]:
    """Read a user's override rows as ``(permission, effect)`` pairs.

    Opens a short-lived session — route dependencies already hold one, but
    the wrapped dependency never receives it. Fail-open: any read failure
    (missing table during bootstrap, pool hiccup) yields no overrides so
    the original claim-based decision stands.
    """
    try:
        from sqlalchemy import select

        from app.core.database.session import async_session_factory
        from app.modules.rbac.domain.models import UserPermissionOverride

        async with async_session_factory() as db:
            stmt = select(
                UserPermissionOverride.permission, UserPermissionOverride.effect
            ).where(UserPermissionOverride.user_id == user_id)
            rows = (await db.execute(stmt)).all()
            # ``.value``, not ``str()``: OverrideEffect is a str-Enum, and on
            # Python 3.11+ ``str(member)`` is "OverrideEffect.GRANT" — which
            # ``OverrideEffect(...)`` in split_overrides then rejects as an
            # invalid value, so *every* override was being discarded as a bad
            # effect and silently enforced as nothing at all.
            return [(permission, effect.value) for permission, effect in rows]
    except Exception as exc:
        await logger.awarning(
            "permission_override_lookup_failed",
            user_id=str(user_id),
            error=str(exc),
        )
        return []


def split_overrides(overrides: list[tuple[str, str]]) -> tuple[set[str], set[str]]:
    """Split override pairs into ``(grants, denies)`` codename sets."""
    grants: set[str] = set()
    denies: set[str] = set()
    for permission, effect in overrides:
        try:
            effect_value = OverrideEffect(str(effect).strip().lower())
        except ValueError:
            logger.warning("permission_override_bad_effect", permission=permission)
            continue
        if effect_value is OverrideEffect.DENY:
            denies.add(permission)
        else:
            grants.add(permission)
    return grants, denies


def _caller_id(payload: dict[str, Any]) -> uuid.UUID | None:
    """Extract the caller's UUID from the JWT ``sub`` claim, if parseable."""
    try:
        return uuid.UUID(str(payload.get("sub", "")))
    except (TypeError, ValueError):
        return None


def install() -> None:
    """Wrap the security dependencies so every existing guard honours overrides.

    Idempotent: repeated imports of the RBAC routes never stack wrappers.
    Fail-safe: an installation problem is logged and swallowed — overrides
    are a management feature and must never prevent the app from booting.
    """
    global _installed
    if _installed:
        return
    try:
        from app.core.security.casbin_enforcer import RequireCasbinPolicy
        from app.core.security.dependencies import RequirePermissions

        _install_require_permissions(RequirePermissions)
        _install_casbin_policy(RequireCasbinPolicy)
        _installed = True
        logger.info("permission_override_enforcement_installed")
    except Exception as exc:
        logger.error("permission_override_enforcement_install_failed", error=str(exc))


def _install_require_permissions(cls: type) -> None:
    from app.core.security.dependencies import get_current_active_user

    original = cls.__call__

    async def call_with_overrides(
        self: Any,
        payload: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        # Superusers keep their unconditional bypass (unchanged behaviour).
        if payload.get("is_superuser"):
            self._rebind_admin(payload)
            return payload

        caller = _caller_id(payload)
        try:
            overrides = await load_overrides(caller) if caller else []
        except Exception:
            overrides = []
        if not overrides:
            return await original(self, payload)

        from app.modules.rbac.application.permission_catalog import CATALOG_CODENAMES

        grants, denies = split_overrides(overrides)

        # An application password carries ``scopes``, not ``permissions``, so
        # everything below would compute against an empty base and a scoped
        # credential would be denied on every route as soon as it had any
        # override at all. The scope list is the ceiling the holder of the
        # credential chose, so a per-user override must never widen it — a
        # grant override would otherwise turn ``scopes=["users:read"]`` into a
        # ``users:write`` credential, and a deny override unrelated to the
        # scope would refuse access the credential actually has. Denies that
        # name a required permission still apply, on top of the scope.
        if payload.get("auth_method") == "application_password":
            from app.modules.auth.application.application_password_service import (
                has_scope,
            )

            missing = {
                required
                for required in self.required_permissions
                if not has_scope(payload, required)
            } | (denies & set(self.required_permissions))
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
        claim: set[str] = set(payload.get("permissions", []))
        # Wildcard claim / super_admin role mean "everything enforceable";
        # expanding first lets deny overrides carve real holes out of it.
        if "*" in claim or "super_admin" in payload.get("roles", []):
            base: set[str] = set(CATALOG_CODENAMES)
        else:
            base = claim
        # Deny beats grant beats role-derived: grants apply first, denies strip.
        effective = (base | grants) - denies

        missing = self.required_permissions - effective
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(sorted(missing))}",
            )
        self._rebind_admin(payload)
        return payload

    cls.__call__ = call_with_overrides


def _install_casbin_policy(cls: type) -> None:
    from app.core.security.dependencies import get_current_active_user

    original = cls.__call__

    async def casbin_with_overrides(
        self: Any,
        payload: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        caller = _caller_id(payload)
        try:
            overrides = await load_overrides(caller) if caller else []
        except Exception:
            overrides = []
        if not overrides:
            return await original(self, payload)

        grants, denies = split_overrides(overrides)
        codename = f"{self.resource}:{self.action}"
        if codename in denies:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"عدم دسترسی: شما مجوز انجام عملیات '{self.action}' "
                    f"روی بخش '{self.resource}' را ندارید."
                ),
            )
        if codename in grants:
            return payload
        return await original(self, payload)

    cls.__call__ = casbin_with_overrides
