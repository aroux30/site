"""Per-user permission overrides (WordPress add_cap/remove_cap parity).

Resolution contract — effective permission set for a user::

    deny override  >  grant override  >  role-derived permissions

* A ``deny`` row removes the codename from the effective set even when every
  role the user holds grants it (and even when the JWT carries ``*``).
* A ``grant`` row adds the codename without touching any role.
* Role-derived permissions (the JWT ``permissions`` claim built at token
  time) fill everything else — their behaviour is never changed.

Permission strings must exist in :data:`PERMISSION_CATALOG`; unknown
codenames are rejected with the API-wide 422 validation error. The catalog
itself is untouched: overrides are a per-user delta on top of it.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.rbac.application.permission_catalog import CATALOG_CODENAMES
from app.modules.rbac.domain.models import OverrideEffect, UserPermissionOverride

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def validate_permission_codename(permission: str) -> str:
    """Return *permission* if it exists in the catalog, else raise 422.

    Overrides can never mint permissions the API does not enforce: an
    unknown codename would be dead weight at best and a typo-shaped trap
    at worst, so it is rejected like any other invalid payload.
    """
    codename = permission.strip()
    if codename not in CATALOG_CODENAMES:
        raise ValidationError(
            detail=f"Unknown permission '{permission}'; it must exist in the permission catalog"
        )
    return codename


def validate_effect(effect: OverrideEffect | str) -> OverrideEffect:
    """Normalise an effect value ("grant"/"deny", case-insensitive)."""
    if isinstance(effect, OverrideEffect):
        return effect
    try:
        return OverrideEffect(str(effect).strip().lower())
    except ValueError as exc:
        raise ValidationError(detail=f"Invalid effect '{effect}'; use 'grant' or 'deny'") from exc


def resolve_effective_permissions(
    role_permissions: Iterable[str],
    overrides: Iterable[tuple[str, OverrideEffect | str]],
    *,
    catalog: Iterable[str] = CATALOG_CODENAMES,
) -> set[str]:
    """Apply the resolution contract to a role-derived permission set.

    Pure and session-free. ``catalog`` is the universe a ``*`` wildcard
    expands to (the enforceable codenames); by default the real catalog.
    Overrides whose permission is outside *catalog* are ignored — they could
    never be enforced anyway.
    """
    universe = set(catalog)
    roles = set(role_permissions)
    # The ``*`` wildcard (superuser-style claim) expands to the whole
    # enforceable catalog so a deny override can carve a hole out of it.
    effective = set(universe) if "*" in roles else set(roles)
    known_grants: set[str] = set()
    known_denies: set[str] = set()
    for permission, effect in overrides:
        if permission not in universe:
            continue
        try:
            effect_value = validate_effect(effect)
        except ValidationError:
            continue
        if effect_value is OverrideEffect.DENY:
            known_denies.add(permission)
        else:
            known_grants.add(permission)
    # Deny beats grant beats role-derived: add grants first, then strip
    # denies (a permission that is both denied and granted ends up denied).
    effective |= known_grants
    effective -= known_denies
    return effective


async def list_overrides(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[UserPermissionOverride]:
    """List every override row for a user."""
    stmt = (
        select(UserPermissionOverride)
        .where(UserPermissionOverride.user_id == user_id)
        .order_by(UserPermissionOverride.permission)
    )
    return list((await db.execute(stmt)).scalars().all())


async def grant_override(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    permission: str,
    effect: OverrideEffect | str,
    created_by: uuid.UUID | None = None,
    actor_payload: dict[str, Any] | None = None,
) -> UserPermissionOverride:
    """Grant (or deny) a single permission to a user — upsert semantics.

    The (user, permission) pair is unique: granting an existing row flips
    its effect instead of duplicating it, mirroring ``add_cap`` replacing
    the capability's value in WordPress.

    An override is the sharpest escalation tool in the system: ``grant`` for
    ``*`` hands the caller every permission in the catalog, and it was reachable
    for one's own account because this function never saw who was asking. The
    payload is optional so internal callers keep working, but routes must pass
    it or the guard cannot run.
    """
    from app.modules.users.domain.models import User

    if actor_payload is not None:
        from app.core.security.object_capabilities import require_no_self_escalation

        await require_no_self_escalation(
            actor_payload, target_user_id=user_id, action="change the permissions of"
        )

    codename = validate_permission_codename(permission)
    effect_value = validate_effect(effect)

    if await db.get(User, user_id) is None:
        raise NotFoundError(resource="User")

    stmt = select(UserPermissionOverride).where(
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.permission == codename,
    )
    override = (await db.execute(stmt)).scalar_one_or_none()
    if override is None:
        override = UserPermissionOverride(
            user_id=user_id,
            permission=codename,
            effect=effect_value,
            created_by=created_by,
        )
        db.add(override)
    else:
        override.effect = effect_value
        override.created_by = created_by
    await db.flush()

    await logger.ainfo(
        "user_permission_override_set",
        user_id=str(user_id),
        permission=codename,
        effect=effect_value.value,
        actor=str(created_by) if created_by else None,
    )
    return override


async def revoke_override(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    permission: str,
) -> None:
    """Remove a user's override for a permission (WordPress remove_cap)."""
    codename = validate_permission_codename(permission)
    stmt = select(UserPermissionOverride).where(
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.permission == codename,
    )
    override = (await db.execute(stmt)).scalar_one_or_none()
    if override is None:
        raise NotFoundError(resource="UserPermissionOverride")
    await db.delete(override)
    await db.flush()

    await logger.ainfo(
        "user_permission_override_revoked",
        user_id=str(user_id),
        permission=codename,
    )
