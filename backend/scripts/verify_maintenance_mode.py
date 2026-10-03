"""Live check: maintenance mode takes the store down and brings it back.

P0 "ابزارها: حالت نگهداری". Nothing existed — no flag, no page, no gate. An
operator about to run a migration against a live storefront had two options,
both bad: take the site down at the load balancer and hope they remember to
bring it back, or deploy over a running shop.

Six properties. Two of them are the ones people get wrong, and both are
failures that look like the feature working:

  - the flag **lapses**. An operator who sets it and goes home must not have
    left a store that cannot be reached until they come back.
  - staff are **exempt**. Locking the operator out of the panel to end their own
    maintenance turns a ten-minute migration into an all-day outage.

The rest follow from those: the gate returns 503 with a Retry-After (a 200 gets
cached by every CDN in front of the store and served long after the migration is
over), health checks stay reachable (a load balancer that pulls the instance
removes the only way to turn the flag off), and turning it off restores service.

    cd backend && PYTHONPATH=. python scripts/verify_maintenance_mode.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import pkgutil
import sys
import uuid
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

from app.core.middleware.maintenance_middleware import (  # noqa: E402
    RETRY_AFTER_SECONDS,
    MaintenanceMiddleware,
)
from app.modules.settings.application import maintenance_service as svc  # noqa: E402

OPTION = svc.MAINTENANCE_OPTION


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _option(db) -> str | None:
    return (
        await db.execute(
            text("SELECT option_value FROM site_options WHERE option_key = :k"),
            {"k": OPTION},
        )
    ).scalar()


class _Req:
    """The slice of a Starlette request the middleware reads."""

    def __init__(self, path: str, token: str | None = None):
        self.url = type("U", (), {"path": path})()
        self.headers = {}
        if token:
            self.headers["authorization"] = "Bearer %s" % token


async def _call_mw(path: str, token: str | None = None):
    """Run one request through the middleware, as the app would."""
    seen = {"called": False}

    async def call_next(_request):
        seen["called"] = True
        return "passed-through"

    mw = MaintenanceMiddleware(app=lambda *a, **k: None)
    result = await mw.dispatch(_Req(path, token), call_next)
    return result, seen["called"]


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    original = None
    created: list[str] = []

    try:
        async with session() as db:
            original = await _option(db)
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

        # 1. Off by default: a store that has never used the feature serves
        #    traffic, and a store whose flag is corrupt serves traffic rather
        #    than becoming unreachable.
        async with session() as db:
            await svc.set_maintenance(db, active=False)
            await db.commit()
            off = await svc.get_state(db)
        if off.active:
            failures.append("a store with the flag off reports itself as in maintenance")
        else:
            print("PASS: the flag reads as off when it is off")

        # 2. On: state, and the gate answers 503 with Retry-After.
        async with session() as db:
            await svc.set_maintenance(db, active=True, minutes=30, reason="ارتقای پایگاه داده")
            await db.commit()
            on = await svc.get_state(db)
        if not on.active or on.reason != "ارتقای پایگاه داده":
            failures.append(
                "the flag did not take: active=%r reason=%r" % (on.active, on.reason)
            )
        else:
            print("PASS: the flag reads as on with the operator's reason")

        response, passed = await _call_mw("/api/v1/products")
        if passed:
            failures.append(
                "a public request went through while the store was in maintenance"
            )
        elif getattr(response, "status_code", None) != 503:
            failures.append(
                "the gate answered %r rather than 503; a 200 gets cached by every "
                "CDN in front of the store" % getattr(response, "status_code", None)
            )
        elif "retry-after" not in {h.lower() for h in response.headers}:
            failures.append("the 503 carries no Retry-After, so clients hammer the store")
        else:
            print(
                "PASS: a public request gets 503 with Retry-After=%s"
                % response.headers.get("retry-after")
            )

        # 3. Health checks stay reachable, or the load balancer pulls the
        #    instance and the flag cannot be turned off from anywhere.
        for path in ("/healthz", "/readyz", "/api/v1/health/live"):
            response, passed = await _call_mw(path)
            if not passed:
                failures.append(
                    "%s was blocked during maintenance; a load balancer that sees a "
                    "503 here pulls the instance and the flag becomes impossible to "
                    "clear" % path
                )
        else:
            print("PASS: health checks stay reachable during maintenance")

        # 4. The operator gets in. Token-level, because the middleware resolves
        #    the caller itself rather than trusting a header.
        async with session() as db:
            real_admin = (
                await db.execute(
                    text(
                        "SELECT id FROM users WHERE is_superuser AND is_active "
                        "ORDER BY created_at LIMIT 1"
                    )
                )
            ).scalar()
        if real_admin is not None:
            from app.core.security.jwt import create_access_token

            token = create_access_token(real_admin)
            response, passed = await _call_mw("/api/v1/products", token=token)
            if not passed:
                failures.append(
                    "a superuser was blocked during maintenance; locking the "
                    "operator out of the panel to end their own maintenance turns a "
                    "ten-minute migration into an all-day outage"
                )
            else:
                print("PASS: a superuser gets through during maintenance")

            # And a non-staff caller does not, even with a valid token. An
            # exemption that is "any logged-in user" is not an exemption.
            #
            # A real, *inactive* staff account rather than an invented uuid: an
            # id that is not in the users table is rejected by the first check, so
            # it would pass on a guard that had lost every later check. An
            # inactive holder of the admin role is the case that distinguishes
            # "is this person staff" from "can this person act" — a
            # deactivated operator's token is still in their browser, and the
            # exemption is exactly the thing that would let it through.
            role_id = (
                await db.execute(text("SELECT id FROM roles WHERE slug = 'admin'"))
            ).scalar()
            inactive_id = str(uuid.uuid4())
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, is_superuser, is_active, "
                    "is_verified, totp_enabled, created_at, updated_at) "
                    "VALUES (:u, :p, false, false, true, false, now(), now())"
                ),
                {"u": inactive_id, "p": "9" + uuid.uuid4().hex[:9]},
            )
            await db.execute(
                text(
                    "INSERT INTO user_roles (id, user_id, role_id, created_at, "
                    "updated_at) VALUES (gen_random_uuid(), :u, :r, now(), now())"
                ),
                {"u": inactive_id, "r": str(role_id)},
            )
            created.append(inactive_id)
            await db.commit()
            response, passed = await _call_mw(
                "/api/v1/products", token=create_access_token(inactive_id)
            )
            if passed:
                failures.append(
                    "a deactivated staff account got through; their token is still "
                    "in a browser somewhere, and exempting it is a way around "
                    "maintenance rather than a way to run a migration"
                )
            else:
                print("PASS: a deactivated staff account is still blocked")

        # 5. The flag lapses. Written as an already-elapsed value rather than by
        #    waiting, because the alternative is a test that takes ten minutes.
        async with session() as db:
            from app.modules.settings.application.site_options_service import (
                SiteOptionsService,
            )

            expired = json.dumps(
                {
                    "active": True,
                    "reason": "expired",
                    "minutes": 10,
                    "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                }
            )
            await SiteOptionsService.set(db, OPTION, expired)
            await db.commit()
            lapsed = await svc.get_state(db)
        if lapsed.active:
            failures.append(
                "a flag whose expiry has passed still reads as active; an operator "
                "who sets it and goes home has left the store down until they return"
            )
        else:
            print("PASS: an elapsed flag reads as off by itself")

        # 6. And a corrupt one is treated the same way. A flag that cannot be
        #    parsed must not lock a store out: the failure of ignoring it is a
        #    storefront that is up when it should be down, which somebody can see.
        async with session() as db:
            from app.modules.settings.application.site_options_service import (
                SiteOptionsService,
            )

            await SiteOptionsService.set(db, OPTION, "{not json at all")
            await db.commit()
            broken = await svc.get_state(db)
        if broken.active:
            failures.append(
                "an unreadable flag value locks the store out; the safer reading of "
                "a corrupt flag is 'not in maintenance'"
            )
        else:
            print("PASS: a corrupt flag is treated as off")

        # 7. And turning it off restores service, which is the whole round trip.
        async with session() as db:
            await svc.set_maintenance(db, active=True, minutes=30)
            await db.commit()
            _, reached_before = await _call_mw("/api/v1/products")
            await svc.set_maintenance(db, active=False)
            await db.commit()
            _, reached_after = await _call_mw("/api/v1/products")
        # "Blocked" means the request never reached a handler, which is what
        # `passed` reports. Reading the response instead compares an HTMLResponse
        # to a string that says the request passed, which is never equal and so
        # reports the gate as not blocking even when it blocks every time.
        blocked = not reached_before
        served = reached_after
        if not blocked:
            failures.append("the gate did not block before the flag was cleared")
        elif not served:
            failures.append(
                "traffic is still blocked after the flag was cleared; a gate that "
                "will not open is the outage this feature exists to prevent"
            )
        else:
            print("PASS: clearing the flag restores service")

        # 8. And the endpoint an operator reads before a migration, which is what
        #    the storefront asks so it can render the page itself.
        from app.main import app as fastapi_app

        paths = [
            r.path for r in fastapi_app.routes if "maintenance" in getattr(r, "path", "")
        ]
        if not any(p.endswith("/settings/public/maintenance") for p in paths):
            failures.append(
                "no public maintenance endpoint, so a client-rendered storefront "
                "cannot show the page and shows a network error instead"
            )
        else:
            public = next(
                p for p in paths if p.endswith("/settings/public/maintenance")
            )
            order = [r.path for r in fastapi_app.routes if r.path.startswith("/api/v1/settings")]
            catch_all = [p for p in order if p == "/api/v1/settings/{key}"]
            if catch_all and order.index(public) > order.index(catch_all[0]):
                failures.append(
                    "the maintenance endpoint is declared after /{key}, so FastAPI "
                    "matches the catch-all first and every caller gets a 404"
                )
            else:
                print("PASS: the public endpoint is reachable")

        if RETRY_AFTER_SECONDS < 60:
            failures.append(
                "Retry-After is under a minute, so every client retries in a tight "
                "loop while the store is down"
            )
    finally:
        async with session() as db:
            from app.modules.settings.application.site_options_service import (
                SiteOptionsService,
            )

            if original is None:
                await db.execute(
                    text("DELETE FROM site_options WHERE option_key = :k"), {"k": OPTION}
                )
            else:
                await SiteOptionsService.set(db, OPTION, original)
            await db.commit()
        async with session() as db:
            await db.rollback()
            for uid in created:
                await db.execute(
                    text("DELETE FROM user_roles WHERE user_id::text = :u"), {"u": uid}
                )
                await db.execute(
                    text("DELETE FROM users WHERE id::text = :u"), {"u": uid}
                )
            await db.commit()
        print("restored the maintenance flag")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: maintenance takes the store down for everyone but staff, and comes back on its own.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))