"""User CRUD service for address management and admin operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.modules.audit.application.audit_service import log_action
from app.modules.rbac.domain.models import Role, UserRole
from app.modules.users.domain.models import Address, User, UserProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Admin User CRUD ──────────────────────────────────────────────────────────


async def get_users(
    db: AsyncSession,
    *,
    search: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
    include_deleted: bool = False,
    pending_approval: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """List users with optional filters and pagination (admin).

    Returns ``(items, total_count)``.

    ``role`` filters server-side, on the role slug. It used to be a client-side
    filter over the current page, so "show me the vendors" answered with the
    vendors *on this page* — and an operator had to page through the whole
    store to find the one they wanted. The join is on the slug because that is
    what the admin table badges on.

    ``include_deleted`` is what makes a soft-deleted account reachable again:
    without it the list (and therefore the restore action) could not see the
    rows that a restore is for.

    ``pending_approval`` is what makes the approval queue reachable: without a
    filter for it, an operator has no way to find the accounts waiting on them
    among every other row.
    """
    # The role links are eager-loaded on purpose: the admin users table has a
    # role column and a role filter, and without this the API returned no role
    # names at all, so every row rendered as "مشتری عادی" and the filter matched
    # nothing. A repair of the frontend alone could not have fixed it — the field
    # was never on the wire.
    stmt = select(User).options(selectinload(User.profile), selectinload(User.roles).selectinload(UserRole.role))
    count_stmt = select(func.count(User.id))

    if not include_deleted:
        # Soft-deleted accounts are hidden by default, exactly like the library
        # hides trashed media. A restore view asks for them explicitly.
        stmt = stmt.where(User.deleted_at.is_(None))
        count_stmt = count_stmt.where(User.deleted_at.is_(None))

    if search is not None:
        pattern = f"%{search}%"
        search_filter = User.phone.ilike(pattern) | User.email.ilike(pattern)
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
        count_stmt = count_stmt.where(User.is_active == is_active)

    if pending_approval is not None:
        stmt = stmt.where(User.pending_approval == pending_approval)
        count_stmt = count_stmt.where(User.pending_approval == pending_approval)

    if role:
        # A subquery rather than a join: a user with two roles would otherwise
        # appear twice in the page and inflate the count.
        role_users = (
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.slug == role)
        )
        stmt = stmt.where(User.id.in_(role_users))
        count_stmt = count_stmt.where(User.id.in_(role_users))

    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().unique().all()

    items = []
    for user in users:
        profile = user.profile
        items.append(
            {
                "id": user.id,
                "phone": user.phone,
                "email": user.email,
                "first_name": profile.first_name if profile else None,
                "last_name": profile.last_name if profile else None,
                "display_name": profile.display_name if profile else None,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                # So the approval queue can badge the row and offer
                # approve/reject instead of the ordinary block action.
                "pending_approval": bool(user.pending_approval),
                "created_at": user.created_at,
                "last_login": user.last_login,
                # Slugs, not the Persian display name: the admin table filters
                # and badges on ``super_admin``/``vendor``, so a display name
                # made the role filter match nothing.
                "roles": [ur.role.slug for ur in user.roles if ur.role is not None],
                "is_superuser": bool(user.is_superuser),
                # So the restore view can tell a deleted row from a live one
                # with the same fields, and offer the right action.
                "deleted_at": user.deleted_at,
            }
        )

    return items, total


async def get_user_entity(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> User | None:
    """The ORM row itself, or None.

    For the paths that need a column the detail dict flattens away — the admin
    password reset reads ``email`` and ``password_hash``, and neither is part of
    ``get_user``'s payload because neither belongs in a response. Rebuilding a
    query per field at each call site is how one of them ends up checking
    ``is_active`` where it meant ``password_hash``.

    Returns None rather than raising, because the caller here wants to answer
    404 itself; ``get_user`` raises, because its callers all want that.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Get detailed user information (admin)."""
    stmt = (
        select(User)
        .options(selectinload(User.profile), selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(resource="User")

    profile = user.profile
    role_slugs = [ur.role.slug for ur in user.roles if ur.role] if user.roles else []

    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "first_name": profile.first_name if profile else None,
        "last_name": profile.last_name if profile else None,
        "display_name": profile.display_name if profile else None,
        "pending_approval": bool(user.pending_approval),
        "national_code": profile.national_code if profile else None,
        "birth_date": str(profile.birth_date) if profile and profile.birth_date else None,
        "avatar_url": profile.avatar_url if profile else None,
        "gender": profile.gender if profile else None,
        "is_b2b": bool(getattr(profile, "is_b2b", False)) if profile else False,
        "company_name": getattr(profile, "company_name", None) if profile else None,
        "tax_exemption_certificate_no": (
            getattr(profile, "tax_exemption_certificate_no", None) if profile else None
        ),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login,
        "roles": role_slugs,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "deleted_at": user.deleted_at,
    }


async def create_user_admin(
    db: AsyncSession,
    *,
    data: dict[str, Any],
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Admin direct creation of a new platform user."""
    from app.core.security.password import hash_password
    from app.modules.rbac.domain.models import Role, UserRole

    phone = data["phone"]
    email = data.get("email")
    password = data.get("password")

    existing_phone = await db.execute(select(User).where(User.phone == phone))
    if existing_phone.scalar_one_or_none() is not None:
        raise ConflictError(detail="Phone number already registered")

    if email:
        existing_email = await db.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none() is not None:
            raise ConflictError(detail="Email already registered")

    pwd_hash = hash_password(password) if password else None

    from app.modules.users.application.author_slug import unique_author_slug

    user = User(
        phone=phone,
        email=email,
        password_hash=pwd_hash,
        is_active=data.get("is_active", True),
        is_verified=data.get("is_verified", True),
        # Same reason as the registration path: the author archive reads this
        # column, and an admin-created author is exactly the person who writes
        # a byline. Falling back to the phone keeps it unique when the name is
        # empty.
        author_slug=await unique_author_slug(
            db,
            f"{data.get('first_name') or ''} {data.get('last_name') or ''}".strip(),
            fallback=phone,
        ),
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        national_code=data.get("national_code"),
    )
    db.add(profile)

    role_slugs = data.get("role_slugs", [])
    if role_slugs:
        roles_res = await db.execute(select(Role).where(Role.slug.in_(role_slugs)))
        for r in roles_res.scalars().all():
            # No `assigned_by`: `user_roles` has no such column — it is a bare
            # association. Passing one raised TypeError, so creating an account
            # *with* a role never worked; the role editor's separate path (which
            # omits it) is why nobody noticed. The audit row below carries the
            # actor instead.
            db.add(UserRole(user_id=user.id, role_id=r.id))

    await db.flush()
    created = await get_user(db, user_id=user.id)

    # Tell the account holder. An operator creating a staff or customer account
    # left it completely silent: the address was stored, the password was set,
    # and the new owner had no idea the account existed until they tried to
    # log in and failed. Sent after the row is flushed so the id exists, and
    # through the same path as every other transactional mail in the app.
    #
    # Best-effort: a mail outage must not roll back a user the operator just
    # created, so the failure is logged and swallowed, exactly as in
    # ``_send_password_reset`` and ``email_change_service``.
    if email:
        try:
            from app.modules.notifications.application.email_service import send_email

            await send_email(
                db,
                recipient=email,
                subject="حساب شما ایجاد شد",
                html_body=(
                    '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                    "<p>حساب کاربری شما در فروشگاه ایجاد شد.</p>"
                    "<p>اگر این حساب را شما درخواست نکرده‌اید، "
                    "همین حالا با پشتیبانی تماس بگیرید.</p>"
                    "</div>"
                ),
                text_body=(
                    "حساب کاربری شما در فروشگاه ایجاد شد.\n"
                    "اگر این حساب را شما درخواست نکرده‌اید، "
                    "همین حالا با پشتیبانی تماس بگیرید."
                ),
            )
        except Exception:
            logger.exception("admin_user_created_email_failed", user_id=str(user.id))

    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_created",
        resource="user",
        resource_id=user.id,
        after=created,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return created


def _check_admin_target_guard(user: User, actor_id: uuid.UUID) -> None:
    """An admin must not neutralize their own account or a superuser's.

    Self-block would instantly revoke the acting admin's own sessions and
    denylist their token; blocking a superuser would let a mere ``users:write``
    holder disable the most privileged account. Mirrors the self-escalation
    guard in rbac_service.

    Note what this does *not* do: it says nothing about how many admins would be
    left. That question is asked by ``assert_not_last_admin``, which is async and
    therefore cannot live here, and it is asked at the three call sites that
    actually remove access. Between them the store is closed to a lone operator
    doing what two operators cannot: each of them removes one of the last two
    accounts, in two steps, and nothing in a per-account rule can see it.
    """
    from app.core.exceptions.handlers import ForbiddenError

    if user.id == actor_id:
        raise ForbiddenError(detail="You cannot perform this action on your own account")
    if user.is_superuser:
        raise ForbiddenError(detail="A superuser account cannot be modified by this action")


async def block_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Block user, revoke all active sessions, and denylist tokens in Redis."""
    from app.core.security.revocation import denylist_user
    from app.modules.users.domain.models import UserSession

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    # P0 "کاربران: محافظت آخرین ادمین". Asked before the write, so a refused
    # block leaves nothing to undo. The target may be a superuser, in which case
    # the guard above has already refused, and the count is simply never reached.
    from app.modules.users.application.last_admin_guard import assert_not_last_admin

    await assert_not_last_admin(db, user_id=user_id, operation="block")

    before = await get_user(db, user_id=user_id)
    user.is_active = False

    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await denylist_user(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_blocked",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


async def unblock_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Unblock user and remove from token denylist."""
    from app.core.security.revocation import remove_from_denylist

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    before = await get_user(db, user_id=user_id)
    user.is_active = True
    await remove_from_denylist(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_unblocked",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


async def soft_delete_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    reassign_to: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Soft-delete a user, optionally handing their content to a successor.

    P0 "کاربران: حذف کاربر با واگذاری محتوا". Thirty-four columns point at
    ``users`` with ``ON DELETE SET NULL``, so a user who leaves takes seven of
    them down to NULL: their posts, pages, comments, reviews of content,
    reusable blocks and uploads all become ownerless. An article attributed to
    nobody is not a deleted employee's article any more.

    ``reassign_to`` is optional and defaults to None. That default is the honest
    one — a caller who has not thought about attribution gets exactly what it
    asked for, rather than having content silently moved to whoever happens to be
    first in a dropdown. The route exposes it, and the admin page asks.

    The heir is checked before anything is written: reassigning to the departing
    user themselves moves every row and reports nothing, and reassigning to a
    non-existent account leaves the content pointing at nothing at all — the same
    outcome as not reassigning, reached by a longer route.
    """
    from datetime import UTC, datetime

    from app.core.security.revocation import denylist_user
    from app.modules.users.application import reassign_service
    from app.modules.users.domain.models import UserSession

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    from app.modules.users.application.last_admin_guard import assert_not_last_admin

    await assert_not_last_admin(db, user_id=user_id, operation="delete")

    if reassign_to is not None:
        if reassign_to == user_id:
            raise ValidationError(
                "کاربر جایگزین نمی‌تواند همان کاربر حذف‌شونده باشد."
            )
        heir = await db.get(User, reassign_to)
        if heir is None:
            raise NotFoundError(resource="User", detail=str(reassign_to))
        if heir.deleted_at is not None:
            raise ValidationError(
                "کاربر جایگزین حذف شده است و نمی‌تواند مالک محتوا شود."
            )

    before = await get_user(db, user_id=user_id)
    # Counted *before* the move, so the audit trail records what the account
    # actually held rather than a re-read of an already-emptied set.
    owned = await reassign_service.count_authored_content(db, user_id=user_id)

    moved: dict[str, int] = {}
    if reassign_to is not None:
        moved = await reassign_service.reassign_authored_content(
            db, from_user_id=user_id, to_user_id=reassign_to
        )
        await db.flush()

    user.deleted_at = datetime.now(UTC)
    user.is_active = False

    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await denylist_user(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_deleted",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return {
        "owned_before": owned,
        "reassigned": moved,
        "summary": reassign_service.summarise_reassignment(
            moved if reassign_to is not None else owned
        ),
    }


async def restore_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Restore a soft-deleted user."""
    from app.core.security.revocation import remove_from_denylist

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    _check_admin_target_guard(user, actor_id)

    before = await get_user(db, user_id=user_id)
    user.deleted_at = None
    user.is_active = True
    await remove_from_denylist(user_id)
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_restored",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


async def update_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Admin update of a user's fields."""
    # Same guard as block/unblock/soft_delete/restore. Without it this path was
    # the only admin route on the user that could rewrite a superuser's fields,
    # including their email — which is a takeover path, since the next password
    # reset goes to the address the attacker chose.
    target = await db.get(User, user_id)
    if target is None:
        raise NotFoundError(resource="User", detail=f"User {user_id} not found")
    _check_admin_target_guard(target, actor_id)

    before = await get_user(db, user_id=user_id)

    user_fields = {}
    profile_fields = {}

    for key in ("email", "is_active", "is_verified"):
        if key in data and data[key] is not None:
            user_fields[key] = data[key]

    if "email" in user_fields:
        existing = await db.execute(
            select(User).where(User.email == user_fields["email"], User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(detail="Email already in use")

    for key in ("first_name", "last_name", "display_name"):
        if key in data and data[key] is not None:
            profile_fields[key] = data[key]

    # B2B / مالیات تکلیفی fields (tax engine v1) — additive; only mapped when
    # explicitly provided so existing admin updates keep working untouched.
    for key in ("is_b2b", "company_name", "tax_exemption_certificate_no"):
        if key in data:
            profile_fields[key] = data[key]

    if user_fields:
        await db.execute(update(User).where(User.id == user_id).values(**user_fields))

    # Deactivation must take effect immediately (audit R4): kill refresh
    # sessions and put the user on the access-token denylist so live JWTs
    # are rejected for the rest of their TTL.
    if user_fields.get("is_active") is False:
        from app.core.security.revocation import denylist_user
        from app.modules.users.domain.models import UserSession

        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
            .values(is_revoked=True)
        )
        await denylist_user(user_id)
        await logger.ainfo("admin_user_deactivated_access_revoked", user_id=str(user_id))
    elif user_fields.get("is_active") is True:
        from app.core.security.revocation import remove_from_denylist

        await remove_from_denylist(user_id)

    if profile_fields:
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user_id, **profile_fields)
            db.add(profile)
        else:
            for k, v in profile_fields.items():
                setattr(profile, k, v)

    await db.flush()

    after = await get_user(db, user_id=user_id)

    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_updated",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return after


#: The bulk actions the admin users list offers, and the per-account guards each
#: one must still pass. An unknown action is refused rather than silently
#: no-op'ing, because a bulk call that returns "20 done" for an action nobody
#: implemented is the worst of both worlds.
BULK_USER_ACTIONS = {"block", "unblock", "delete", "restore", "set_role"}


async def bulk_users(
    db: AsyncSession,
    *,
    ids: list[uuid.UUID],
    action: str,
    actor_id: uuid.UUID,
    role_slug: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Apply one action to many accounts, reporting a per-account outcome.

    Partial success is the contract, exactly as in ``BlogService.bulk_posts``:
    an operator selecting twenty accounts may not be allowed to touch all of
    them — the self/superuser guard and the last-admin guard each refuse some —
    and a bare boolean would make "20 selected, 18 done, 2 refused" read as
    "20 done". Every id gets an entry in ``results`` (``ok`` or ``error``) and
    the counts say what really happened.

    Each account is acted on through the *same* single-account function the
    individual buttons call, so a bulk call is exactly as strict as the
    equivalent N separate clicks: the guards, the session revocation and the
    audit row all still run per user. Re-implementing the writes here would be
    a second code path to keep in step, and the first one to drift.

    ``set_role`` delegates to the RBAC service for the same reason — role
    assignment carries its own self-escalation guard, and that guard must see
    the real caller's payload.
    """
    from app.core.exceptions.handlers import ValidationError

    if action not in BULK_USER_ACTIONS:
        raise ValidationError(f"عملیات گروهی ناشناخته: {action}")
    if action == "set_role" and not role_slug:
        raise ValidationError("برای تغییر گروهی نقش، یک نقش انتخاب کنید.")

    # Resolved once, not per user: a typo'd or deleted role must fail the whole
    # request rather than half of it, and the operator is looking at one form.
    role_id: uuid.UUID | None = None
    if action == "set_role":
        role_row = (
            await db.execute(select(Role).where(Role.slug == role_slug))
        ).scalar_one_or_none()
        if role_row is None:
            raise NotFoundError(resource="Role", detail=str(role_slug))
        role_id = role_row.id

    results: list[dict[str, Any]] = []
    ok = 0
    failed = 0

    for user_id in ids:
        try:
            if action == "block":
                await block_user(
                    db, user_id=user_id, actor_id=actor_id,
                    ip_address=ip_address, user_agent=user_agent,
                )
            elif action == "unblock":
                await unblock_user(
                    db, user_id=user_id, actor_id=actor_id,
                    ip_address=ip_address, user_agent=user_agent,
                )
            elif action == "delete":
                # No ``reassign_to`` in bulk: handing every selected account's
                # content to one heir is almost never what "delete these" means,
                # and doing it silently would move a whole team's articles in
                # one click. The single-account dialog is where attribution is
                # decided.
                await soft_delete_user(
                    db, user_id=user_id, actor_id=actor_id,
                    ip_address=ip_address, user_agent=user_agent,
                )
            elif action == "restore":
                await restore_user(
                    db, user_id=user_id, actor_id=actor_id,
                    ip_address=ip_address, user_agent=user_agent,
                )
            elif action == "set_role":
                from app.modules.rbac.application import rbac_service

                await rbac_service.assign_roles_to_user(
                    db,
                    user_id=user_id,
                    role_ids=[role_id] if role_id is not None else [],
                    actor_id=actor_id,
                )
        except Exception as exc:  # noqa: BLE001 - one refusal must not stop the rest
            failed += 1
            results.append({
                "id": str(user_id),
                "ok": False,
                "error": str(exc),
            })
        else:
            ok += 1
            results.append({"id": str(user_id), "ok": True, "error": None})

    await db.commit()
    return {
        "action": action,
        "ok": ok,
        "failed": failed,
        "total": len(ids),
        "results": results,
    }


# ── Admin registration approval ──────────────────────────────────────────────


async def approve_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Admit a pending account.

    P1 "کاربران: تأیید حساب توسط مدیر". Approving is a write of its own, not
    "unblock": the account was never blocked, it was never admitted, and an
    audit trail that says "unblocked" for a first admission is wrong.

    Approving a non-pending account is refused rather than treated as a no-op,
    so an operator double-clicking does not produce two admissions in the log.
    """
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    if not user.pending_approval:
        raise ConflictError(detail="This account is not awaiting approval")

    before = await get_user(db, user_id=user_id)
    user.pending_approval = False
    user.is_active = True
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_approved",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


async def reject_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Refuse a pending account.

    Kept as a soft state — the row stays, ``pending_approval`` clears and
    ``is_active`` goes false, which is exactly the blocked state — so a
    rejection is reversible with the existing unblock action and the account's
    data is not destroyed by a click.
    """
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError(resource="User")

    if not user.pending_approval:
        raise ConflictError(detail="This account is not awaiting approval")

    before = await get_user(db, user_id=user_id)
    user.pending_approval = False
    user.is_active = False
    await db.flush()

    after = await get_user(db, user_id=user_id)
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_rejected",
        resource="user",
        resource_id=user_id,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return after


# ── Admin session management ─────────────────────────────────────────────────


async def list_user_sessions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Every active session an account holds, for an operator to review.

    P1 "کاربران: مدیریت نشست‌های دیگر کاربران از پنل". "Sign out everywhere" was
    self-service only: a user who suspected a stolen session could do something,
    but the operator handling the support ticket could see nothing and do
    nothing. This is the read half; ``revoke_user_session`` is the write half.

    Revoked sessions are filtered out — the same predicate the self-service list
    uses — because a list that mixes live and dead rows makes "how many devices
    is this account on" unanswerable.
    """
    from app.modules.users.domain.models import UserSession

    rows = (
        await db.execute(
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .order_by(UserSession.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": s.id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "device_info": s.device_info,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "is_revoked": s.is_revoked,
        }
        for s in rows
    ]


async def revoke_user_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Kill one session of another account, at an operator's request.

    Scoped by ``user_id`` as well as ``session_id`` so an operator cannot revoke
    a session that belongs to a different account by guessing its id — the same
    owner predicate the self-service revoke uses, just with the owner supplied
    by the route rather than the token.

    The acting admin is the ``actor_id`` in the audit row, so a forced logout is
    attributable: "your session was ended" with no record of who ended it is not
    a support action, it is a mystery.
    """
    from app.modules.users.domain.models import UserSession

    result = await db.execute(
        update(UserSession)
        .where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
        )
        .values(is_revoked=True)
    )
    cursor = cast("CursorResult[Any]", result)
    if (cursor.rowcount or 0) == 0:
        raise NotFoundError(resource="Session")

    await db.flush()
    await log_action(
        db,
        actor_id=actor_id,
        action="admin.user_session_revoked",
        resource="user_session",
        resource_id=session_id,
        after={"user_id": str(user_id)},
    )
    await logger.ainfo(
        "admin_session_revoked",
        user_id=str(user_id),
        session_id=str(session_id),
        actor_id=str(actor_id),
    )


# ── Address CRUD ─────────────────────────────────────────────────────────────


async def get_addresses(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[Address]:
    """List all addresses belonging to a user."""
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_address(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> Address:
    """Create a new address for a user."""
    # If this is marked as default, unset any existing default
    if data.get("is_default", False):
        await db.execute(
            update(Address)
            .where(Address.user_id == user_id, Address.is_default.is_(True))
            .values(is_default=False)
        )

    address = Address(user_id=user_id, **data)
    db.add(address)
    await db.flush()

    await logger.ainfo(
        "address_created",
        user_id=str(user_id),
        address_id=str(address.id),
    )
    return address


async def update_address(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
    data: dict[str, Any],
) -> Address:
    """Update an existing address."""
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    result = await db.execute(stmt)
    address = result.scalar_one_or_none()

    if address is None:
        raise NotFoundError(resource="Address")

    # Handle default flag
    if data.get("is_default", False):
        await db.execute(
            update(Address)
            .where(
                Address.user_id == user_id,
                Address.id != address_id,
                Address.is_default.is_(True),
            )
            .values(is_default=False)
        )

    for key, value in data.items():
        if value is not None:
            setattr(address, key, value)

    await db.flush()

    await logger.ainfo(
        "address_updated",
        user_id=str(user_id),
        address_id=str(address_id),
    )
    return address


async def delete_address(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
) -> None:
    """Delete an address belonging to a user."""
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    result = await db.execute(stmt)
    address = result.scalar_one_or_none()

    if address is None:
        raise NotFoundError(resource="Address")

    await db.delete(address)
    await db.flush()

    await logger.ainfo(
        "address_deleted",
        user_id=str(user_id),
        address_id=str(address_id),
    )


async def list_failed_attempts(
    db: AsyncSession,
    *,
    attempt_type: str | None = None,
    identifier: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """Persisted failed login/OTP/KYC attempts for the admin panel (Karta failed_attempts).

    The search term is bound as a parameter via ``contains(autoescape=True)``;
    user-supplied LIKE wildcards are escaped, never concatenated (P1.4).
    """
    from app.modules.users.domain.kyc_models import AttemptType, FailedAttempt

    stmt = select(FailedAttempt).order_by(FailedAttempt.created_at.desc())
    if attempt_type:
        stmt = stmt.where(FailedAttempt.attempt_type == AttemptType(attempt_type))
    if identifier:
        stmt = stmt.where(FailedAttempt.identifier.contains(identifier, autoescape=True))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "identifier": r.identifier,
            "attempt_type": (
                r.attempt_type.value if hasattr(r.attempt_type, "value") else str(r.attempt_type)
            ),
            "ip_address": r.ip_address,
            "user_agent": r.user_agent,
            "created_at": r.created_at,
        }
        for r in rows
    ]


async def count_failed_attempts(
    db: AsyncSession,
    *,
    attempt_type: str | None = None,
    identifier: str | None = None,
) -> int:
    """Count failed attempts matching the admin panel filters."""
    from app.modules.users.domain.kyc_models import AttemptType, FailedAttempt

    stmt = select(func.count()).select_from(FailedAttempt)
    if attempt_type:
        stmt = stmt.where(FailedAttempt.attempt_type == AttemptType(attempt_type))
    if identifier:
        stmt = stmt.where(FailedAttempt.identifier.contains(identifier, autoescape=True))
    return int((await db.execute(stmt)).scalar_one() or 0)


async def list_trust_profiles(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Any], int]:
    """All user trust profiles, riskiest first (anti-fraud admin panel)."""
    from app.modules.users.domain.kyc_models import UserTrustProfile

    total_result = await db.execute(select(func.count()).select_from(UserTrustProfile))
    total = int(total_result.scalar_one() or 0)
    rows = (
        (
            await db.execute(
                select(UserTrustProfile)
                .order_by(UserTrustProfile.risk_score.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total
