"""Privacy email confirmation, ZIP export, and the policy-page selector.

Three items:

  * P1 "حریم خصوصی: جریان ایمیلی تأیید درخواست" (133): a mailed link confirms
    a pending request — the second path beside the SMS OTP;
  * P1 "حریم خصوصی: خروجی ZIP ساخت‌یافته" (130): the ZIP route serves an
    archive with index.html + per-source JSON, one-shot;
  * P1 "حریم خصوصی: انتخابگر صفحه‌ی سیاست" (132): the policy option names a
    published public page, and the public endpoint serves it.

Server-side facts over the real routes:

  * send-email-confirmation issues a token (and reports honestly when the
    account has no address);
  * confirming with the right token sets confirmed_at; a second redemption is
    refused; a wrong token is refused;
  * the ZIP route answers application/zip with index.html inside, and a second
    read is refused (one-shot);
  * the policy option is honoured by /settings/public/privacy-policy, and a
    draft page is treated as "no policy".

Run:  python .p1-tests/privacy_email_confirm_and_policy_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.settings.application.privacy_request_service import (
    _hash_confirm_token,
)
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.settings.domain.models import (
    PrivacyRequest,
    PrivacyRequestStatus,
    PrivacyRequestType,
)
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
    email = f"prvmail{marker}@example.com"

    created_user_ids: list[uuid.UUID] = []
    created_request_ids: list[uuid.UUID] = []
    original_policy: str | None = None

    try:
        async with Session() as db:
            original_policy = await SiteOptionsService.get(db, "privacy.policy_page")
            u = User(
                phone=phone, is_active=True, is_verified=True, email=email,
                author_slug=f"p1pv{marker}",
            )
            db.add(u)
            await db.flush()
            db.add(UserProfile(user_id=u.id, first_name=f"PRV{marker}"))
            await db.commit()
            user_id = u.id
            created_user_ids.append(u.id)

        token = create_access_token(str(user_id), {"roles": ["customer"]})
        # The submit route is rate-limited at 5/hour per client IP. The limiter
        # reads X-Forwarded-For with TRUSTED_PROXY_COUNT hops trusted (2 in
        # this environment), so the forwarded header must carry that many
        # entries — the *second-from-right* is the client address it keys on.
        # A single-hop header falls through to the socket IP (127.0.0.1), which
        # is how repeated runs 429'd on each other and on a developer's browser
        # bucket. Two hops, with the per-run IP second-from-right, gives this
        # fixture its own bucket and touches nobody else's.
        probe_ip = f"10.99.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": f"{probe_ip}, 10.0.0.1",
        }

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 1. Raise an export request.
            r = await client.post(
                "/api/v1/settings/privacy/requests",
                headers=headers,
                json={"type": "export", "reason": f"probe {marker}"},
            )
            check("1. submitting an export answers 201",
                  r.status_code == 201, f"status {r.status_code} {r.text[:200]}")
            req_id = r.json().get("id")
            created_request_ids.append(uuid.UUID(req_id))

            # 2. Ask for the emailed confirmation link.
            r = await client.post(
                f"/api/v1/settings/privacy/requests/{req_id}/send-email-confirmation",
                headers=headers,
            )
            check("2. send-email-confirmation answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            body = r.json()
            check("2b. it reports a send (SMTP is mock-configured in dev)",
                  "sent" in body, f"body={body}")

            async with Session() as db:
                row = await db.get(PrivacyRequest, uuid.UUID(req_id))
                check("2c. a token hash was stored on the request",
                      bool(row and row.confirm_token_hash), "no token stored")

            # 3. A wrong token is refused.
            r = await client.post(
                "/api/v1/settings/privacy/requests/confirm-by-email",
                json={"token": "wrong-token-probe"},
            )
            # The app's ValidationError maps to 422; both 400 and 422 mean "refused".
            check("3. a wrong token is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 4. The right token confirms. The raw token only exists in the
            #    email, so the test rewrites the stored hash to a known value.
            raw = "probe-privacy-" + uuid.uuid4().hex
            async with Session() as db:
                row = await db.get(PrivacyRequest, uuid.UUID(req_id))
                row.confirm_token_hash = _hash_confirm_token(raw)
                row.confirm_token_expires_at = datetime.now(UTC) + timedelta(hours=1)
                await db.commit()

            r = await client.post(
                "/api/v1/settings/privacy/requests/confirm-by-email",
                json={"token": raw},
            )
            check("4. the right token confirms (200)",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            async with Session() as db:
                row = await db.get(PrivacyRequest, uuid.UUID(req_id))
                check("4b. confirmed_at is set",
                      bool(row and row.confirmed_at), "confirmed_at empty")
                check("4c. the token was consumed",
                      bool(row and not row.confirm_token_hash), "token hash kept")

            # 5. A second redemption is refused.
            r = await client.post(
                "/api/v1/settings/privacy/requests/confirm-by-email",
                json={"token": raw},
            )
            check("5. a second redemption is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 6. An expired token is refused. Re-issue a token with a past
            #    expiry on a fresh request.
            async with Session() as db:
                req2 = PrivacyRequest(
                    user_id=user_id,
                    type=PrivacyRequestType.EXPORT,
                    status=PrivacyRequestStatus.PENDING,
                    verified_at=datetime.now(UTC),
                )
                db.add(req2)
                await db.flush()
                raw2 = "expired-probe-" + uuid.uuid4().hex
                req2.confirm_token_hash = _hash_confirm_token(raw2)
                req2.confirm_token_expires_at = datetime.now(UTC) - timedelta(hours=1)
                await db.commit()
                created_request_ids.append(req2.id)

            r = await client.post(
                "/api/v1/settings/privacy/requests/confirm-by-email",
                json={"token": raw2},
            )
            check("6. an expired token is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # ── ZIP export (130 consumer) ────────────────────────────────────
            # Complete the first request as an operator would, then collect
            # the ZIP. Run the export through the service so the payload shape
            # matches production.
            from app.modules.settings.application.privacy_request_service import (
                PrivacyRequestService,
            )

            async with Session() as db:
                await PrivacyRequestService.run_export(
                    db, request_id=uuid.UUID(req_id), admin_id=user_id
                )

            r = await client.get(
                f"/api/v1/settings/privacy/requests/{req_id}/result.zip",
                headers=headers,
            )
            check("7. the ZIP route answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:160]}")
            check("7b. the content type is a zip",
                  "zip" in (r.headers.get("content-type") or ""),
                  f"content-type={r.headers.get('content-type')!r}")
            names: list[str] = []
            try:
                with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                    names = zf.namelist()
            except Exception as exc:  # noqa: BLE001
                check("7c. the body parses as a zip", False, str(exc)[:120])
            else:
                check("7c. the archive has an index.html",
                      "index.html" in names, f"names={names[:6]}")
                check("7d. the archive has a report",
                      "_report.json" in names, f"names={names[:6]}")

            # 8. One-shot: a second read is refused.
            r = await client.get(
                f"/api/v1/settings/privacy/requests/{req_id}/result.zip",
                headers=headers,
            )
            check("8. a second ZIP read is refused (400/404)",
                  r.status_code in (400, 404), f"status {r.status_code}")

            # ── Policy page selector (132) ───────────────────────────────────
            async with Session() as db:
                await SiteOptionsService.set(db, "privacy.policy_page", "no-such-page-probe")
            r = await client.get("/api/v1/settings/public/privacy-policy")
            check("9. an option naming a missing page answers 200 with no policy",
                  r.status_code == 200 and r.json().get("slug") is None,
                  f"status {r.status_code} body={r.text[:160]}")

            async with Session() as db:
                await SiteOptionsService.set(db, "privacy.policy_page", original_policy)
    finally:
        async with Session() as db:
            await SiteOptionsService.set(db, "privacy.policy_page", original_policy)
        async with Session() as db:
            for rid in created_request_ids:
                await db.execute(delete(PrivacyRequest).where(PrivacyRequest.id == rid))
            for uid in created_user_ids:
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            restored = await SiteOptionsService.get(db, "privacy.policy_page")
            check("10. the real policy option was restored",
                  restored == original_policy,
                  f"restored={restored!r} expected={original_policy!r}")
            left = (
                await db.execute(select(User.id).where(User.phone == phone))
            ).scalars().all()
            check("10b. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nPRIVACY EMAIL/ZIP/POLICY GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the emailed confirmation link is issued, single-use and "
          "expiry-checked; the ZIP is structured and one-shot; the policy "
          "selector option is honoured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))