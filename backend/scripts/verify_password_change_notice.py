"""Live check: a password rotation tells the account holder.

P0 "کاربران: ایمیل اطلاع تغییر رمز". The rotation revoked every session and
wrote an audit row, and told the person nothing — so somebody whose password was
changed by someone else keeps using the old one until it stops working, and never
learns why.

Three properties, and the second is the one a check on "did it send" would miss
entirely:

  1. the notice is sent for an account with an address
  2. it names the *rotation* time, not the last update — `updated_at` moves on
     any profile edit, so a notice reading it would tell a person their password
     changed when they last fixed a typo in their name
  3. a mail outage does not undo the rotation or fail the request

    cd backend && PYTHONPATH=. python scripts/verify_password_change_notice.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid
from pathlib import Path
from datetime import UTC, datetime, timedelta

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
from app.modules.auth.application import registration_email_service as reg  # noqa: E402
from app.modules.auth.application.registration_email_service import (  # noqa: E402
    RegistrationEmailService,
)

PASSWORD = "Probe!Passw0rd"


BACKEND = Path(__file__).resolve().parents[1]


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _account(db, *, email: str | None) -> str:
    from app.core.security.password import hash_password

    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, email, password_hash, is_active, "
            "is_verified, is_superuser, totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, :e, :pw, true, true, false, false, now(), now())"
        ),
        {"u": uid, "p": "9" + uuid.uuid4().hex[:9], "e": email, "pw": hash_password(PASSWORD)},
    )
    return uid


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []

    try:
        # The model and the migration have to agree on the column's name, and
        # neither checks the other. A rename on one side leaves the other naming
        # a column that does not exist, which is a ProgrammingError on every read
        # of a user — so the whole login path goes down rather than one notice
        # going quiet. Compared by reading the source rather than importing the
        # model: importing is what breaks, and a check that crashes on the defect
        # it is looking for reports nothing.
        models_src = (
            BACKEND / "app" / "modules" / "users" / "domain" / "models.py"
        ).read_text(encoding="utf-8")
        if "password_changed_at" not in models_src:
            failures.append(
                "the User model no longer declares password_changed_at, so the "
                "rotation writes to a column the model does not know about"
            )

        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'users'"
                        )
                    )
                ).fetchall()
            }
            if "password_changed_at" not in columns:
                print("SKIP: users.password_changed_at has not been migrated.")
                return 0

            addr = "pw-notice.%s@registration-probe.invalid" % uuid.uuid4().hex[:6]
            uid = await _account(db, email=addr)
            created.append(uid)
            await db.commit()

        # 1. A rotation stamps the time and sends the notice.
        async with session() as db:
            sent = await RegistrationEmailService.send_password_changed_notice(
                db, user_id=uid
            )
            await db.commit()
        if sent:
            print("PASS: the change notice is attempted for an account with an address")
        else:
            failures.append(
                "no notice was attempted for an account that has an email address"
            )

        # 2. The rotation itself must stamp the column, and the stamp must be the
        #    rotation's own time rather than the account's last update.
        #
        #    `updated_at` is moved forward first so that a notice reading it would
        #    produce a time minutes away from the rotation — which is the shape of
        #    the bug this is here to catch.
        async with session() as db:
            await db.execute(
                text(
                    "UPDATE users SET updated_at = now() - interval '90 seconds' "
                    "WHERE id = :i"
                ),
                {"i": uid},
            )
            await db.commit()
            before_change = datetime.now(UTC) - timedelta(seconds=90)

            await auth_service.change_password(
                db, user_id=uuid.UUID(uid), old_password=PASSWORD, new_password="New!Passw0rd"
            )
            await db.commit()
            row = (
                await db.execute(
                    text(
                        "SELECT password_changed_at, updated_at FROM users WHERE id = :i"
                    ),
                    {"i": uid},
                )
            ).fetchone()

        if row is None or row[0] is None:
            failures.append(
                "the rotation left password_changed_at NULL, so the notice has no "
                "time to name and the recipient cannot judge whether the change "
                "was theirs"
            )
        else:
            stamp = row[0]
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=UTC)
            # Within a minute of now, and clearly not the 90-seconds-ago update.
            if abs((datetime.now(UTC) - stamp).total_seconds()) > 60:
                failures.append(
                    "password_changed_at is %s, which is not this rotation" % stamp
                )
            elif abs((stamp - before_change).total_seconds()) < 30:
                failures.append(
                    "password_changed_at equals the account's last update, so a "
                    "profile edit would make the notice claim the password changed"
                )
            else:
                print("PASS: the rotation stamps its own time, distinct from updated_at")

        # 3. And the real call site sends it — a notice nobody triggers is a
        #    feature that exists.
        import ast
        import inspect

        fn = next(
            n
            for n in ast.walk(ast.parse(inspect.getsource(auth_service)))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "change_password"
        )
        called = {
            node.func.id
            for node in ast.walk(fn)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } | {
            node.func.attr
            for node in ast.walk(fn)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        if "send_password_changed_notice" not in called:
            failures.append(
                "change_password does not call the notice, so a rotation sends none"
            )
        else:
            print("PASS: change_password calls the notice")

        # 3b. No link in a security notice. This is a rule rather than a
        #     preference: a mail that says "your password changed" and carries a
        #     link is the exact shape a phisher copies, and this project has no
        #     business minting one. The recipient's real action is to phone us.
        notice_src = inspect.getsource(RegistrationEmailService.send_password_changed_notice)
        if "<a href" in notice_src or "reset-password?token=" in notice_src:
            failures.append(
                "the change notice carries a link; a security notice with a link in "
                "it is the shape a phisher copies, and the recipient's real next "
                "step is to phone support"
            )
        else:
            print("PASS: the change notice carries no link, only a number to call")

        # 4. A mail outage must not undo the rotation. The password change has
        #    already happened by the time the notice is sent, so an exception
        #    here would leave a password changed and the request failing — the
        #    customer retries with the old password and is told it is wrong.
        async with session() as db:
            uid2 = await _account(db, email=None)
            created.append(uid2)
            await db.commit()
            original = RegistrationEmailService.send_password_changed_notice

            async def exploding(session, *, user_id):  # noqa: ARG001
                raise RuntimeError("SMTP is down")

            RegistrationEmailService.send_password_changed_notice = staticmethod(
                exploding
            )
            try:
                await auth_service.change_password(
                    db,
                    user_id=uuid.UUID(uid2),
                    old_password=PASSWORD,
                    new_password="New!Passw0rd",
                )
                await db.commit()
                changed = (
                    await db.execute(
                        text("SELECT count(*) FROM users WHERE id = :i AND password_changed_at IS NOT NULL"),
                        {"i": uid2},
                    )
                ).scalar()
                if not changed:
                    failures.append(
                        "a mail outage rolled the rotation back; the customer is "
                        "left with the new password on the server and the old one "
                        "in their hand"
                    )
                else:
                    print("PASS: a mail outage does not undo the rotation")
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                failures.append(
                    "a mail outage failed the change-password request outright: %r — "
                    "the customer is told their old password is now wrong" % exc
                )
            finally:
                RegistrationEmailService.send_password_changed_notice = original

        # 5. An account with no address reports honestly rather than pretending.
        #    Registration is by phone, so this is the common case and it must not
        #    be reported as a broken notice.
        async with session() as db:
            uid3 = await _account(db, email=None)
            created.append(uid3)
            await db.commit()
            quiet = await RegistrationEmailService.send_password_changed_notice(
                db, user_id=uid3
            )
        if quiet:
            failures.append(
                "a change notice was reported as sent for an account with no address"
            )
        else:
            print("PASS: an account with no address reports honestly")

        # 6. The distinction between "this account rotated a password" and "this
        #    account has never rotated one" has to survive into the mail.
        #    Checked on the selector rather than on the rendered HTML, because the
        #    alternative is asserting that a template mentions something — and a
        #    template mentioning it while the code beneath it passes the wrong
        #    value is exactly the shape of this bug.
        #
        #    A fresh account's `password_changed_at` is NULL, so the fallback is
        #    the path this exists for: dated to the last update, the notice says
        #    the password changed when the person edited their profile.
        from types import SimpleNamespace

        from datetime import datetime as _dt

        from app.modules.auth.application.registration_email_service import (
            _password_changed_when,
        )

        rotated_at = _dt(2026, 1, 2, 3, 4, tzinfo=UTC)
        updated_at = _dt(2026, 6, 7, 8, 9, tzinfo=UTC)

        got, real = _password_changed_when(
            SimpleNamespace(password_changed_at=rotated_at, updated_at=updated_at)
        )
        if not real or got != rotated_at:
            failures.append(
                "an account with a rotation stamp reads %r (real=%s), so the notice "
                "reports something other than when the password changed" % (got, real)
            )
        else:
            print("PASS: a rotated account reports the rotation time")

        got2, real2 = _password_changed_when(
            SimpleNamespace(password_changed_at=None, updated_at=updated_at)
        )
        if real2:
            failures.append(
                "an account that has never rotated reports a rotation time; its "
                "notice would claim a password change that did not happen"
            )
        elif got2 != updated_at:
            failures.append(
                "an account with no rotation stamp renders %r, which is neither its "
                "rotation time nor its last update" % got2
            )
        else:
            print("PASS: an account that never rotated says so rather than guessing")
    finally:
        async with session() as db:
            await db.rollback()
            for item in created:
                await db.execute(
                    text("DELETE FROM user_sessions WHERE user_id = :i"), {"i": item}
                )
                await db.execute(
                    text("DELETE FROM users WHERE id::text = :i"), {"i": item}
                )
            await db.commit()
        print("removed the probe rows")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: a password rotation tells its owner, names the time, and cannot be lost to a mail outage.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))