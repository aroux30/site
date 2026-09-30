"""Idempotent permission seeding for bootstrap-ready RBAC.

Upserts every codename from :data:`PERMISSION_CATALOG` into the
``permissions`` table and grants the full catalog to the system role
``admin`` (created when missing; existing grants are never removed).
It also provisions the WordPress-parity staff/customer system roles
(editor, author, contributor, customer) with curated permission subsets.

Designed to run on every application startup and via
``python manage.py rbac seed-permissions``: it only ever inserts, so
re-running is a no-op.  Unlike the RBAC API service functions, seeding
deliberately performs no audit logging — it runs outside any actor context
at boot time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.modules.rbac.application.permission_catalog import (
    PERMISSION_CATALOG,
    split_codename,
)
from app.modules.rbac.domain.models import Permission, Role, RolePermission

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

ADMIN_ROLE_SLUG = "admin"
ADMIN_ROLE_NAME = "مدیر سیستم"
ADMIN_ROLE_DESCRIPTION = (
    "نقش سیستمی با دسترسی کامل به تمام ماژول‌ها (به‌روزرسانی خودکار از کاتالوگ مجوزها)"
)

# WordPress-parity role hierarchy (wp-includes/capabilities.php): the admin
# role above gets the whole catalog; the editorial staff roles below get
# curated subsets so an "author" can publish articles but never touch
# payments, and a "contributor" can write drafts that an editor reviews.
# ``customer`` is seeded too so it exists in the role list before the first
# registration creates it. Grants are insert-only: removing a permission from
# a system role is an operator decision, never a seed side-effect.
#
# The ``*:write_others`` codenames are the load-bearing part of that hierarchy:
# they are what separates "edit your own posts" (author, contributor) from
# "edit anyone's posts" (editor, administrator). They are seeded here for the
# two supervisory roles and deliberately withheld from author and contributor,
# which is what makes the per-object check in
# ``app.core.security.object_capabilities`` meaningful.
STAFF_ROLE_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "slug": "editor",
        "name": "سردبیر",
        "description": "مدیریت کامل محتوا: نوشته‌ها، رسانه، نظرات، سئو و صفحات",
        "permissions": (
            "admin:access",
            "blog:write",
            "blog:publish",
            "blog:write_others",
            "blog:moderate_comments",
            "media:read",
            "media:write",
            "seo:write",
            "calendar:read",
            "reviews:moderate",
            "support:read",
            "settings:read",
            "notifications:read",
        ),
    },
    {
        "slug": "author",
        "name": "نویسنده",
        "description": "نوشتن و انتشار نوشته‌های خود با آپلود رسانه",
        "permissions": (
            "admin:access",
            "blog:write",
            "blog:publish",
            "media:read",
            "media:write",
            "calendar:read",
        ),
    },
    {
        "slug": "contributor",
        "name": "همکار",
        "description": "نوشتن پیش‌نویس برای بازبینی سردبیر (بدون انتشار)",
        "permissions": (
            "admin:access",
            "blog:write",
            "media:read",
        ),
    },
    {
        "slug": "customer",
        "name": "مشتری",
        "description": "نقش پیش‌فرض کاربران ثبت‌نام‌شده (بدون دسترسی مدیریتی)",
        "permissions": (),
    },
    {
        # A seller. Deliberately gets NO ``vendors:read``/``vendors:write``:
        # those codenames are global, so granting them here is exactly what
        # would let a seller read another seller's earnings or write a
        # settlement in their name. The surfaces a seller needs — profile,
        # storefront, orders, payouts — are reached through the self-service
        # routes that already scope by ``Vendor.user_id``, and the admin routes
        # are gated per tenant by ``vendors.application.tenant_scope``.
        "slug": "vendor",
        "name": "فروشنده",
        "description": (
            "فروشندهٔ ثبت‌نام‌شده. دسترسی فقط به فروشگاه و تسویهٔ خودش؛ "
            "بدون دسترسی به ویندورهای دیگر."
        ),
        "permissions": (
            "catalog:read",
            "media:read",
        ),
    },
)


@dataclass(frozen=True)
class SeedStats:
    """What a seed run did — also the CLI's JSON output."""

    permissions_created: list[str] = field(default_factory=list)
    permissions_skipped: list[str] = field(default_factory=list)
    permissions_granted_to_admin: list[str] = field(default_factory=list)
    admin_role_created: bool = False
    roles_created: list[str] = field(default_factory=list)
    permissions_granted_to_roles: dict[str, int] = field(default_factory=dict)
    total_catalog: int = 0


async def seed_permissions(db: AsyncSession) -> SeedStats:
    """Upsert the permission catalog and grant it to the ``admin`` role.

    Caller owns the transaction boundary: this function flushes but never
    commits, so it composes with both the startup lifespan and the CLI.
    """
    # 1. Fetch existing permissions in one round-trip.
    existing_perms = list((await db.execute(select(Permission))).scalars().all())
    by_slug = {p.slug: p for p in existing_perms}

    created: list[str] = []
    skipped: list[str] = []

    # 2. Upsert catalog permissions (skip any slug that already exists).
    for entry in PERMISSION_CATALOG:
        codename = entry["codename"]
        if codename in by_slug:
            skipped.append(codename)
            continue
        resource, action = split_codename(codename)
        perm = Permission(
            name=entry["name_fa"],
            slug=codename,
            description=entry["description"],
            resource=resource,
            action=action,
        )
        db.add(perm)
        by_slug[codename] = perm
        created.append(codename)

    await db.flush()  # assign PKs to newly added permissions

    # 3. Get-or-create the admin system role.
    role_result = await db.execute(select(Role).where(Role.slug == ADMIN_ROLE_SLUG))
    admin_role = role_result.scalar_one_or_none()
    admin_role_created = False
    if admin_role is None:
        admin_role = Role(
            name=ADMIN_ROLE_NAME,
            slug=ADMIN_ROLE_SLUG,
            description=ADMIN_ROLE_DESCRIPTION,
            is_system=True,
        )
        db.add(admin_role)
        await db.flush()  # assign role PK
        admin_role_created = True

    # 4. Grant every catalog permission the role does not already have.
    existing_grants = set(
        (
            await db.execute(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == admin_role.id
                )
            )
        )
        .scalars()
        .all()
    )

    granted: list[str] = []
    for codename in [e["codename"] for e in PERMISSION_CATALOG]:
        perm = by_slug[codename]
        if perm.id in existing_grants:
            continue
        db.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
        granted.append(codename)

    await db.flush()

    roles_by_slug: dict[str, Role] = {}
    for row in (await db.execute(select(Role))).scalars():
        roles_by_slug[row.slug] = row

    grants_by_role: dict[uuid.UUID, set[uuid.UUID]] = {}
    for grant in (await db.execute(select(RolePermission))).scalars():
        grants_by_role.setdefault(grant.role_id, set()).add(grant.permission_id)

    # 5. Get-or-create the WordPress-parity staff/customer system roles and
    # grant each its curated subset (insert-only: a permission an operator
    # removed from a role is never re-added by the seed).
    roles_created: list[str] = []
    role_grants: dict[str, int] = {}
    for seed in STAFF_ROLE_SEEDS:
        role_slug: str = seed["slug"]
        role = roles_by_slug.get(role_slug)
        if role is None:
            role = Role(
                name=seed["name"],
                slug=role_slug,
                description=seed["description"],
                is_system=True,
            )
            db.add(role)
            await db.flush()  # assign role PK before granting
            roles_by_slug[role_slug] = role
            roles_created.append(role_slug)

        existing_role_grants = grants_by_role.get(role.id, set())
        granted_count = 0
        for codename in seed["permissions"]:
            perm = by_slug.get(codename)
            if perm is None or perm.id in existing_role_grants:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))
            existing_role_grants.add(perm.id)
            granted_count += 1
        if granted_count:
            role_grants[role_slug] = granted_count

    await db.flush()

    await logger.ainfo(
        "permission_seed_completed",
        permissions_created=len(created),
        permissions_skipped=len(skipped),
        granted_to_admin=len(granted),
        admin_role_created=admin_role_created,
        roles_created=roles_created,
        granted_to_roles=role_grants,
    )

    return SeedStats(
        permissions_created=created,
        permissions_skipped=skipped,
        permissions_granted_to_admin=granted,
        admin_role_created=admin_role_created,
        roles_created=roles_created,
        permissions_granted_to_roles=role_grants,
        total_catalog=len(PERMISSION_CATALOG),
    )
