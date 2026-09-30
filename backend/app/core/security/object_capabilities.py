"""Per-object authorisation — the ``map_meta_cap`` equivalent.

A ``RequirePermissions("blog:write")`` guard answers a single question: *does
this caller hold the codename?* It says nothing about **which record** the
caller is acting on. That is enough for a route that only creates things, and
not enough for one that edits: a flat codename check turns "you may write
blog posts" into "you may rewrite anyone's blog post".

WordPress splits the primitive in two. ``edit_post`` is a *meta* capability:
``map_meta_cap`` resolves it against the concrete post id, and only maps it to
the primitive ``edit_others_posts`` when the post is **not** the caller's own::

    edit_post  ->  edit_posts      when author_id == caller
                ->  edit_others_posts otherwise

This module is that mapping for this codebase. It answers the same question
for a loaded ORM row: is the caller the owner, and do they hold the "others"
capability that lifts them above ownership?

Three design decisions worth stating plainly, because they are not what a
single-content-type shop would do:

1. **The "others" half is its own permission codename.** The capability
   vocabulary already existed
   (:mod:`app.modules.rbac.application.capability_service`) but every
   ``*_others_*`` entry was declared over the *same* codename as its base
   (``edit_others_posts`` → ``{"blog:write"}``, exactly like ``edit_posts``),
   so the two were indistinguishable and both were decorative — grep found the
   only consumer in a read-only matrix route. ``edit_others_posts`` now
   additionally requires ``blog:write_others`` and ``edit_others_pages``
   additionally requires ``settings:write_others``. Because those are ordinary
   catalog codenames, an operator can grant or deny them per user through the
   existing override API with no new machinery here.

2. **A record with no owner is not claimable.** ``author_id`` is nullable on
   pages and on custom post entries, and content entries carry no owner
   column at all (it is recoverable only from the creating revision).
   Treating "no owner" as "owned by everyone" would hand every contributor the
   whole content library; treating it as "owned by nobody" would lock the row
   against its own creator forever. An ownerless record is therefore
   **orphaned** and is not reachable through the owner path at all — only
   through the "others" capability. That keeps a mis-authored row from
   becoming a shared editing surface while leaving it manageable by an editor.

3. **The caller is expected to already be authenticated.** This is a *second*
   check layered on top of whatever route guard brought them to the record; it
   never grants anything, only subtracts. It resolves the *effective*
   permission set (claim + per-user overrides, deny beating grant) so it
   agrees with the guard in front of it — the same source of truth, not a
   parallel one. A second opinion reading a different set would either
   duplicate the override logic or contradict it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ObjectRule:
    """The capability pair that governs one kind of record.

    ``own`` is the primitive WordPress grants for your own content
    (``edit_posts``); ``others`` is the one that unlocks everyone else's
    (``edit_others_posts``). Holding only ``others`` is not enough — the
    caller must be able to edit their own content at all — which keeps this
    check a strict subset of the route guard's codename check.
    """

    own: str
    others: str
    #: Human-readable noun used in the 403 body, e.g. ``"post"``.
    label: str


#: The rules this deployment actually needs, named after the WordPress
#: capability pair they mirror so a reader can look one up. Content *types*
#: (a schema shared by every entry, with no owner column) are deliberately
#: absent: there is no per-object ownership question to answer about a global
#: definition, so it stays governed by its route guard alone.
OBJECT_RULES: dict[str, ObjectRule] = {
    "posts": ObjectRule(own="edit_posts", others="edit_others_posts", label="post"),
    "pages": ObjectRule(own="edit_pages", others="edit_others_pages", label="page"),
    "custom_posts": ObjectRule(
        own="edit_custom_posts", others="edit_others_posts", label="custom post entry"
    ),
}

#: Owner attribute names to try, in order. ``author_id`` is the direct column
#: on a post, page or custom post entry; ``created_by`` is on a revision row,
#: which is how a content entry's author is recovered.
OWNER_FIELDS: tuple[str, ...] = ("author_id", "created_by")


def owner_of(record: Any, fields: tuple[str, ...] = OWNER_FIELDS) -> uuid.UUID | None:
    """Read an owner id off a record under the first attribute present.

    Takes attribute *names* rather than a model so one helper serves records
    that name the column differently. Returns ``None`` when the record has no
    owner column or the column is null — see the orphaned-record note in the
    module docstring.
    """
    for field in fields:
        value = getattr(record, field, None)
        if value is not None:
            return value
    return None


def caller_id(payload: dict[str, Any]) -> uuid.UUID | None:
    """The authenticated caller's UUID from the JWT ``sub`` claim."""
    try:
        return uuid.UUID(str(payload.get("sub", "")))
    except (TypeError, ValueError):
        return None


def is_superuser(payload: dict[str, Any]) -> bool:
    """Whether the caller holds the unconditional bypass.

    Mirrors the check :class:`~app.core.security.dependencies.RequirePermissions`
    makes, so this module can never strip a bypass the route guard granted.
    ``is_superuser`` is included because the override-enforcement wrapper
    treats it as the *primary* bypass (it short-circuits before the permission
    set is even read), so a check that ignored it would narrow a superuser.
    """
    permissions = payload.get("permissions") or []
    return bool(
        payload.get("is_superuser")
        or "*" in permissions
        or "super_admin" in (payload.get("roles") or [])
    )


async def effective_permissions(payload: dict[str, Any]) -> set[str]:
    """The caller's permissions as of *this request*, not at token issuance.

    The JWT ``permissions`` claim is built once at login. Per-user overrides
    must apply per request, so this reads them through the same
    ``load_overrides`` / ``split_overrides`` pair the guard wrapper in
    :mod:`app.modules.rbac.application.override_enforcement` uses and applies
    the same contract via ``resolve_effective_permissions``: deny beats grant
    beats role-derived, with ``*`` expanding to the catalog first so a deny
    override can carve a real hole in it.

    An override lookup that fails is fail-open (``load_overrides`` swallows
    infrastructure errors), degrading to the plain claim — the same trade the
    guard already makes, so the two can never disagree in a way that would let
    an operator's deny be ignored by one path and honoured by the other.
    """
    claim: set[str] = set(payload.get("permissions") or [])
    caller = caller_id(payload)
    if caller is None:
        return claim

    from app.modules.rbac.application.override_enforcement import load_overrides
    from app.modules.rbac.application.override_service import (
        resolve_effective_permissions,
    )

    overrides = await load_overrides(caller)
    if not overrides:
        return claim
    return resolve_effective_permissions(claim, overrides)


async def capabilities_of(payload: dict[str, Any]) -> set[str]:
    """Every capability the caller holds, overrides included.

    A superuser holds all of them. Otherwise the set is projected off the
    effective permissions through the capability vocabulary, which is what
    makes a role created at runtime through ``/admin/roles`` work with no code
    change — the projection reads the permissions the role was actually
    granted, not a fixed list of built-in role names.
    """
    if is_superuser(payload):
        from app.modules.rbac.application.capability_service import (
            CAPABILITY_PERMISSIONS,
        )

        return set(CAPABILITY_PERMISSIONS)

    from app.modules.rbac.application.capability_service import (
        UserCapabilityService,
    )

    return UserCapabilityService.capabilities_from_permissions(
        await effective_permissions(payload)
    )


async def require_object_capability(
    payload: dict[str, Any],
    record: Any,
    rule: ObjectRule,
    *,
    owner_fields: tuple[str, ...] = OWNER_FIELDS,
) -> None:
    """Authorise *payload* to mutate *record*; raise ``403`` otherwise.

    The owner/non-owner matrix, matching ``map_meta_cap``:

    ====================================  ===============================
    Caller                                Outcome
    ====================================  ===============================
    superuser / ``*`` / ``super_admin``    allowed (bypass, checked first)
    owner, holds ``own`` capability       allowed
    owner, lacks ``own``                  403 — ownership is necessary
                                         but not sufficient
    non-owner, holds ``others``           allowed
    non-owner, lacks ``others``          403
    orphaned record, holds ``others``     allowed
    orphaned record, lacks ``others``    403 (see module docstring)
    ====================================  ===============================

    ``record`` is whatever the route already loaded: the post itself, or — for
    a table with no author column — the revision that created it, whose
    ``created_by`` is the author. The function only ever removes access. It
    deliberately does not re-check the underlying permission codename: the
    route's ``RequirePermissions(...)`` guard is the single place that decides
    whether ``blog:write`` is held, and duplicating it here would let a deny
    override and this check disagree about the same caller.
    """
    if is_superuser(payload):
        return

    capabilities = await capabilities_of(payload)
    if rule.own not in capabilities:
        # Checked before ownership on purpose: a caller who cannot edit their
        # own content at all should not reach the ownership comparison, and
        # the message must not leak "you *do* own this, you just may not have
        # the capability".
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required capability: {rule.own}",
        )

    owner = owner_of(record, owner_fields)
    caller = caller_id(payload)
    if owner is not None and owner == caller:
        return

    if rule.others in capabilities:
        return

    if owner is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Editing this {rule.label} requires the "
                f"'{rule.others}' capability; only the author may do otherwise."
            ),
        )

    # Orphaned record: no author to compare against, so the owner path cannot
    # apply — and the "others" capability was just tested and failed.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"This {rule.label} has no author, so it can only be changed by a "
            f"caller holding '{rule.others}'."
        ),
    )


# ── Self-escalation guard ────────────────────────────────────────────────────

#: Capability required to change **your own** roles or permission overrides.
#: `rbac:write` answers "may this caller assign roles at all", which is not the
#: same question as "may this caller raise their own privileges" — without a
#: separate codename, every role manager could mint themselves an administrator.
ESCALATE_OWN_CAPABILITY = "rbac:escalate_own"


async def require_no_self_escalation(
    payload: dict[str, Any],
    *,
    target_user_id: uuid.UUID,
    action: str,
) -> None:
    """Refuse a privilege change aimed at the caller themselves.

    ``assign_roles_to_user`` and ``grant_override`` take an ``actor_id`` and log
    it, which made both functions *look* like they knew who was acting. Neither
    compared it to the target: any holder of ``rbac:write`` could hand
    themselves ``admin`` or a ``grant`` override for every permission. The
    resulting user could then grant themselves anything else.

    A user holds a *set* of roles, so a blanket ban on self-targeting would lock
    an administrator out of their own account. The rule is therefore narrower:
    self-targeting is fine as long as the caller already holds the resulting
    privilege — you may not use the RBAC API to gain something you do not have.
    Superusers are exempt, which is what makes an escalation recoverable at all.

    Raises ``403``. Returns ``None`` when the change is allowed.
    """
    caller = caller_id(payload)
    if caller is None or caller != target_user_id:
        return
    if is_superuser(payload):
        return

    capabilities = await capabilities_of(payload)
    if ESCALATE_OWN_CAPABILITY in capabilities:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"You cannot {action} your own account without the "
            f"'{ESCALATE_OWN_CAPABILITY}' capability."
        ),
    )


async def require_no_self_escalation_via_role(
    payload: dict[str, Any],
    db: Any,
    *,
    role_id: uuid.UUID,
    role_name: str,
    permission_codenames: list[str],
) -> None:
    """Refuse adding permissions to a role the caller already holds.

    The second door into self-escalation, and the one a per-user guard cannot
    see. ``require_no_self_escalation`` blocks "grant myself a role", but a
    caller with ``rbac:write`` could instead add ``rbac:escalate_own`` to the
    role they already had, then walk back through the first door. Two requests,
    same outcome.

    The rule is the same shape, applied one level up: you may reshape a role you
    hold only with the explicit capability that says you may. Rejecting every
    edit to your own role would be worse than the bug — a system administrator
    could no longer adjust their own permissions, and a bad grant would become
    unrecoverable.
    """
    if is_superuser(payload):
        return

    caller = caller_id(payload)
    if caller is None:
        return

    from sqlalchemy import select

    from app.modules.rbac.domain.models import Role, UserRole

    held = await db.execute(
        select(UserRole.role_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == caller, Role.id == role_id)
    )
    if held.first() is None:
        return

    capabilities = await capabilities_of(payload)
    if ESCALATE_OWN_CAPABILITY in capabilities:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"You cannot add permissions ({', '.join(permission_codenames) or 'none named'}) "
            f"to the role '{role_name}' that you hold yourself, without the "
            f"'{ESCALATE_OWN_CAPABILITY}' capability."
        ),
    )
