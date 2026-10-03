"""Application passwords authenticate over HTTP Basic, as WordPress does.

P2 "REST: احراز Basic با Application Password". The item was reported as a
gap ("only Bearer is accepted"); recon and a live probe showed the path is in
fact complete — so this fixture exists to *keep* it complete. A working
feature with no gate is one refactor away from silently reverting, and the
failure mode is quiet: a WordPress client script gets 401 and its author
concludes the store does not support application passwords at all.

Server-side facts over the real dependency:

  * ``Authorization: Bearer <app_password>`` works (the original path);
  * ``Authorization: Basic base64(user:app_password)`` works;
  * the username is NOT trusted — a different username with the right password
    authenticates as the password's owner, which is what makes a leaked script
    config useless without the password;
  * a revoked credential is refused on both schemes.

Run:  python .p1-tests/basic_auth_app_password_test.py
"""

from __future__ import annotations

import asyncio
import base64
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.auth.application.application_password_service import (
    create_application_password,
    revoke_application_password,
)
from app.modules.rbac.domain.models import UserRole
from app.modules.users.domain.models import ApplicationPassword, User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def basic(user: str, password: str) -> dict[str, str]:
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    phone = "09" + "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])

    created_user_ids: list[uuid.UUID] = []

    try:
        async with Session() as db:
            u = User(
                phone=phone, is_active=True, is_verified=True,
                author_slug=f"p1ba{marker}",
            )
            db.add(u)
            await db.flush()
            db.add(UserProfile(user_id=u.id, first_name=f"BA{marker}"))
            await db.commit()
            uid = u.id
            created_user_ids.append(u.id)

            row, secret = await create_application_password(
                db, user_id=uid, name=f"basic-probe-{marker}"
            )
            await db.commit()
            ap_id = row.id

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 1. The original path still works.
            r = await client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {secret}"}
            )
            check("1. Bearer with the app password answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")

            # 2. Basic with the account's own phone as username.
            r = await client.get("/api/v1/auth/me", headers=basic(phone, secret))
            check("2. Basic with the account's username answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")

            # 3. THE SECURITY PROPERTY: the username is not trusted. A caller
            #    naming somebody else authenticates as the password's owner.
            r = await client.get(
                "/api/v1/auth/me", headers=basic("somebody-else", secret)
            )
            check("3. Basic with a wrong username still answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")
            if r.status_code == 200:
                check("3b. and the identity is the password's owner",
                      r.json().get("phone") == phone,
                      f"phone={r.json().get('phone')!r}")

            # 4. A revoked credential is refused on both schemes.
            async with Session() as db:
                await revoke_application_password(
                    db, user_id=uid, app_password_id=ap_id
                )
                await db.commit()

            r = await client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {secret}"}
            )
            check("4. the revoked credential fails over Bearer (401)",
                  r.status_code == 401, f"status {r.status_code}")
            r = await client.get("/api/v1/auth/me", headers=basic(phone, secret))
            check("4b. and over Basic too (401)",
                  r.status_code == 401, f"status {r.status_code}")
    finally:
        async with Session() as db:
            for uid in created_user_ids:
                await db.execute(delete(ApplicationPassword).where(ApplicationPassword.user_id == uid))
                await db.execute(delete(UserRole).where(UserRole.user_id == uid))
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            left = (
                await db.execute(select(User.id).where(User.phone == phone))
            ).scalars().all()
            check("5. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nBASIC AUTH GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: application passwords authenticate over both Bearer and Basic, "
          "the username is not trusted, and revocation closes both paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))