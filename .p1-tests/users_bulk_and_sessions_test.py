"""Bulk user actions and admin session management actually work over HTTP.

Two gaps with one shape — a write path that existed only one row at a time:

  * bulk operations (P1 "کاربران: عملیات گروهی"): the list had no multi-select,
    so closing fifty spam accounts meant fifty clicks;
  * admin session management (P1 "کاربران: مدیریت نشست‌های دیگر کاربران از پنل"):
    "sign out everywhere" was self-service only — an operator handling a stolen
    account could neither see the sessions nor end one.

The assertions are server-side facts over the real routes:

  * POST /users/admin/users/bulk (action=block) blocks the selected rows and
    reports a per-account outcome;
  * the self/superuser guard still fires per account under bulk (the acting
    admin selecting themselves must be reported failed, not silently skipped);
  * GET  /users/admin/users/{id}/sessions lists a target's live session;
  * DELETE .../sessions/{sid} revokes exactly that session and no other.

Run:  python .p1-tests/users_bulk_and_sessions_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.users.domain.models import User, UserProfile, UserSession

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    phone_a = "98" + uuid.uuid4().hex[:9]
    phone_b = "98" + uuid.uuid4().hex[:9]
    # A third account kept out of the bulk actions: blocking a user revokes
    # their sessions (correctly), so the session assertions need an account the
    # bulk steps never touch.
    phone_c = "98" + uuid.uuid4().hex[:9]
    # A fourth account, never touched by the bulk steps: they block user B
    # (which legitimately revokes B's sessions), so the "another account's
    # session survives" check needs an account the bulk steps never see.
    phone_d = "98" + uuid.uuid4().hex[:9]

    async with Session() as db:
        admin = (
            await db.execute(select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()
        if admin is None:
            print("  no superuser to act as — cannot run")
            await eng.dispose()
            return 1

        a = User(phone=phone_a, is_active=True, is_verified=True, author_slug=f"p1ba{marker}")
        b = User(phone=phone_b, is_active=True, is_verified=True, author_slug=f"p1bb{marker}")
        c = User(phone=phone_c, is_active=True, is_verified=True, author_slug=f"p1bc{marker}")
        d = User(phone=phone_d, is_active=True, is_verified=True, author_slug=f"p1bd{marker}")
        db.add_all([a, b, c, d])
        await db.flush()
        db.add_all([
            UserProfile(user_id=a.id, first_name=f"BULK{marker}A"),
            UserProfile(user_id=b.id, first_name=f"BULK{marker}B"),
            UserProfile(user_id=c.id, first_name=f"BULK{marker}C"),
            UserProfile(user_id=d.id, first_name=f"BULK{marker}D"),
        ])
        # Two live sessions on user C (the session subject), one on user D (a
        # second account the bulk steps never touch, to prove revocation is
        # scoped to its owner).
        sess_c1 = UserSession(
            user_id=c.id, refresh_token=f"rt-{marker}-c1",
            ip_address="10.0.0.1", user_agent="UA-C1",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        sess_c2 = UserSession(
            user_id=c.id, refresh_token=f"rt-{marker}-c2",
            ip_address="10.0.0.2", user_agent="UA-C2",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        sess_d1 = UserSession(
            user_id=d.id, refresh_token=f"rt-{marker}-d1",
            ip_address="10.0.0.3", user_agent="UA-D1",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add_all([sess_c1, sess_c2, sess_d1])
        await db.commit()
        a_id, b_id, c_id, d_id = a.id, b.id, c.id, d.id
        sess_c1_id, sess_c2_id, sess_d1_id = sess_c1.id, sess_c2.id, sess_d1.id
        admin_id = admin.id

    token = create_access_token(
        str(admin_id), {"roles": ["super_admin"], "permissions": ["*"]}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        try:
            # 1. Bulk block, including the acting admin themselves — the
            #    self-guard must fire for that one row and report it failed
            #    while the other two succeed. "3 done" would be a lie.
            r = await client.post(
                "/api/v1/users/admin/users/bulk",
                headers=headers,
                json={"action": "block", "ids": [str(a_id), str(b_id), str(admin_id)]},
            )
            check("1. bulk block answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:200]}")
            body = r.json()
            check("1b. two accounts were blocked, one refused",
                  body.get("ok") == 2 and body.get("failed") == 1,
                  f"ok={body.get('ok')} failed={body.get('failed')}")
            self_row = next(
                (x for x in body.get("results", []) if x["id"] == str(admin_id)), None
            )
            check("1c. the refusal is the acting admin's own row",
                  self_row is not None and self_row["ok"] is False,
                  f"self_row={self_row}")
            # And the refusal is real: the admin is still active.
            async with Session() as db:
                still = await db.get(User, admin_id)
                check("1d. the acting admin was not actually blocked",
                      bool(still and still.is_active), "the self-guard let it through")

            # 2. The block took effect and revoked the target's sessions.
            async with Session() as db:
                blocked = await db.get(User, a_id)
                check("2. the target account is blocked", bool(blocked and not blocked.is_active))
            r = await client.get(
                "/api/v1/users/admin/users", headers=headers,
                params={"search": phone_a},
            )
            row = next((i for i in r.json()["items"] if i["id"] == str(a_id)), {})
            check("2b. the list shows it as inactive", row.get("is_active") is False,
                  f"is_active={row.get('is_active')!r}")

            # 3. Bulk unblock restores both.
            r = await client.post(
                "/api/v1/users/admin/users/bulk",
                headers=headers,
                json={"action": "unblock", "ids": [str(a_id), str(b_id)]},
            )
            check("3. bulk unblock answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:200]}")
            check("3b. both accounts unblocked", r.json().get("ok") == 2,
                  f"ok={r.json().get('ok')}")

            # 4. Admin sees another user's live sessions.
            r = await client.get(
                f"/api/v1/users/admin/users/{c_id}/sessions", headers=headers
            )
            check("4. admin session list answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:200]}")
            listed = {s["id"] for s in r.json()}
            check("4b. both of C's live sessions are listed",
                  {str(sess_c1_id), str(sess_c2_id)} <= listed,
                  f"listed={listed}")

            # 5. Revoke exactly one; the other must survive, and B's untouched.
            r = await client.delete(
                f"/api/v1/users/admin/users/{c_id}/sessions/{sess_c1_id}",
                headers=headers,
            )
            check("5. revoke answers 204", r.status_code == 204,
                  f"status {r.status_code} {r.text[:200]}")
            async with Session() as db:
                s1 = await db.get(UserSession, sess_c1_id)
                s2 = await db.get(UserSession, sess_c2_id)
                sd = await db.get(UserSession, sess_d1_id)
                check("5b. the named session is revoked", bool(s1 and s1.is_revoked))
                check("5c. the sibling session is untouched",
                      bool(s2 and not s2.is_revoked), "revoking one killed another")
                check("5d. the other user's session is untouched",
                      bool(sd and not sd.is_revoked), "cross-account revocation")

            # 5e. A revoked session disappears from the admin list.
            r = await client.get(
                f"/api/v1/users/admin/users/{c_id}/sessions", headers=headers
            )
            listed = {s["id"] for s in r.json()}
            check("5e. the revoked session left the list",
                  str(sess_c1_id) not in listed, f"listed={listed}")

            # 6. Revoking a session that belongs to another account is refused,
            #    not silently applied — the owner predicate is the safety arg.
            r = await client.delete(
                f"/api/v1/users/admin/users/{c_id}/sessions/{sess_d1_id}",
                headers=headers,
            )
            check("6. cross-account revoke is refused (404)",
                  r.status_code == 404, f"status {r.status_code} {r.text[:160]}")
        finally:
            async with Session() as db:
                for uid in (a_id, b_id, c_id, d_id):
                    await db.execute(delete(UserSession).where(UserSession.user_id == uid))
                    await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                    await db.execute(delete(User).where(User.id == uid))
                await db.commit()
            async with Session() as db:
                left = (
                    await db.execute(
                        select(User.id).where(User.phone.in_([phone_a, phone_b, phone_c, phone_d]))
                    )
                ).scalars().all()
                check("7. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nBULK/SESSION GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: bulk user actions honour per-account guards and report the "
          "split; admins can see and revoke another account's sessions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))