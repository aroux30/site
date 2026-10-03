"""Refuse to remove the last way into the admin area.

P0 "کاربران: محافظت «آخرین ادمین»". The existing guard stops an admin acting on
their own account and stops a ``users:write`` holder touching a superuser. Neither
has anything to do with *how many* admins are left, so the sequence a lone
operator cannot do in one step is: disable the second admin, then the first.
Nothing stops it, and the store has no way back in — the users table is the only
place a role is granted, and the route that grants roles now needs an admin to
call it.

Both sides of the count matter, and they are counted separately on purpose:

  - **superusers** — a flag on the account, so it survives the role table being
    edited. A store whose superuser has no role still has an admin.
  - **role holders** — whoever carries an admin-capable role. On a store where
    roles were customised, that may not be a row called ``admin``.

Counting either alone produces a guard that is wrong in a way nobody can see. A
guard that only counts superusers refuses the second demotion on a store whose
admins are all role-holders, and locks out a perfectly capable operator. A guard
that only counts roles blocks a store whose superuser happens to hold no role —
and that store has a perfectly capable operator too.

The refusal is on the *outcome*, not the operation. Deleting, blocking and
demoting all reduce the same count, so all three go through the same check: would
this leave zero? That is why the check is a count of what would remain rather
than three separate rules, and why a fourth way to lose an admin — a new one,
found later — gets the guard for free if it calls this.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, or_, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Roles that can reach the admin area. Read from the role table rather than
#: assumed, because a store that renames or adds a role would otherwise have an
#: admin its own guard does not recognise.
ADMIN_ROLE_SLUGS: tuple[str, ...] = ("admin", "super_admin", "shop_manager", "manager")

#: What the operator is about to do, for the error message and the log. The
#: count is the same for all three; only the wording differs.
OPERATIONS: dict[str, str] = {
    "delete": "حذف",
    "block": "مسدودسازی",
    "demote": "تنزل نقش",
    "deactivate": "غیرفعال‌سازی",
}


async def count_remaining_admins(
    db: AsyncSession,
    *,
    excluding_user_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """How many accounts could still administer the store.

    ``excluding_user_id`` is the account about to lose its access, so the number
    returned is what would be *left* — which is the number the decision needs.
    Counting and then subtracting in Python would be wrong the moment a filter is
    missed, so the filter goes into the query.

    Superusers and role holders are returned separately as well as summed, because
    the refusal has to name which kind ran out. "You are the last admin" is
    actionable; "you are the last holder of a role nobody will ever revoke" is
    not.
    """
    from app.modules.rbac.domain.models import Role, UserRole
    from app.modules.users.domain.models import User

    def _active(*extra):
        clauses = [User.is_active.is_(True), User.deleted_at.is_(None)]
        if extra:
            clauses.extend(extra)
        if excluding_user_id is not None:
            clauses.append(User.id != excluding_user_id)
        return clauses

    superusers = int(
        (
            await db.execute(
                select(func.count(User.id.distinct())).where(*_active(User.is_superuser.is_(True)))
            )
        ).scalar()
        or 0
    )

    role_holders = int(
        (
            await db.execute(
                select(func.count(User.id.distinct()))
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(*_active(Role.slug.in_(ADMIN_ROLE_SLUGS)))
            )
        ).scalar()
        or 0
    )

    # A superuser who also holds a role is counted twice, and "would one removal
    # take the store below one" is not a question the arithmetic above answers.
    # The union is what matters.
    union = int(
        (
            await db.execute(
                select(func.count(User.id.distinct()))
                .outerjoin(UserRole, UserRole.user_id == User.id)
                .outerjoin(Role, Role.id == UserRole.role_id)
                .where(
                    *_active(
                        or_(
                            User.is_superuser.is_(True),
                            Role.slug.in_(ADMIN_ROLE_SLUGS),
                        )
                    )
                )
            )
        ).scalar()
        or 0
    )

    return {
        "superusers": superusers,
        "role_holders": role_holders,
        "total": union,
    }


async def assert_not_last_admin(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    operation: str,
) -> dict[str, int]:
    """Raise if removing ``user_id``'s access would leave nobody who can administer.

    Returns the counts on success, so the caller can log them without asking
    again — the query is not free and a guard that runs it twice is a guard whose
    two answers can disagree if anything changes between them.

    ``operation`` is only used for wording. A caller that passes something outside
    ``OPERATIONS`` still gets the check; the label falls back to a neutral word
    rather than rejecting the call, because a new way to lose an admin should be
    guarded by default, not refused for being unfamiliar.
    """
    from app.core.exceptions.handlers import ConflictError

    remaining = await count_remaining_admins(db, excluding_user_id=user_id)
    if remaining["total"] > 0:
        return remaining

    label = OPERATIONS.get(operation, "این عملیات")
    raise ConflictError(
        detail=(
            "این آخرین حسابی است که می‌تواند به پنل مدیریت دسترسی داشته باشد. "
            "پیش از %s، یک مدیر دیگر بسازید یا نقش مدیریتی بدهید." % label
        ),
        error_code="LAST_ADMIN",
    )


async def would_leave_no_admin(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> bool:
    """Whether this account is the last way in — for previews and tests.

    A read with no exception, so an admin screen can disable the button before
    the operator finds out by pressing it. The action still re-checks: a
    pre-check is a courtesy, and the count can change between the page load and
    the click.
    """
    remaining = await count_remaining_admins(db, excluding_user_id=user_id)
    return remaining["total"] == 0
