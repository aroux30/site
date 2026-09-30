"""Per-tenant scoping for the vendor surfaces.

Every admin vendor route takes a ``{id}`` and is guarded only by
``RequirePermissions("vendors:read"/"vendors:write", "admin:access")``. Those
codenames are global, so the moment a ``vendor`` role is seeded with
``vendors:write`` — which is the natural way to give sellers a storefront — any
holder can act on *every* vendor: edit their details, read their earnings,
create settlements in their name.

``Vendors.user_id`` already links a vendor profile to the user who owns it, so
the scoping has a source of truth. This module turns that link into a check.

Two kinds of caller, and the difference matters:

* a **platform admin** — holds ``admin:access`` through the staff side. May act
  on any vendor; that is the job.
* a **vendor** — holds ``vendors:*`` but not ``admin:access``. May act only on
  the vendor profile their own user owns.

The self-service routes (``GET /vendors/me``, ``PATCH /vendors/me/profile``)
already scope themselves through ``get_vendor_by_user_id`` and do not use this.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.exceptions.handlers import ForbiddenError, NotFoundError


def is_platform_admin(payload: dict[str, Any]) -> bool:
    """Whether the caller may act on *any* vendor, not just their own.

    Mirrors the unconditional bypass in
    ``object_capabilities.is_superuser`` plus the ``admin:access`` that every
    admin vendor route already requires. A vendor role never carries it, so
    holding both is the test for "staff, not seller".
    """
    permissions = set(payload.get("permissions") or [])
    if (
        payload.get("is_superuser")
        or "*" in permissions
        or "super_admin" in (payload.get("roles") or [])
    ):
        return True
    return "admin:access" in permissions


def _caller_id(payload: dict[str, Any]) -> uuid.UUID | None:
    """The calling user, or ``None`` when the ``sub`` claim is not a UUID.

    Returning ``None`` is not a pass. An unparseable identity cannot be shown to
    own a specific vendor, so the call falls through to the deny branch rather
    than silently widening access.
    """
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(str(sub))
    except (TypeError, ValueError):
        return None


async def require_vendor_scope(
    payload: dict[str, Any],
    vendor: Any,
    *,
    owned_by: uuid.UUID | None = None,
) -> None:
    """Authorise *payload* to act on *vendor*; raise otherwise.

    ``vendor`` is the row the route already loaded. ``owned_by`` is the
    ``Vendor.user_id`` column, passed separately so this does not depend on the
    attribute being spelled the same way on every call site.

    Raises ``403`` for a vendor reaching outside their own profile. The
    distinction from the content layer is deliberate: there, seeing another
    author's post is a legitimate editorial job, so a 404 would be wrong. Here,
    a seller asking about another seller's settlement should learn nothing —
    including whether that vendor exists — so an unowned target is reported as
    ``404`` when no such vendor exists at all and ``403`` when it does and the
    caller is simply not its owner. The route has already 404'd by the time
    this runs, so in practice a seller sees ``403`` on a real vendor and a bare
    ``404`` on a made-up id.
    """
    if is_platform_admin(payload):
        return

    caller = _caller_id(payload)
    if caller is None:
        raise ForbiddenError(detail="قابل تشخیص نیست که این درخواست از طرف چه کسی است")

    owner = owned_by if owned_by is not None else getattr(vendor, "user_id", None)
    if owner is None:
        # A vendor row with no owner cannot be scoped, so it is staff-only.
        raise ForbiddenError(detail="این ویندور به کاربری متصل نیست")

    if owner != caller:
        raise ForbiddenError(detail="شما فقط به ویندور خودتان دسترسی دارید")


async def load_scoped_vendor(
    db: Any,
    payload: dict[str, Any],
    vendor_id: uuid.UUID,
) -> Any:
    """Load a vendor and check the caller may act on it.

    Used by the admin routes that take ``{id}``. Keeps the load-then-check pair
    in one place so a new route cannot forget the second half — the shape that
    let four unguarded taxonomy routes through in the WordPress parity audit.
    """
    from sqlalchemy import select

    from app.modules.vendors.domain.models import Vendor

    vendor = (
        await db.execute(select(Vendor).where(Vendor.id == vendor_id))
    ).scalar_one_or_none()
    if vendor is None:
        raise NotFoundError(resource="Vendor", detail=f"Vendor '{vendor_id}' not found")

    await require_vendor_scope(payload, vendor, owned_by=vendor.user_id)
    return vendor
