"""Live check: a registration produces both emails, and neither can break it.

P0 "کاربران: ایمیل خوش‌آمد ثبت‌نام و اطلاع به مدیر". Neither existed. The
customer got a token pair and a flash of success; the store got an audit row
nobody reads during business hours.

Four properties, and the last two are the ones that decide whether this is a
feature or a hazard:

  1. an account *with* an address gets a welcome; one without reports honestly,
     because registration is by phone and most accounts have no address
  2. the store's admin address gets a notice
  3. a signup still returns its token pair when the mail step raises — an SMTP
     outage must not cost the customer an account they were told was created
  4. the call site is real, not a name in a comment

    cd backend && PYTHONPATH=. python scripts/verify_registration_emails.py
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import io
import pkgutil
import sys
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
from app.modules.auth.application import registration_email_service as reg  # noqa: E402
from app.modules.auth.application.registration_email_service import (  # noqa: E402
    RegistrationEmailService,
)

PROBE_DOMAIN = "registration-probe.invalid"


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _write_option(db, key: str, value: str | None) -> None:
    if value is None:
        await db.execute(
            text("DELETE FROM site_options WHERE option_key = :k"), {"k": key}
        )
    else:
        await db.execute(
            text(
                "INSERT INTO site_options (id, option_key, option_value, autoload, "
                "created_at, updated_at) VALUES (:i, :k, :v, false, now(), now()) "
                "ON CONFLICT (option_key) DO UPDATE SET option_value = "
                "EXCLUDED.option_value, updated_at = now()"
            ),
            {"i": str(uuid.uuid4()), "k": key, "v": value},
        )


async def _user(db, *, email: str | None) -> str:
    """One account, plus the audit row the admin notice reads its IP from.

    The audit row is not decoration: the notice resolves the signup address out
    of it, so without one it finds nothing and the "with an IP" and "without an
    IP" paths are indistinguishable — which is exactly the ambiguity this check
    would then be unable to resolve.
    """
    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, email, password_hash, is_active, "
            "is_verified, is_superuser, totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, :e, 'x', true, true, false, false, now(), now())"
        ),
        {"u": uid, "p": "9" + uuid.uuid4().hex[:9], "e": email},
    )
    await db.execute(
        text(
            "INSERT INTO audit_logs (id, actor_id, action, resource, resource_id, "
            "ip_address, created_at, updated_at) "
            "VALUES (:i, :a, 'user.register', 'user', :r, '203.0.113.11', "
            "now(), now())"
        ),
        {"i": str(uuid.uuid4()), "a": uid, "r": uid},
    )
    return uid


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []
    original_admin_email = None
    _probe_admin = ""

    try:
        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'site_options'"
                        )
                    )
                ).fetchall()
            }
            if not {"option_key", "option_value"} <= columns:
                print("SKIP: site_options has no option_key/option_value pair.")
                return 0

            original_admin_email = (
                await db.execute(
                    text("SELECT option_value FROM site_options WHERE option_key = :k"),
                    {"k": "admin_email"},
                )
            ).scalar()
            _probe_admin = "probe-admin.%s@example.invalid" % uuid.uuid4().hex[:6]
            await _write_option(db, "admin_email", _probe_admin)
            await db.commit()

        # 1. An account with an address gets a welcome.
        with_addr = "probe-welcome.%s@%s" % (uuid.uuid4().hex[:6], PROBE_DOMAIN)
        async with session() as db:
            uid = await _user(db, email=with_addr)
            created.append(uid)
            await db.commit()
            welcome = await RegistrationEmailService.send_welcome(db, user_id=uid)
            await db.commit()

        if welcome:
            print("PASS: the welcome send is attempted for an account with an address")
        else:
            failures.append(
                "no welcome was attempted for an account that has an email address"
            )

        # 2. And the store hears about it.
        async with session() as db:
            notified = await RegistrationEmailService.notify_admin(db, user_id=uid)
            await db.commit()
        if notified:
            print("PASS: the store's admin address is notified of the signup")
        else:
            failures.append(
                "the admin signup notice was not attempted; a new account is "
                "invisible to the operator until they go looking"
            )

        # 2b. And the address comes from the store's own setting, not from a
        #     literal. A hardcoded recipient would still produce a delivered
        #     mail and still be wrong: the operator who changes the address in
        #     Settings would go on reading notices in an inbox nobody owns.
        from app.modules.auth.application.registration_email_service import _admin_email

        async with session() as db:
            resolved = await _admin_email(db)
        if resolved != _probe_admin:
            failures.append(
                "the admin recipient resolved to %r, not the address configured in "
                "the store's settings — a hardcoded one keeps delivering after the "
                "operator changes it" % resolved
            )
        else:
            print("PASS: the admin recipient is read from the store's settings")

        # 3. No address is a normal outcome, not a failure. Registration is by
        #    phone and most accounts have no email, so this is the common path
        #    and must not report as broken.
        async with session() as db:
            quiet_uid = await _user(db, email=None)
            created.append(quiet_uid)
            await db.commit()
            quiet = await RegistrationEmailService.send_welcome(db, user_id=quiet_uid)
            await db.commit()
        if quiet:
            failures.append(
                "a welcome was reported as sent for an account with no address"
            )
        else:
            print("PASS: an account with no address reports honestly")

        # 4. The load-bearing one. Patched at the boundary register calls, so
        #    the try/except in register is what is under test — a re-implementation
        #    of it here would prove nothing about the real path.
        async with session() as db:
            original = reg.send_registration_emails

            async def exploding(session, *, user_id):  # noqa: ARG001
                raise RuntimeError("SMTP is down")

            reg.send_registration_emails = exploding
            try:
                phone = "9" + uuid.uuid4().hex[:9]
                tokens = None
                try:
                    tokens = await auth_service.register(
                        db,
                        phone=phone,
                        password="Probe!Passw0rd",
                        first_name="Probe",
                        last_name="User",
                    )
                    await db.commit()
                except Exception as exc:  # noqa: BLE001
                    await db.rollback()
                    failures.append(
                        "a mail outage took the signup with it: %r. The customer is "
                        "told their account exists and then no token pair comes "
                        "back, and the account is rolled back with it." % exc
                    )
                else:
                    if tokens is None or "access_token" not in tokens:
                        failures.append(
                            "a mail outage cost the customer their token pair, so the "
                            "signup reported success while returning nothing usable"
                        )
                    else:
                        created.append(phone)
                        print("PASS: a mail outage does not fail the signup")
            finally:
                reg.send_registration_emails = original

        # 5. And the call site is real. The check is a *call*, not a name: register's
        # own comment quotes ``send_registration_emails`` while explaining what it
        # does, so a substring search over the source is satisfied by the prose
        # describing the call that is not there.
        import ast

        fn = next(
            n
            for n in ast.walk(ast.parse(inspect.getsource(auth_service)))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "register"
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
        if "send_registration_emails" not in called:
            failures.append(
                "register does not call the email service, so the feature exists "
                "and nothing sends"
            )
        else:
            print("PASS: register calls the email service")
    finally:
        async with session() as db:
            await db.rollback()
            # `created` holds two kinds of probe and they are cleaned up by
            # different columns. A phone number is not a uuid, and passing one to
            # the uuid column is a DataError; a uuid is not a phone, and passing
            # one there is a silent no-op. So: uuid-shaped values are removed from
            # both columns, and anything else is treated as a phone.
            for item in created:
                looks_like_uuid = len(item) in (32, 36) and "-" in item
                if looks_like_uuid:
                    await db.execute(
                        text("DELETE FROM audit_logs WHERE resource_id = :i"), {"i": item}
                    )
                    await db.execute(
                        text("DELETE FROM users WHERE id::text = :i"), {"i": item}
                    )
                else:
                    await db.execute(
                        text("DELETE FROM users WHERE phone = :i"), {"i": item}
                    )
            await _write_option(db, "admin_email", original_admin_email)
            await db.commit()
        print("removed the probe rows")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: a registration says hello, tells the store, and survives a mail outage.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))