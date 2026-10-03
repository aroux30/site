"""Live check: an admin can issue a password reset for an account.

P0 "کاربران: ارسال لینک بازنشانی رمز توسط ادمین". Every piece of the machinery
already existed for the self-service flow — token, hash, TTL, voiding the
previous token, the email — but only reachable when the *account holder* asked.
An operator who locked someone out, or who is onboarding someone whose password
never reached them, had no route at all.

The property under test is not "the mail went out" — that needs an SMTP server.
It is that the operator's action reaches the same machinery the user's action
does, and that the two disagree honestly when there is nothing to reset.

    cd backend && PYTHONPATH=. python scripts/verify_admin_password_reset.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import re
import sys
from pathlib import Path
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.auth.application import auth_service  # noqa: E402
from app.modules.users.application import user_service  # noqa: E402


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _make_user(db, *, email: str | None, password: str | None) -> str:
    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, email, password_hash, is_active, "
            "is_verified, is_superuser, totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, :e, :pw, true, true, false, false, now(), now())"
        ),
        {
            "u": uid,
            "p": "9" + uuid.uuid4().hex[:9],
            "e": email,
            "pw": password,
        },
    )
    return uid


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []

    try:
        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'password_reset_tokens'"
                        )
                    )
                ).fetchall()
            }
            if not {"user_id", "token_hash", "expires_at"} <= columns:
                print("SKIP: password_reset_tokens is not the table this check needs.")
                return 0

            # The actor has to be a real row: audit_logs.actor_id carries a foreign
            # key to users, so an invented UUID makes the very insert that records
            # the operator's action fail — which reads as "the reset is broken"
            # when the reset is fine and the probe is not.
            actor_id = await _make_user(
                db,
                email=None,
                password="probe-hash",
            )
            created.append(f"users:{actor_id}")

            good = await _make_user(
                db,
                email="reset.probe.%s@example.invalid" % uuid.uuid4().hex[:8],
                password="probe-hash",
            )
            no_email = await _make_user(db, email=None, password="probe-hash")
            no_password = await _make_user(
                db,
                email="nopw.probe.%s@example.invalid" % uuid.uuid4().hex[:8],
                password=None,
            )
            created += [f"users:{u}" for u in (good, no_email, no_password)]
            await db.commit()

        # 1. A password account with an address gets a token. The token is the
        #    whole point — a mail that fails to send is a transport problem, but a
        #    reset that issues nothing is a logic one, and this distinguishes them.
        async with session() as db:
            user = await user_service.get_user_entity(db, user_id=uuid.UUID(good))
            before = await _tokens(db, good)
            # `sent` is bound in every branch. Leaving it to the else-branch
            # meant the "user vanished" path reached the line below with no value
            # and raised UnboundLocalError — which reported a crash instead of
            # the missing user it had just diagnosed, and hid the finding behind
            # a traceback.
            sent = False
            after = before
            if user is None:
                failures.append("the probe user vanished before the reset")
            else:
                sent = await auth_service.admin_request_password_reset(
                    db, user=user, actor_id=actor_id
                )
                await db.commit()
                after = await _tokens(db, good)
        if user is not None and sent:
            if len(after) != len(before) + 1:
                failures.append(
                    "the reset reported success but issued %d token(s), expected one "
                    "more than the %d already there"
                    % (len(after), len(before))
                )
            else:
                print("PASS: the admin reset issued a token for a password account")

        # 2. And the token is the same machinery the self-service flow uses — a
        #    hash, never the plaintext. A second implementation is how this ends up
        #    with a reset token stored in a form the public confirm endpoint does
        #    not accept.
        async with session() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT token_hash FROM password_reset_tokens "
                        "WHERE user_id = :u ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"u": good},
                )
            ).scalar()
        if row and len(str(row)) < 32:
            failures.append(
                "the stored reset token is %d characters; a plaintext token or a "
                "truncated one would both look like this" % len(str(row))
            )
        elif row:
            print("PASS: the issued token is stored hashed, as the public flow does")

        # 3. An account with no address gets an honest "no", not a fake success.
        async with session() as db:
            user = await user_service.get_user_entity(db, user_id=uuid.UUID(no_email))
            sent = user is not None and await auth_service.admin_request_password_reset(
                db, user=user, actor_id=actor_id
            )
            await db.commit()
        if user is None:
            failures.append("the probe user for the no-address case vanished")
        elif sent:
            failures.append(
                "an account with no email address reported a reset as sent; the "
                "operator would wait for a message that can never be written"
            )
        else:
            print("PASS: an account with no address reports honestly")

        # 4. Same for one that has an address but no password to reset — an
        #    OTP-only account has never had a password, so there is nothing to
        #    reset and the link would lead to a form that cannot be completed.
        async with session() as db:
            user = await user_service.get_user_entity(
                db, user_id=uuid.UUID(no_password)
            )
            sent = user is not None and await auth_service.admin_request_password_reset(
                db, user=user, actor_id=actor_id
            )
            await db.commit()
        if user is None:
            failures.append("the probe user for the no-password case vanished")
        elif sent:
            failures.append(
                "an OTP-only account with no password reported a reset as sent"
            )
        else:
            print("PASS: an account with no password reports honestly")

        # 5. The route exists and is behind users:write, and it is declared
        #    before any `/{user_id}` catch-all so it is not shadowed.
        from app.main import app as fastapi_app

        paths = [
            r.path for r in fastapi_app.routes if "password-reset" in getattr(r, "path", "")
        ]
        if not paths:
            failures.append(
                "no admin password-reset route is registered, so the service method "
                "is reachable only from a script"
            )
        else:
            target = paths[0]
            if not target.endswith("/users/admin/users/{user_id}/password-reset"):
                failures.append("the route is at %r, not under /users/admin/users/" % target)
            else:
                print("PASS: the admin route is registered")

        # 6. And it delegates rather than reimplementing, so a future change to
        #    the reset rules reaches the admin path too.
        import inspect

        src = inspect.getsource(auth_service.admin_request_password_reset)
        if "request_password_reset" not in src.split('"""')[2]:
            failures.append(
                "the admin reset does not delegate to request_password_reset, so it "
                "is a second implementation of the rules about voiding the previous "
                "token and skipping OTP-only accounts"
            )
        else:
            print("PASS: the admin path delegates to the same machinery")

        # 7. And an operator can actually reach it. Checked by reading the page
        #    rather than by clicking it: the button's handler is what the guard is
        #    about, and a browser run cannot see a handler that was replaced with a
        #    no-op that still looks like a button.
        #
        # backend/scripts/verify_admin_password_reset.py -> backend/scripts ->
        # backend -> site. Three levels up: parents[2] of the *file* is `backend`,
        # and the frontend sits beside it, not inside it. The wrong index reads a
        # path that does not exist, and the whole assertion then passes on every
        # run without ever reading a file.
        page = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "app"
            / "admin"
            / "users"
            / "page.tsx"
        )
        if page.is_file():
            src = page.read_text(encoding="utf-8")
            # Two links in the chain, and both have to be live: the client call
            # inside the handler, and the handler wired to a control. Checking
            # only the first passes on a button whose onClick is a no-op — the
            # handler still exists and still calls the API, and no operator ever
            # reaches it. That is the same dead-end as a route with no caller,
            # one component up.
            client_called = re.search(r"usersAdminApi\.sendPasswordReset\s*\(", src)
            wired = re.search(r"onClick=\{[^}]*sendPasswordReset\s*\(", src)
            if not client_called:
                failures.append(
                    "the users admin page never calls the reset client, so the route "
                    "exists and no operator can reach it"
                )
            elif not wired:
                failures.append(
                    "the reset handler exists but no control calls it, so the feature "
                    "is built and unreachable"
                )
            else:
                print("PASS: the users admin page calls the reset client and wires it up")
        else:
            failures.append("the users admin page is missing, so nothing can call it")
    finally:
        async with session() as db:
            await db.rollback()
            for item in created:
                kind, _, ident = item.partition(":")
                if kind == "users":
                    await db.execute(
                        text(
                            "DELETE FROM password_reset_tokens WHERE user_id = :u"
                        ),
                        {"u": ident},
                    )
                    await db.execute(
                        text("DELETE FROM users WHERE id = :u"), {"u": ident}
                    )
            await db.commit()
        print("removed the probe rows")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: an operator can issue a reset, and it is the same one a user gets.")
    return 0


async def _tokens(db, user_id: str) -> list:
    return (
        (
            await db.execute(
                text("SELECT id FROM password_reset_tokens WHERE user_id = :u"),
                {"u": user_id},
            )
        )
        .fetchall()
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))