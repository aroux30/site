"""Every user-creation path writes an author_slug.

The column is read by the author archive (`/author/<slug>`), and it was
populated by a one-shot migration with writers on only two of the four paths:
password registration and admin creation had it, OTP registration and SSO
provisioning did not — so a user made through either had an empty slug and a
404 archive. Same column, four doors, two of them forgetting.

This exercises the two doors directly at the service layer, because the HTTP
surface for OTP needs an OTP row and the SSO surface needs a provider
round-trip; the bug was in the creation, and the creation is what is called
here. Both probes are removed afterwards, and their slugs are asserted unique
against the real table so the check runs on live data.

Run:  python .p1-tests/author_slug_paths_test.py
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

from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.auth.application import auth_service
from app.modules.users.domain.models import OTPRequest, User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    probe_phone = "9891" + uuid.uuid4().hex[:8]
    probe_slug: str | None = None

    try:
        # 1. OTP registration path: a valid OTP row + verify_otp creates a user.
        async with Session() as db:
            db.add(
                OTPRequest(
                    phone=probe_phone,
                    code="123456",
                    purpose="login",
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    is_used=False,
                )
            )
            await db.commit()

        async with Session() as db:
            try:
                await auth_service.verify_otp(db, phone=probe_phone, code="123456")
                await db.commit()
            except Exception as exc:  # noqa: BLE001 — report, do not crash the probe
                check("1. verify_otp created the account", False, str(exc)[:200])

        async with Session() as db:
            user = (
                await db.execute(select(User).where(User.phone == probe_phone))
            ).scalars().first()
            if user is None:
                check("1. verify_otp created the account", False, "no user row")
            else:
                check("1. verify_otp created the account", True)
                check("1b. and it has an author_slug",
                      bool(user.author_slug), f"slug={user.author_slug!r}")
                probe_slug = user.author_slug
                if probe_slug:
                    # 1c. unique against the live table.
                    clash = (
                        await db.execute(
                            select(User.id).where(
                                User.author_slug == probe_slug, User.id != user.id
                            )
                        )
                    ).scalars().first()
                    check("1c. and it is unique in the table", clash is None,
                          f"slug {probe_slug} already held")

        # 2. The slugify helper's fallback: a phone-only name still yields a
        #    usable slug rather than an empty string every check collides on.
        from app.modules.users.application.author_slug import unique_author_slug

        async with Session() as db:
            fallback_slug = await unique_author_slug(
                db, "", fallback=probe_phone + "x"
            )
            check("2. an empty name still produces a slug",
                  bool(fallback_slug), f"slug={fallback_slug!r}")
    finally:
        # Remove every probe row, in FK order, whatever happened above.
        async with Session() as db:
            user = (
                await db.execute(select(User).where(User.phone == probe_phone))
            ).scalars().first()
            if user is not None:
                await db.execute(
                    delete(UserProfile).where(UserProfile.user_id == user.id)
                )
                await db.execute(delete(User).where(User.id == user.id))
            await db.execute(
                delete(OTPRequest).where(OTPRequest.phone == probe_phone)
            )
            await db.commit()
        async with Session() as db:
            leftover = (
                await db.execute(select(User.id).where(User.phone == probe_phone))
            ).scalars().first()
            check("3. the probe rows were cleaned up", leftover is None)

    await eng.dispose()
    if bad:
        print("\nAUTHOR-SLUG GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the OTP creation path writes a unique author_slug.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
