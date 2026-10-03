"""Display name and the admin-email change/review flow behave.

  * P1 "کاربران: نام نمایشی/نام مستعار": `display_name` is stored, returned,
    and an empty value means "fall back to first+last" (stored as NULL, not "");
  * P1 "کاربران: تغییر ایمیل مدیریتی با تأییدیه و بازبینی دوره‌ای": the admin
    address moves only after the token mailed to the *new* address is redeemed,
    and the periodic review records a fresh confirmation without changing it.

Server-side facts over the real routes:

  * PATCH /auth/me with display_name stores and returns it;
  * PATCH with display_name="" clears it to NULL (fallback state);
  * POST /settings/admin/admin-email/change does NOT move admin_email;
  * confirming with the wrong token is refused; the right one moves it;
  * a second confirm of the same token reports no pending request;
  * confirm-current refreshes confirmed_at and clears needs_review.

Run:  python .p1-tests/display_name_and_admin_email_test.py
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
from app.modules.settings.application.admin_email_service import (
    ADMIN_EMAIL_CONFIRMED_AT_OPTION,
    PENDING_TOKEN_HASH_OPTION,
    _hash_token,
)
from app.modules.settings.application.site_options_service import SiteOptionsService
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
    phone = "09" + "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])
    email = f"dispname{marker}@example.com"

    created_user_ids: list[uuid.UUID] = []
    # Snapshot the admin-email options so the whole test can restore them,
    # whichever branch it exits through. These are REAL site options — the
    # test must put them back exactly as it found them.
    original: dict[str, str | None] = {}

    try:
        async with Session() as db:
            for key in (
                "admin_email",
                "new_admin_email",
                PENDING_TOKEN_HASH_OPTION,
                "new_admin_email_requested_at",
                ADMIN_EMAIL_CONFIRMED_AT_OPTION,
            ):
                original[key] = await SiteOptionsService.get(db, key)

            u = User(phone=phone, is_active=True, is_verified=True, author_slug=f"p1dn{marker}")
            db.add(u)
            await db.flush()
            db.add(UserProfile(user_id=u.id, first_name="First", last_name="Last"))
            await db.commit()
            user_id = u.id
            created_user_ids.append(u.id)

        token = create_access_token(str(user_id), {"roles": ["customer"]})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 1. Set a display name.
            r = await client.patch(
                "/api/v1/auth/me",
                headers=headers,
                json={"display_name": "آرش"},
            )
            check("1. setting a display name answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            check("1b. and it comes back in the response",
                  r.json().get("display_name") == "آرش",
                  f"display_name={r.json().get('display_name')!r}")

            async with Session() as db:
                prof = (
                    await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
                ).scalar_one()
                check("1c. and it is stored on the profile",
                      prof.display_name == "آرش", f"stored={prof.display_name!r}")

            # 2. GET /auth/me also returns it.
            r = await client.get("/api/v1/auth/me", headers=headers)
            check("2. /auth/me returns the display name",
                  r.json().get("display_name") == "آرش",
                  f"display_name={r.json().get('display_name')!r}")

            # 3. Clearing it stores NULL (the fallback state), not "".
            r = await client.patch(
                "/api/v1/auth/me", headers=headers, json={"display_name": ""}
            )
            check("3. clearing answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:160]}")
            async with Session() as db:
                prof = (
                    await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
                ).scalar_one()
                check("3b. an empty display name is stored as NULL",
                      prof.display_name is None, f"stored={prof.display_name!r}")

            # ── Admin email flow (needs settings:write, so mint an admin) ────
            async with Session() as db:
                admin = (
                    await db.execute(select(User).where(User.is_superuser == True).limit(1))
                ).scalars().first()
            admin_token = create_access_token(
                str(admin.id), {"roles": ["super_admin"], "permissions": ["*"]}
            )
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Read the current admin_email cleanly, through a fresh session.
        async with Session() as db:
            current = await SiteOptionsService.get(db, "admin_email")

        target = f"newadmin{marker}@example.com"

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 4. Status endpoint answers.
            r = await client.get("/api/v1/settings/admin/admin-email", headers=admin_headers)
            check("4. admin-email status answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")
            body = r.json()
            check("4b. it reports the current address",
                  body.get("admin_email") == current,
                  f"admin_email={body.get('admin_email')!r} vs {current!r}")

            # 5. Propose a change — admin_email must NOT move yet.
            r = await client.post(
                "/api/v1/settings/admin/admin-email/change",
                headers=admin_headers,
                json={"new_email": target},
            )
            check("5. proposing answers 200", r.status_code == 200,
                  f"status {r.status_code} {r.text[:200]}")
            check("5b. the proposal is recorded as pending",
                  r.json().get("status") == "pending", f"body={r.json()}")
            async with Session() as db:
                still = await SiteOptionsService.get(db, "admin_email")
                pending = await SiteOptionsService.get(db, "new_admin_email")
                check("5c. admin_email did NOT move",
                      still == current, f"admin_email={still!r}")
                check("5d. the pending option holds the new address",
                      pending == target, f"pending={pending!r}")

            # 6. A wrong token is refused.
            r = await client.post(
                "/api/v1/settings/admin/admin-email/confirm",
                headers=admin_headers,
                json={"token": "definitely-not-the-token"},
            )
            check("6. a wrong token answers 200 with a refusal status",
                  r.status_code == 200 and r.json().get("status") == "invalid_token",
                  f"status {r.status_code} body={r.text[:160]}")

            # 7. The right token moves the address. The raw token only exists in
            #    the email, so the test writes the hash the service expects.
            raw = "probe-admin-" + uuid.uuid4().hex
            async with Session() as db:
                await SiteOptionsService.set(db, PENDING_TOKEN_HASH_OPTION, _hash_token(raw))

            r = await client.post(
                "/api/v1/settings/admin/admin-email/confirm",
                headers=admin_headers,
                json={"token": raw},
            )
            check("7. the right token confirms",
                  r.status_code == 200 and r.json().get("status") == "confirmed",
                  f"status {r.status_code} body={r.text[:200]}")
            async with Session() as db:
                moved = await SiteOptionsService.get(db, "admin_email")
                confirmed_at = await SiteOptionsService.get(db, ADMIN_EMAIL_CONFIRMED_AT_OPTION)
                check("7b. admin_email moved to the new address",
                      moved == target, f"admin_email={moved!r}")
                check("7c. a confirmation timestamp was recorded",
                      bool(confirmed_at), f"confirmed_at={confirmed_at!r}")

            # 8. A second redemption reports "no pending", not a second apply.
            r = await client.post(
                "/api/v1/settings/admin/admin-email/confirm",
                headers=admin_headers,
                json={"token": raw},
            )
            check("8. re-using the token reports no pending request",
                  r.status_code == 200 and r.json().get("status") == "no_pending",
                  f"status {r.status_code} body={r.text[:160]}")

            # 9. The periodic review: clear confirmed_at → needs_review true →
            #    confirm-current → needs_review false, address unchanged.
            async with Session() as db:
                await SiteOptionsService.set(db, ADMIN_EMAIL_CONFIRMED_AT_OPTION, None)
            r = await client.get("/api/v1/settings/admin/admin-email", headers=admin_headers)
            check("9. an unconfirmed address needs review",
                  r.json().get("needs_review") is True, f"body={r.text[:200]}")
            r = await client.post(
                "/api/v1/settings/admin/admin-email/confirm-current",
                headers=admin_headers,
            )
            check("9b. confirm-current answers 200",
                  r.status_code == 200, f"status {r.status_code}")
            async with Session() as db:
                after_review = await SiteOptionsService.get(db, "admin_email")
                check("9c. the review did not change the address",
                      after_review == target, f"admin_email={after_review!r}")
            r = await client.get("/api/v1/settings/admin/admin-email", headers=admin_headers)
            check("9d. needs_review is cleared after the review",
                  r.json().get("needs_review") is False, f"body={r.text[:200]}")
    finally:
        # Restore the real site options first — they are live data.
        async with Session() as db:
            for key, value in original.items():
                await SiteOptionsService.set(db, key, value)
        async with Session() as db:
            for uid in created_user_ids:
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            restored = await SiteOptionsService.get(db, "admin_email")
            check("10. the real admin_email option was restored",
                  restored == original.get("admin_email"),
                  f"restored={restored!r} expected={original.get('admin_email')!r}")
            left = (
                await db.execute(select(User.id).where(User.phone == phone))
            ).scalars().all()
            check("10b. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nDISPLAY-NAME/ADMIN-EMAIL GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: display_name stores and clears correctly; the admin email moves "
          "only on token redemption and the review is non-mutating.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))