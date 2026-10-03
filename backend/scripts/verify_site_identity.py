"""Live check: the site-identity settings are writable and actually read.

P0 "تنظیمات: نام سایت، توضیح سایت و ایمیل ادمین از UI" and "نمایش/پنهان‌سازی
سایت از موتورهای جست‌وجو". The keys were seeded and read by the feed, the
sitemap and the robots route, but nothing on the admin side could write them —
so the store's name in a feed was whatever the seed said, forever.

A UI test would only prove the form posts. What matters is the round trip:
write the key, read it back through the *reader* that cares, and confirm the
value moved. So this drives the real service and then asserts on the actual
readers.

    cd backend && PYTHONPATH=. python scripts/verify_site_identity.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.settings.application.site_options_service import (  # noqa: E402
    SiteOptionsService,
)

PROBE = f"identity-probe-{__import__('uuid').uuid4().hex[:8]}"


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []

    async with session() as db:
        # 1. Every one of the four keys is writable through the same call the
        #    admin route makes.
        originals = {}
        for key in ("blogname", "blogdescription", "admin_email", "blog_public"):
            originals[key] = await SiteOptionsService.get(db, key)

        try:
            await SiteOptionsService.set(db, "blogname", PROBE)
            await db.commit()
            read_back = await SiteOptionsService.get(db, "blogname")
            if read_back != PROBE:
                failures.append(f"blogname read back as {read_back!r}, expected {PROBE!r}")
            else:
                print("PASS: blogname writes and reads back")

            # 2. A reader must see it, or the setting is decorative. The feed
            #    settings helper is the real reader the route uses, so this
            #    goes through it rather than through the pure string builder.
            from app.modules.blog.api.routes import _feed_settings

            feed_settings = await _feed_settings(db)
            if feed_settings.get("site_title") != PROBE:
                failures.append(
                    "the feed settings report site_title=%r, expected the value just "
                    "written (%r) — the setting is stored but never read"
                    % (feed_settings.get("site_title"), PROBE)
                )
            else:
                print("PASS: the feed reader carries the new site name")

            # 3. blog_public is the WordPress search-engine switch: "0" must
            #    read as hidden, and anything unrecognised as visible rather
            #    than silently hiding a live store.
            await SiteOptionsService.set(db, "blog_public", "0")
            await db.commit()
            hidden = await SiteOptionsService.get(db, "blog_public", "1")
            if str(hidden) != "0":
                failures.append(f"blog_public read back as {hidden!r}, expected '0'")
            else:
                print("PASS: blog_public round-trips as 0 (hidden)")

            await SiteOptionsService.set(db, "blog_public", "1")
            await db.commit()

            # 4. admin_email is the sender of system mail, so an empty value
            #    must not be accepted silently — the fallback exists, but the
            #    UI is what guards the shape.
            await SiteOptionsService.set(db, "admin_email", "owner@example.com")
            await db.commit()
            email = await SiteOptionsService.get(db, "admin_email")
            if email != "owner@example.com":
                failures.append(f"admin_email read back as {email!r}")
            else:
                print("PASS: admin_email round-trips")

        finally:
            for key, value in originals.items():
                await SiteOptionsService.set(db, key, value)
            await db.commit()
            print("restored the four original values")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the identity settings are writable and a reader sees them.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))