"""Creating an account with a role assigns the role in the same call.

Every layer of this existed and one was broken: `create_user_admin` built
`UserRole(user_id, role_id, assigned_by=...)`, but `user_roles` has no
`assigned_by` column — so the call raised `TypeError` and an account created
*with* a role was never created at all. It went unnoticed because the separate
role editor's path omits the field, and nothing exercised the create-with-role
path end to end.

This drives the real service and asserts the role lands.

Run:  python .p1-tests/users_create_role_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.rbac.domain.models import Role, UserRole
from app.modules.users.application import user_service
from app.modules.users.domain.models import User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    phone = "97" + uuid.uuid4().hex[:9]
    plain_phone = "97" + uuid.uuid4().hex[:9]
    created_phones = [phone, plain_phone]

    async with Session() as db:
        admin = (
            await db.execute(select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()
        vendor = (
            await db.execute(select(Role).where(Role.slug == "vendor"))
        ).scalars().first()
        if vendor is None:
            vendor = Role(name="Vendor", slug="vendor", is_system=False)
            db.add(vendor)
            await db.flush()

    try:
        async with Session() as db:
            try:
                created = await user_service.create_user_admin(
                    db,
                    data={
                        "phone": phone,
                        "password": "Test1234!",
                        "first_name": "P1Role",
                        "last_name": "Probe",
                        "role_slugs": ["vendor"],
                    },
                    actor_id=admin.id,
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001 — report, do not crash the probe
                check("1. create-with-role succeeds", False, f"{type(exc).__name__}: {exc}")
                created = None

        if created is not None:
            check("1. create-with-role succeeds", True)
            async with Session() as db:
                roles = (
                    await db.execute(
                        select(Role.slug)
                        .join(UserRole, UserRole.role_id == Role.id)
                        .where(UserRole.user_id == created["id"])
                    )
                ).scalars().all()
                check("1b. and the role is assigned", "vendor" in roles,
                      f"roles={list(roles)}")

        # 2. A create with no role still works (the default customer path),
        #    so the fix did not tie creation to the presence of a role.
        async with Session() as db:
            try:
                await user_service.create_user_admin(
                    db,
                    data={
                        "phone": plain_phone,
                        "password": "Test1234!",
                        "first_name": "P1NoRole",
                    },
                    actor_id=admin.id,
                )
                await db.commit()
                check("2. create with no role still works", True)
            except Exception as exc:  # noqa: BLE001
                check("2. create with no role still works", False,
                      f"{type(exc).__name__}: {exc}")
    finally:
        # Remove both probes by phone, whatever happened above.
        async with Session() as db:
            rows = (
                await db.execute(
                    select(User).where(User.phone.in_(created_phones))
                )
            ).scalars().all()
            for u in rows:
                await db.execute(delete(UserRole).where(UserRole.user_id == u.id))
                await db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
                await db.execute(delete(User).where(User.id == u.id))
            await db.commit()
            left = (
                await db.execute(
                    select(User.id).where(User.phone.in_(created_phones))
                )
            ).scalars().all()
            check("3. probes cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nCREATE-ROLE GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: creating an account with a role assigns it, and without one "
          "still works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))