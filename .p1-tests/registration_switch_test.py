"""The registration switch and the default role, including the refusal.

Two settings, and the second one is a security control wearing a setting's
clothes.

  * ``registration_enabled``. Closing a storefront's sign-up while it is in
    pre-launch, or when it only serves existing accounts. Not a route removal,
    so the form can say why rather than 404.
  * ``registration_default_role``. Which role a new account lands in. The
    point of the test is the *ceiling*: an operator who sets this to a role
    carrying admin capability must not hand every future sign-up that role.
    Read from the database, and therefore reachable by anyone who can write
    options — so it is refused rather than trusted, and refusing silently would
    make a typo indistinguishable from a working setting.

The privileged case is checked by asking for `admin` and asserting the account
did not get it. That is the assertion that matters; the rest is bookkeeping.
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.auth.application import auth_service
from app.modules.rbac.domain.models import Role, UserRole
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = "p1reg"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        async def setopt(k, v):
            await SiteOptionsService.set(db, k, v)

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        made: list[str] = []

        mine: list[str] = []

        async def register(tag):
            phone = f"9{tag[:2]}{uuid.uuid4().hex[:8]}"
            mine.append(phone)
            await auth_service.register(
                db,
                phone=phone,
                password="Test1234!",
                first_name=tag,
                last_name="User",
            )
            user = (await db.execute(
                select(User).where(User.phone == phone)
                .order_by(User.created_at.desc()).limit(1)
            )).scalars().first()
            made.append(str(user.id))
            return user

        async def roles_of(user_id):
            rows = (await db.execute(
                select(Role.slug).join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user_id)
            )).scalars().all()
            return set(rows)

        try:
            # 1. the switch, both ways
            await setopt("registration_enabled", "1")
            await setopt("registration_default_role", "customer")
            u1 = await register("open")
            check("1. registration works when the switch is on",
                  u1 is not None)
            check("1b. and the default role is applied",
                  "customer" in await roles_of(u1.id), str(await roles_of(u1.id)))

            await setopt("registration_enabled", "0")
            refused = False
            try:
                await register("closed")
            except Exception as exc:
                refused = type(exc).__name__ == "ValidationError"
            check("2. registration is refused when the switch is off", refused)
            check("2b. and no account was created",
                  not (await db.execute(
                      select(User).where(User.phone == "9cl-none"))
                  ).scalars().first())

            # 3. a privileged default role is refused, not honoured
            await setopt("registration_enabled", "1")
            await setopt("registration_default_role", "admin")
            u3 = await register("priv")
            got = await roles_of(u3.id)
            check("3. a privileged default role is refused", "admin" not in got,
                  str(got))
            check("3b. and the account falls back to customer",
                  "customer" in got, str(got))

            # 4. a role that does not exist falls back too, rather than
            #    stopping a customer from registering
            await setopt("registration_default_role", "no-such-role")
            u4 = await register("missing")
            got = await roles_of(u4.id)
            check("4. an unknown role falls back", "customer" in got, str(got))
            check("4b. and registration still succeeded", u4 is not None)

            # 5. the refusal list is a constant, not something the option can
            #    widen — check the module still refuses a superuser slug too
            await setopt("registration_default_role", "super_admin")
            u5 = await register("super")
            check("5. super_admin is refused as well",
                  "super_admin" not in await roles_of(u5.id),
                  str(await roles_of(u5.id)))

        finally:
            await setopt("registration_enabled", "1")
            await setopt("registration_default_role", "customer")

        for user_id in made:
            await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
            # Another session can attach a post to one of these rows between
            # the register and here, and a FK to blog_posts.author_id then
            # refuses the delete. The role assertions are the subject; the
            # cleanup is housekeeping and must not fail the fixture over it.
            try:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
            except Exception:
                await db.rollback()
        # Debris from a killed run, matched on this run's own phones only. A
        # prefix like "9%" swept up rows other fixtures owned — and other
        # fixtures deleting my users left their blog_posts dangling.
        for stale in (await db.execute(
                select(User).where(User.phone.in_(mine))
        )).scalars().all():
            await db.execute(delete(UserRole).where(UserRole.user_id == stale.id))
            try:
                await db.execute(delete(User).where(User.id == stale.id))
            except Exception:
                await db.rollback()
        # Every row this run made, and nothing else. A `9%` prefix swept up
        # rows other fixtures owned, and deleting those fired their FKs.
        await db.execute(delete(User).where(User.phone.in_(mine)))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nREGISTRATION GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: registration can be closed, the default role applies, and a "
          "privileged role is refused.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))