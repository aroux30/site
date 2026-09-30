"""User capabilities per post type (WordPress parity).

Maps content-type-specific permissions to RBAC roles. Extends the existing
RBAC system with fine-grained per-post-type capabilities.

Capabilities follow WordPress naming:
- edit_posts, edit_others_posts, publish_posts, delete_posts
- edit_pages, edit_others_pages, publish_pages, delete_pages
- moderate_comments, manage_categories, manage_options

Capabilities are a *vocabulary*, not a second permission system: each one is
declared here purely in terms of the real permission codenames the route
guards already enforce (``blog:write``, ``settings:write``, …). A role —
including one created at runtime through ``/admin/roles`` — holds a
capability exactly when its assigned permissions include every codename the
capability requires. Nothing consults a fixed list of role names, so a new
role is honoured the moment it is granted permissions.

``ROLE_CAPABILITIES`` survives only as the *default* projection used to seed
and describe the WordPress built-in roles; it is not the source of truth.

The ``*_others_*`` entries are the *meta* half of the WordPress pair and are
enforced per object, not per route: see
:func:`app.core.security.object_capabilities.require_object_capability`, which
maps ``edit_post`` to ``edit_posts`` for the caller's own content and to
``edit_others_posts`` for anyone else's.

Usage:
    can = UserCapabilityService.check(user_roles, "edit_posts")
    caps = UserCapabilityService.get_all_for_role("editor")
    caps = await UserCapabilityService.get_for_user(db, user_id)   # real RBAC
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# WordPress capability -> the permission codenames that grant it.
#
# Every codename below appears in ``permission_catalog.PERMISSION_CATALOG``
# and is enforced by a ``RequirePermissions(...)`` guard on the route that
# capability fronts, so a capability can never claim more than the API grants.
#
# The ``*_others_*`` capabilities carry a *second* codename
# (``blog:write_others`` / ``settings:write_others``) on top of the write
# codename their base already requires. That extra codename is what makes
# "edit anyone's post" a distinct grant from "edit your own": without it the
# two are declared over the same permission and are indistinguishable, which
# is why these entries used to be decorative. A role holding only
# ``blog:write`` holds ``edit_posts`` but not ``edit_others_posts`` — exactly
# the author/contributor split WordPress draws. Enforcement lives in
# ``app.core.security.object_capabilities`` (the ``map_meta_cap`` equivalent).
CAPABILITY_PERMISSIONS: dict[str, frozenset[str]] = {
    # Posts
    "edit_posts": frozenset({"blog:write"}),
    # Deliberately NOT blog:write. Mapping publish onto the same codename meant
    # a contributor — who holds blog:write and, per this file's own seed
    # comment, "can write drafts that an editor reviews" — could publish: the
    # status is client-supplied on BlogPostCreate and nothing checked it.
    "publish_posts": frozenset({"blog:publish"}),
    "delete_posts": frozenset({"blog:write_others", "blog:publish"}),
    "edit_others_posts": frozenset({"blog:write", "blog:write_others"}),
    # Pages and other CMS surfaces (all guarded by settings:write)
    "edit_pages": frozenset({"settings:write"}),
    "publish_pages": frozenset({"settings:write"}),
    "delete_pages": frozenset({"settings:write"}),
    "edit_others_pages": frozenset({"settings:write", "settings:write_others"}),
    "edit_custom_posts": frozenset({"blog:write"}),
    "publish_custom_posts": frozenset({"blog:write"}),
    "delete_custom_posts": frozenset({"blog:write"}),
    "manage_taxonomies": frozenset({"blog:write"}),
    "manage_options": frozenset({"settings:write"}),
    "export_content": frozenset({"settings:write"}),
    "import_content": frozenset({"settings:write"}),
    # Comments and terms
    # `moderate_comments` is deliberately *not* satisfied by `blog:write`. Every
    # author and contributor holds `blog:write`, and mapping the WordPress
    # capability onto it gave the contributor role — whose own description says
    # "drafts for review, no publishing" — the power to approve, spam and delete
    # every comment on the site. WordPress reserves it for editors.
    "moderate_comments": frozenset({"blog:moderate_comments"}),
    "manage_categories": frozenset({"blog:write"}),
    # Media
    "upload_files": frozenset({"media:write"}),
    "manage_media": frozenset({"media:write"}),
    # People and access
    "edit_users": frozenset({"users:write"}),
    "manage_roles": frozenset({"rbac:write"}),
}

# WordPress built-in role name -> the slug this deployment actually seeds.
# The two differ ("administrator" vs the seeded "admin"), and a role may be
# referenced by either name, so both resolve to the same capability set.
ROLE_ALIASES: dict[str, str] = {
    "administrator": "admin",
    "admin": "administrator",
    "super_admin": "administrator",
}

# Default capability projection for the WordPress built-in roles. Used to
# seed and describe them — runtime checks go through the RBAC tables.
ROLE_CAPABILITIES: dict[str, set[str]] = {
    "administrator": {
        "edit_posts", "edit_others_posts", "publish_posts", "delete_posts",
        "edit_pages", "edit_others_pages", "publish_pages", "delete_pages",
        "moderate_comments", "manage_categories", "manage_options",
        "edit_custom_posts", "publish_custom_posts", "delete_custom_posts",
        "manage_taxonomies", "upload_files", "manage_media",
        "edit_users", "manage_roles", "export_content", "import_content",
    },
    "editor": {
        "edit_posts", "edit_others_posts", "publish_posts", "delete_posts",
        "edit_pages", "edit_others_pages", "publish_pages", "delete_pages",
        "moderate_comments", "manage_categories",
        "edit_custom_posts", "publish_custom_posts",
        "manage_taxonomies", "upload_files", "manage_media",
    },
    "author": {
        "edit_posts", "publish_posts", "delete_posts",
        "upload_files",
    },
    "contributor": {
        "edit_posts",
    },
    "subscriber": set(),
}

# The seeded slug and the WordPress name are the same role; alias one onto
# the other so a lookup by either name answers identically.
ROLE_CAPABILITIES["admin"] = ROLE_CAPABILITIES["administrator"]


class UserCapabilityService:
    """Check and manage user capabilities per content type."""

    @staticmethod
    def check(user_roles: list[str], capability: str) -> bool:
        """Check if any of the user's *built-in* roles grants the capability.

        Synchronous and table-free, for callers that already hold role names
        off the token. To honour runtime-defined roles, resolve capabilities
        with :meth:`get_for_user` (or :meth:`capabilities_from_permissions`
        when the permission claim is in hand) instead.
        """
        for role in user_roles:
            if capability in UserCapabilityService.get_all_for_role(role):
                return True
        return False

    @staticmethod
    def get_all_for_role(role: str) -> set[str]:
        """Get the *default* capabilities for a built-in role.

        Only the WordPress built-in roles have a default projection; a role
        created at runtime has none and therefore returns an empty set. Use
        :meth:`get_for_role` when the role may have been defined at runtime.
        """
        cap = ROLE_CAPABILITIES.get(role.lower(), set()).copy()
        alias = ROLE_ALIASES.get(role.lower())
        if alias:
            cap |= ROLE_CAPABILITIES.get(alias, set())
        return cap

    @staticmethod
    def get_all_for_roles(roles: list[str]) -> set[str]:
        """Get merged *default* capabilities for multiple built-in roles."""
        caps: set[str] = set()
        for role in roles:
            caps |= UserCapabilityService.get_all_for_role(role)
        return caps

    @staticmethod
    def capabilities_from_permissions(permissions: set[str]) -> set[str]:
        """Derive the capability set implied by a permission set.

        This is the bridge that makes runtime-defined roles work: a capability
        is held when every codename it requires is present. ``"*"`` (the
        superuser wildcard on the JWT) grants everything.
        """
        if "*" in permissions:
            return set(CAPABILITY_PERMISSIONS)
        return {
            name
            for name, required in CAPABILITY_PERMISSIONS.items()
            if required <= permissions
        }

    @staticmethod
    async def get_for_user(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
        """Capabilities a user actually holds, read from the RBAC tables.

        Unlike :meth:`get_all_for_role` this sees roles created through
        ``/admin/roles`` — it resolves the user's assigned role slugs and the
        permissions attached to them, then projects those onto capabilities.
        """
        from sqlalchemy import select

        from app.modules.rbac.domain.models import Permission, Role, RolePermission, UserRole

        # Select the permission slugs directly rather than walking
        # ``role.role_permissions``: lazy loading raises MissingGreenlet
        # under asyncio, and the join is a single query anyway.
        stmt = (
            select(Role.slug, Permission.slug)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        rows = (await db.execute(stmt)).all()
        permissions = {perm_slug for _, perm_slug in rows if perm_slug is not None}
        return UserCapabilityService.capabilities_from_permissions(permissions)

    @staticmethod
    async def describe_roles(db: AsyncSession) -> dict[str, list[str]]:
        """Every role in the database with its effective capabilities.

        Built-in roles are included whether or not they have been seeded, so
        the admin matrix stays complete on a fresh install.
        """
        from sqlalchemy import select

        from app.modules.rbac.domain.models import Permission, Role, RolePermission

        # One join returning the permission slugs per role — never touch a
        # lazily-loaded relationship here (MissingGreenlet under asyncio).
        stmt = (
            select(Role.slug, Permission.slug)
            .outerjoin(RolePermission, RolePermission.role_id == Role.id)
            .outerjoin(Permission, Permission.id == RolePermission.permission_id)
            .order_by(Role.slug)
        )
        by_role: dict[str, set[str]] = {}
        for role_slug, perm_slug in (await db.execute(stmt)).all():
            by_role.setdefault(role_slug, set())
            if perm_slug is not None:
                by_role[role_slug].add(perm_slug)

        described: dict[str, list[str]] = {}
        for role_slug, permissions in by_role.items():
            caps = UserCapabilityService.capabilities_from_permissions(permissions)
            # A built-in role that has not been seeded yet still has a default.
            if not caps and role_slug in ROLE_CAPABILITIES:
                caps = UserCapabilityService.get_all_for_role(role_slug)
            described[role_slug] = sorted(caps)

        for builtin_slug, caps in ROLE_CAPABILITIES.items():
            described.setdefault(builtin_slug, sorted(caps))
        return described

    @staticmethod
    def list_all_capabilities() -> list[str]:
        """List every capability in the vocabulary."""
        return sorted(CAPABILITY_PERMISSIONS)
