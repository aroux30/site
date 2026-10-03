"""Admin approval of registrations: hold, refuse a session, approve, reject.

P1 "کاربران: تأیید حساب توسط مدیر". With `registration_approval_required` on,
a signup creates the account but issues no session, and both the password and
OTP login paths refuse with ACCOUNT_PENDING_APPROVAL until an operator approves.

Server-side facts over the real routes:

  * registration with the setting on returns no tokens and creates a pending row;
  * password login for a pending account is refused with the pending code;
  * the admin list filter `pending_approval=true` finds it;
  * approve clears the flag and the account can then log in;
  * a second approve is refused (not a silent no-op);
  * reject marks the account inactive.

Run:  python .p1-tests/registration_approval_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.rbac.domain.models import UserRole
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def iran_phone() -> str:
    digits = "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])
    return "09" + digits


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    phone_pending = iran_phone()
    phone_reject = iran_phone()
    password = "Passw0rd!234"

    created_user_ids: list[uuid.UUID] = []
    original_approval: str | None = None
    original_enabled: str | None = None

    try:
        async with Session() as db:
            original_approval = await SiteOptionsService.get(db, "registration_approval_required")
            original_enabled = await SiteOptionsService.get(db, "registration_enabled")
            admin = (
                await db.execute(select(User).where(User.is_superuser == True).limit(1))
            ).scalars().first()
            # Turn approval ON for the duration of the test.
            await SiteOptionsService.set(db, "registration_approval_required", "1")

        admin_token = create_access_token(
            str(admin.id), {"roles": ["super_admin"], "permissions": ["*"]}
        )
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        # /auth/register is rate-limited per client IP (5/minute), and the
        # limiter reads X-Forwarded-For with TRUSTED_PROXY_COUNT hops trusted
        # (2 here), so the forwarded header carries that many entries with a
        # per-run IP second-from-right. Without this, running the fixture twice
        # in a minute 429s on its own previous traffic.
        probe_ip = f"10.98.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
        reg_headers = {"X-Forwarded-For": f"{probe_ip}, 10.0.0.1"}

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 1. Register while approval is required.
            r = await client.post(
                "/api/v1/auth/register",
                headers=reg_headers,
                json={
                    "phone": phone_pending,
                    "password": password,
                    "first_name": "Pending",
                    "last_name": "Probe",
                },
            )
            check("1. registration answers 201",
                  r.status_code == 201, f"status {r.status_code} {r.text[:200]}")
            body = r.json()
            check("1b. no refresh token was issued",
                  not body.get("refresh_token"),
                  f"refresh_token={body.get('refresh_token')!r}")

            async with Session() as db:
                u = (
                    await db.execute(select(User).where(User.phone == phone_pending))
                ).scalar_one_or_none()
                check("1c. the account was created",
                      u is not None, "no user row")
                if u is None:
                    raise SystemExit(1)
                created_user_ids.append(u.id)
                user_id = u.id
                check("1d. it is marked pending_approval",
                      bool(u.pending_approval), "pending_approval is false")

            # 2. Password login is refused with the pending code.
            r = await client.post(
                "/api/v1/auth/login",
                json={"phone": phone_pending, "password": password},
            )
            check("2. login for a pending account is refused (401)",
                  r.status_code == 401, f"status {r.status_code} {r.text[:160]}")
            code = (r.json().get("error") or {}).get("code")
            check("2b. with the pending-approval code",
                  code == "ACCOUNT_PENDING_APPROVAL", f"code={code!r}")

            # 3. The admin approval queue finds it.
            r = await client.get(
                "/api/v1/users/admin/users",
                headers=admin_headers,
                params={"pending_approval": "true", "search": phone_pending},
            )
            check("3. the pending filter answers 200",
                  r.status_code == 200, f"status {r.status_code}")
            ids = {i["id"] for i in r.json()["items"]}
            check("3b. the pending account is in the queue",
                  str(user_id) in ids, f"ids={ids}")

            # 4. Approve it.
            r = await client.post(
                f"/api/v1/users/admin/users/{user_id}/approve", headers=admin_headers
            )
            check("4. approve answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            check("4b. the response shows it no longer pending",
                  r.json().get("pending_approval") is False,
                  f"pending_approval={r.json().get('pending_approval')!r}")

            # 4c. And it is out of the queue.
            r = await client.get(
                "/api/v1/users/admin/users",
                headers=admin_headers,
                params={"pending_approval": "true", "search": phone_pending},
            )
            ids = {i["id"] for i in r.json()["items"]}
            check("4c. the approved account left the queue",
                  str(user_id) not in ids, f"ids={ids}")

            # 5. Now login works.
            r = await client.post(
                "/api/v1/auth/login",
                json={"phone": phone_pending, "password": password},
            )
            check("5. login after approval succeeds",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")

            # 6. A second approve is refused (not a silent no-op).
            r = await client.post(
                f"/api/v1/users/admin/users/{user_id}/approve", headers=admin_headers
            )
            check("6. a second approve is refused (409)",
                  r.status_code == 409, f"status {r.status_code} {r.text[:160]}")

            # 7. Reject a fresh pending account → inactive.
            r = await client.post(
                "/api/v1/auth/register",
                headers=reg_headers,
                json={
                    "phone": phone_reject,
                    "password": password,
                    "first_name": "Reject",
                    "last_name": "Probe",
                },
            )
            check("7. second registration answers 201",
                  r.status_code == 201, f"status {r.status_code}")
            async with Session() as db:
                u2 = (
                    await db.execute(select(User).where(User.phone == phone_reject))
                ).scalar_one()
                created_user_ids.append(u2.id)
                reject_id = u2.id

            r = await client.post(
                f"/api/v1/users/admin/users/{reject_id}/reject", headers=admin_headers
            )
            check("7b. reject answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")
            async with Session() as db:
                u2 = await db.get(User, reject_id)
                check("7c. the rejected account is inactive",
                      bool(u2 and not u2.is_active and not u2.pending_approval),
                      f"active={u2.is_active if u2 else None} pending={u2.pending_approval if u2 else None}")
    finally:
        async with Session() as db:
            await SiteOptionsService.set(
                db, "registration_approval_required", original_approval
            )
            await SiteOptionsService.set(db, "registration_enabled", original_enabled)
        async with Session() as db:
            for uid in created_user_ids:
                await db.execute(delete(UserRole).where(UserRole.user_id == uid))
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            restored = await SiteOptionsService.get(db, "registration_approval_required")
            check("8. the real approval option was restored",
                  restored == original_approval,
                  f"restored={restored!r} expected={original_approval!r}")
            left = (
                await db.execute(
                    select(User.id).where(User.phone.in_([phone_pending, phone_reject]))
                )
            ).scalars().all()
            check("8b. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nREGISTRATION APPROVAL GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: a pending signup gets no session, login is refused with the "
          "pending code, and approve/reject work as their own actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))