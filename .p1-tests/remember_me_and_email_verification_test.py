"""Remember-me sessions and registration email verification behave.

Two features:

  * P1 "کاربران: مرا به خاطر بسپار": login opts a session into a longer
    refresh lifetime, per session;
  * P1 "کاربران: تأیید ایمیل هنگام ثبت‌نام": a signup with an email gets a
    verification link, and `is_verified` flips only when it is redeemed.

Server-side facts over the real routes:

  * login with remember_me=true writes a session whose expires_at is the long
    window; without it, the default window;
  * register with an email leaves is_verified false and creates a token row;
  * POST /auth/me/email/verify with the token sets is_verified true;
  * a second redemption of the same token is refused;
  * a token issued for one address does not verify a different address.

Run:  python .p1-tests/remember_me_and_email_verification_test.py

SABOTAGE SAFETY (learned the hard way today): a deliberate breakage of a
WRITE path must never touch real rows. Breaking the code and re-running this
file is safe — every account it touches is created here with a random probe
phone and deleted in the `finally`. Do NOT validate a write-path sabotage by
letting it hit an existing account; that is how an earlier probe blocked a
real superuser. Confirm with a SELECT after any write-path experiment.
"""

from __future__ import annotations

import asyncio
import io
import re
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.config.settings import get_settings
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.rbac.domain.models import UserRole
from app.modules.users.domain.models import (
    EmailVerificationToken,
    User,
    UserProfile,
    UserSession,
)

settings = get_settings()
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]

    def iran_phone() -> str:
        """A valid `09xxxxxxxxx` probe number (the register validator requires
        the 09 prefix, unlike the older DB-only fixtures)."""
        digits = "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])
        return "09" + digits

    phone_remember = iran_phone()
    phone_plain = iran_phone()
    phone_email = iran_phone()
    email_ok = f"p1verify{marker}@example.com"
    email_taken_probe = f"p1taken{marker}@example.com"
    probe_password = "Passw0rd!234"

    created_user_ids: list[uuid.UUID] = []

    try:
        # ── Remember-me ──────────────────────────────────────────────────────
        from app.core.security.password import hash_password

        async with Session() as db:
            for phone in (phone_remember, phone_plain):
                u = User(
                    phone=phone, is_active=True, is_verified=True,
                    password_hash=hash_password(probe_password),
                    author_slug=f"p1rm{marker}{phone[-2:]}",
                )
                db.add(u)
                await db.flush()
                db.add(UserProfile(user_id=u.id, first_name=f"RM{marker}"))
                created_user_ids.append(u.id)
            await db.commit()

        # Login and register are rate-limited per client IP (5/minute), and the
        # limiter reads X-Forwarded-For with TRUSTED_PROXY_COUNT hops trusted
        # (2 here). A per-run forwarded IP with that many entries gives this
        # fixture its own bucket, so running it back-to-back with the other
        # gates cannot 429 on their traffic or its own previous run.
        probe_ip = f"10.97.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
        rl_headers = {"X-Forwarded-For": f"{probe_ip}, 10.0.0.1"}

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 1. Login through the real route, once per lifetime.
            r_plain = await client.post(
                "/api/v1/auth/login",
                headers=rl_headers,
                json={"phone": phone_plain, "password": probe_password},
            )
            check("1. plain login answers 200",
                  r_plain.status_code == 200, f"status {r_plain.status_code} {r_plain.text[:160]}")
            r_remember = await client.post(
                "/api/v1/auth/login",
                headers=rl_headers,
                json={
                    "phone": phone_remember,
                    "password": probe_password,
                    "remember_me": True,
                },
            )
            check("1b. remember-me login answers 200",
                  r_remember.status_code == 200, f"status {r_remember.status_code} {r_remember.text[:160]}")

            # The cookie must carry the long lifetime too. A long session behind
            # a short cookie forgets itself in the browser — the server still
            # holds the session, but no client can present it.
            def refresh_cookie_max_age(resp) -> int | None:
                for header in resp.headers.get_list("set-cookie"):
                    if header.startswith("refresh_token="):
                        m = re.search(r"[Mm]ax-[Aa]ge=(\d+)", header)
                        if m:
                            return int(m.group(1))
                return None

            plain_cookie = refresh_cookie_max_age(r_plain)
            remember_cookie = refresh_cookie_max_age(r_remember)
            check("1c. the plain login sets a refresh cookie in the default window",
                  plain_cookie is not None
                  and abs(plain_cookie - settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400) < 120,
                  f"max_age={plain_cookie}")
            check("1d. the remember-me cookie carries the long window",
                  remember_cookie is not None
                  and abs(remember_cookie - settings.REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS * 86400) < 120,
                  f"max_age={remember_cookie}")

        async with Session() as db:
            plain_user = (
                await db.execute(select(User).where(User.phone == phone_plain))
            ).scalar_one()
            remember_user = (
                await db.execute(select(User).where(User.phone == phone_remember))
            ).scalar_one()
            plain_sess = (
                await db.execute(
                    select(UserSession).where(UserSession.user_id == plain_user.id)
                )
            ).scalars().first()
            remember_sess = (
                await db.execute(
                    select(UserSession).where(UserSession.user_id == remember_user.id)
                )
            ).scalars().first()

            now = datetime.now(UTC)
            plain_days = (plain_sess.expires_at - now).total_seconds() / 86400
            remember_days = (remember_sess.expires_at - now).total_seconds() / 86400
            check("2. the default session uses the default window",
                  abs(plain_days - settings.REFRESH_TOKEN_EXPIRE_DAYS) < 0.1,
                  f"plain_days={plain_days:.2f}")
            check("3. the remember-me session uses the long window",
                  abs(remember_days - settings.REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS) < 0.1,
                  f"remember_days={remember_days:.2f}")
            check("3b. and it is strictly longer",
                  remember_days > plain_days + 1,
                  f"remember={remember_days:.1f} plain={plain_days:.1f}")

        # ── Email verification ───────────────────────────────────────────────
        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/v1/auth/register",
                headers=rl_headers,
                json={
                    "phone": phone_email,
                    "password": "Passw0rd123",
                    "first_name": "Verify",
                    "last_name": "Probe",
                    "email": email_ok,
                },
            )
            check("4. registration with an email answers 201",
                  r.status_code == 201, f"status {r.status_code} {r.text[:200]}")

        async with Session() as db:
            reg_user = (
                await db.execute(select(User).where(User.phone == phone_email))
            ).scalar_one_or_none()
            check("4b. the account exists", reg_user is not None)
            if reg_user is None:
                raise SystemExit(1)
            created_user_ids.append(reg_user.id)
            check("4c. the address was stored",
                  (reg_user.email or "") == email_ok, f"email={reg_user.email!r}")
            check("4d. is_verified is false until the link is clicked",
                  reg_user.is_verified is False, "flag was pre-set")
            token_row = (
                await db.execute(
                    select(EmailVerificationToken).where(
                        EmailVerificationToken.user_id == reg_user.id
                    )
                )
            ).scalars().first()
            check("4e. a verification token row was created",
                  token_row is not None, "no token row")

            # Mint a known token by rewriting the stored hash: the raw token is
            # only ever in the email, so the test drives the redeem path with
            # the same hash function the service uses.
            from app.modules.users.application.email_verification_service import (
                hash_verification_token,
            )

            raw = "probe-" + uuid.uuid4().hex
            token_row.token_hash = hash_verification_token(raw)
            token_row.expires_at = datetime.now(UTC) + timedelta(hours=1)
            await db.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/v1/auth/me/email/verify", json={"token": raw}
            )
            check("5. redeeming the link answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")

            async with Session() as db:
                refreshed = await db.get(User, reg_user.id)
                check("5b. is_verified is now true",
                      bool(refreshed and refreshed.is_verified),
                      f"is_verified={refreshed.is_verified if refreshed else None}")

            # 6. The same token again is refused (single-use).
            r = await client.post(
                "/api/v1/auth/me/email/verify", json={"token": raw}
            )
            check("6. a second redemption is refused (400)",
                  r.status_code == 400, f"status {r.status_code}")

            # 7. A stale token — issued for an address the account no longer
            #    holds — must not verify the current one.
            async with Session() as db:
                stale_user = await db.get(User, reg_user.id)
                assert stale_user is not None
                stale_user.email = email_taken_probe
                stale_raw = "stale-" + uuid.uuid4().hex
                db.add(
                    EmailVerificationToken(
                        user_id=stale_user.id,
                        email=email_ok,  # the OLD address
                        token_hash=hash_verification_token(stale_raw),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                    )
                )
                stale_user.is_verified = False
                await db.commit()

            r = await client.post(
                "/api/v1/auth/me/email/verify", json={"token": stale_raw}
            )
            check("7. a token for a superseded address is refused (400)",
                  r.status_code == 400, f"status {r.status_code} {r.text[:160]}")
            async with Session() as db:
                still = await db.get(User, reg_user.id)
                check("7b. and the flag stayed false",
                      bool(still and not still.is_verified),
                      "stale link verified the wrong address")
    finally:
        async with Session() as db:
            for uid in created_user_ids:
                await db.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == uid))
                await db.execute(delete(UserSession).where(UserSession.user_id == uid))
                await db.execute(delete(UserRole).where(UserRole.user_id == uid))
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            left = (
                await db.execute(
                    select(User.id).where(
                        User.phone.in_([phone_remember, phone_plain, phone_email])
                    )
                )
            ).scalars().all()
            check("8. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nREMEMBER-ME/VERIFICATION GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: remember-me lengthens only its own session, and registration "
          "email verification is issued, single-use, and address-bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))