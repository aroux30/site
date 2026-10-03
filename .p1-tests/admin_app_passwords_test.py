"""An admin can see and revoke another account's application passwords.

P2 "REST: مدیریت Application Password کاربر دیگر". The self-service list and
revoke existed; a support case about a leaked API token used to end with "ask
the user to revoke it themselves" — the thing the customer is reporting they
cannot do.

Server-side facts over the real routes:

  * GET  /users/admin/users/{id}/application-passwords lists the target's
    credentials, metadata only — no hash, no plaintext anywhere in the body;
  * DELETE .../{app_password_id} revokes exactly that credential;
  * the revoked credential stops authenticating immediately;
  * cross-account revocation (admin of user A naming user B's credential) is
    refused — the owner predicate is the safety argument;
  * a customer without users:read gets 403 on the admin list.

Run:  python .p1-tests/admin_app_passwords_test.py
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
from app.modules.users.domain.models import ApplicationPassword, User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    phone_a = "09" + "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])
    phone_b = "09" + "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])

    created_user_ids: list[uuid.UUID] = []

    try:
        from app.modules.auth.application.application_password_service import (
            create_application_password,
        )

        async with Session() as db:
            a = User(phone=phone_a, is_active=True, is_verified=True, author_slug=f"p1ap{marker}a")
            b = User(phone=phone_b, is_active=True, is_verified=True, author_slug=f"p1ap{marker}b")
            db.add_all([a, b])
            await db.flush()
            db.add_all([
                UserProfile(user_id=a.id, first_name=f"AP{marker}A"),
                UserProfile(user_id=b.id, first_name=f"AP{marker}B"),
            ])
            await db.commit()
            a_id, b_id = a.id, b.id
            created_user_ids.extend([a.id, b.id])

            # A credential on A (the target of the support case) and one on B
            # (the cross-account probe).
            row_a, secret_a = await create_application_password(
                db, user_id=a_id, name=f"probe-a-{marker}"
            )
            row_b, secret_b = await create_application_password(
                db, user_id=b_id, name=f"probe-b-{marker}"
            )
            await db.commit()
            ap_a_id, ap_b_id = row_a.id, row_b.id

            admin = (
                await db.execute(select(User).where(User.is_superuser == True).limit(1))
            ).scalars().first()

        admin_token = create_access_token(
            str(admin.id), {"roles": ["super_admin"], "permissions": ["*"]}
        )
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        # A plain customer token, to prove the admin list is not open to them.
        customer_token = create_access_token(str(a_id), {"roles": ["customer"]})
        customer_headers = {"Authorization": f"Bearer {customer_token}"}

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 0. A customer cannot reach the admin list.
            r = await client.get(
                f"/api/v1/users/admin/users/{a_id}/application-passwords",
                headers=customer_headers,
            )
            check("0. a customer is refused the admin list (403)",
                  r.status_code == 403, f"status {r.status_code} {r.text[:160]}")

            # 1. The admin sees A's credential.
            r = await client.get(
                f"/api/v1/users/admin/users/{a_id}/application-passwords",
                headers=admin_headers,
            )
            check("1. the admin list answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            items = r.json()
            names = [i.get("name") for i in items]
            check("1b. the target's credential is listed",
                  f"probe-a-{marker}" in names, f"names={names}")
            check("1c. the other account's credential is NOT listed",
                  f"probe-b-{marker}" not in names, f"names={names}")

            # 2. THE SECURITY BOUNDARY: no secret material in the body.
            body_text = r.text
            check("2. the response carries no token hash",
                  "token_hash" not in body_text, "a hash field reached the admin API")
            check("2b. the response carries no plaintext secret",
                  secret_a not in body_text, "the plaintext token leaked to the admin API")
            # And the fields it may carry: prefix is fine (identification, not use).
            listed_a = next((i for i in items if i.get("name") == f"probe-a-{marker}"), {})
            check("2c. the prefix is present for identification",
                  bool(listed_a.get("token_prefix")), f"row={listed_a}")

            # 3. The credential still authenticates before revocation.
            r = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {secret_a}"},
            )
            check("3. the credential authenticates before revocation",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")

            # 4. Cross-account revocation is refused: admin names A in the path
            #    but B's credential id.
            r = await client.delete(
                f"/api/v1/users/admin/users/{a_id}/application-passwords/{ap_b_id}",
                headers=admin_headers,
            )
            check("4. cross-account revocation is refused (404)",
                  r.status_code == 404, f"status {r.status_code} {r.text[:160]}")
            async with Session() as db:
                b_row = await db.get(ApplicationPassword, ap_b_id)
                check("4b. and B's credential is still active",
                      bool(b_row and b_row.is_active), "cross-account revoke landed")

            # 5. The admin revokes A's credential.
            r = await client.delete(
                f"/api/v1/users/admin/users/{a_id}/application-passwords/{ap_a_id}",
                headers=admin_headers,
            )
            check("5. the admin revoke answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            check("5b. the response shows it revoked",
                  r.json().get("revoked_at") is not None
                  and r.json().get("is_active") is False,
                  f"body={r.text[:200]}")

            # 6. It stops authenticating immediately.
            r = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {secret_a}"},
            )
            check("6. the revoked credential no longer authenticates",
                  r.status_code == 401, f"status {r.status_code} {r.text[:160]}")

            # 7. The list still shows it, greyed — the panel tells the story.
            r = await client.get(
                f"/api/v1/users/admin/users/{a_id}/application-passwords",
                headers=admin_headers,
            )
            revoked = next(
                (i for i in r.json() if i.get("name") == f"probe-a-{marker}"), None
            )
            check("7. the revoked row stays listed",
                  revoked is not None and revoked.get("revoked_at") is not None,
                  f"row={revoked}")
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
                await db.execute(
                    select(User.id).where(User.phone.in_([phone_a, phone_b]))
                )
            ).scalars().all()
            check("8. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nADMIN APP-PASSWORD GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: an admin can list and revoke a target's application passwords, "
          "with no secret material exposed and cross-account revocation refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))