"""The users list filters by role on the server, and can see deleted rows.

Two gaps, one shape. The role filter ran client-side over the current page, so
"show me the vendors" answered with the vendors *on this page* — and the
soft-delete path shipped with a restore endpoint no view could reach, because
the list hid deleted rows with no way to ask for them.

The assertions are server-side facts, checked through the HTTP route so the
query string is parsed as the admin page sends it:

  * a role filter returns only users holding that role, across the whole table
    (the probe user is off page 1, so a client-side filter could not have found
    it);
  * include_deleted surfaces a soft-deleted user, and its absence hides one.

Run:  python .p1-tests/users_role_filter_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.rbac.domain.models import Role, UserRole
from app.modules.users.domain.models import User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    probe_phone = "98" + uuid.uuid4().hex[:9]
    probe_deleted_phone = "98" + uuid.uuid4().hex[:9]

    async with Session() as db:
        admin = (
            await db.execute(select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()
        # A vendor role, and a probe user carrying it.
        vendor = (
            await db.execute(select(Role).where(Role.slug == "vendor"))
        ).scalars().first()
        if vendor is None:
            vendor = Role(name="Vendor", slug="vendor", is_system=False)
            db.add(vendor)
            await db.flush()
        probe = User(phone=probe_phone, is_active=True, is_verified=True,
                     author_slug=f"p1vend{marker}")
        db.add(probe)
        await db.flush()
        db.add(UserProfile(user_id=probe.id, first_name=f"VENDOR{marker}"))
        db.add(UserRole(user_id=probe.id, role_id=vendor.id))

        # A soft-deleted user.
        gone = User(phone=probe_deleted_phone, is_active=True, is_verified=True,
                    deleted_at=datetime.now(UTC), author_slug=f"p1gone{marker}")
        db.add(gone)
        await db.flush()
        db.add(UserProfile(user_id=gone.id, first_name=f"GONE{marker}"))
        await db.commit()
        probe_id, gone_id = probe.id, gone.id

    token = create_access_token(
        str(admin.id), {"roles": ["super_admin"], "permissions": ["*"]}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        try:
            # 1. role=vendor returns our vendor probe.
            r = await client.get(
                "/api/v1/users/admin/users",
                headers=headers,
                params={"role": "vendor", "page_size": 100},
            )
            check("1. role=vendor answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:160]}")
            ids = {i["id"] for i in r.json()["items"]}
            check("1b. and includes the vendor probe", str(probe_id) in ids,
                  f"probe not in {len(ids)} rows")
            # 1c. Every returned row holds the role (the server did the filter).
            roles_ok = all(
                "vendor" in (i.get("roles") or []) for i in r.json()["items"]
            )
            check("1c. and every returned row holds the role", roles_ok,
                  "a non-vendor slipped through the server filter")

            # 2. The deleted user is hidden by default...
            r = await client.get(
                "/api/v1/users/admin/users",
                headers=headers,
                params={"search": probe_deleted_phone},
            )
            ids = {i["id"] for i in r.json()["items"]}
            check("2. a soft-deleted user is hidden by default",
                  str(gone_id) not in ids, "the deleted row appeared unasked")

            # ...and shown with include_deleted.
            r = await client.get(
                "/api/v1/users/admin/users",
                headers=headers,
                params={"search": probe_deleted_phone, "include_deleted": "true"},
            )
            ids = {i["id"] for i in r.json()["items"]}
            check("3. include_deleted surfaces it", str(gone_id) in ids,
                  "the restore view cannot see the row it must restore")
            row = next((i for i in r.json()["items"] if i["id"] == str(gone_id)), {})
            check("3b. and the row carries deleted_at",
                  bool(row.get("deleted_at")), f"deleted_at={row.get('deleted_at')!r}")
        finally:
            async with Session() as db:
                for uid in (probe_id, gone_id):
                    await db.execute(delete(UserRole).where(UserRole.user_id == uid))
                    await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                    await db.execute(delete(User).where(User.id == uid))
                await db.commit()
            async with Session() as db:
                left = (
                    await db.execute(
                        select(User.id).where(
                            User.phone.in_([probe_phone, probe_deleted_phone])
                        )
                    )
                ).scalars().all()
                check("4. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nUSER-FILTER GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the role filter is server-side and the restore view can see "
          "deleted rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))