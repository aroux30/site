"""Live check: the store name an operator sets actually reaches the storefront.

P0 "تنظیمات: مشخصات فروشگاه". The settings screen writes `store.identity` as a
JSON blob and nothing read it — no public endpoint returned it, so the header,
the footer, the SEO metadata and all four transactional emails carried a
hardcoded string. This asserts the round trip: write the setting, then read it
back through each consumer that matters.

    cd backend && PYTHONPATH=. python scripts/verify_store_identity_reaches.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import pkgutil
import sys
import uuid

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

PROBE = f"فروشگاه-پروب-{uuid.uuid4().hex[:6]}"


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
        original = await SiteOptionsService.get(db, "store.identity")
        try:
            # 1. Write exactly what the settings screen writes.
            await SiteOptionsService.set(
                db, "store.identity", json.dumps({"store_name": PROBE}, ensure_ascii=False)
            )
            await db.commit()

            # 2. The public endpoint is what the storefront calls for its
            #    chrome. If it does not carry the name, the storefront cannot
            #    use it no matter what the frontend does.
            from app.modules.settings.api.routes import (
                get_public_branding,
                _public_store_name,
            )

            branding = await get_public_branding(db)
            if branding.get("store_name") != PROBE:
                failures.append(
                    "the public branding endpoint reports store_name=%r, expected %r"
                    % (branding.get("store_name"), PROBE)
                )
            else:
                print("PASS: the public branding endpoint carries the store name")

            # 3. An empty blob must fall back rather than publish nothing, and
            #    a malformed one must not 500 the storefront.
            await SiteOptionsService.set(db, "store.identity", "{not json")
            await db.commit()
            try:
                fallback = await _public_store_name(db)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"a malformed store.identity raised {type(exc).__name__}: {exc}")
            else:
                if fallback == "":
                    print("      (no blogname set either, so the caller falls back)")
                else:
                    print("PASS: a malformed blob falls back to blogname, not a crash")

            # 4. The transactional emails must use it — this is the half that
            #    shows up in the customer's inbox with the wrong sender name.
            await SiteOptionsService.set(
                db, "store.identity", json.dumps({"store_name": PROBE}, ensure_ascii=False)
            )
            await db.commit()

            from app.modules.notifications.application.email_service import (
                default_email_templates,
            )
            from app.modules.notifications.application.email_template_service import (
                _operator_store_name,
            )

            resolved = await _operator_store_name(db)
            if resolved != PROBE:
                failures.append(
                    "the email resolver reports %r, expected %r" % (resolved, PROBE)
                )
            else:
                print("PASS: the email template resolver reads the store name")

            templates = default_email_templates(resolved)
            wrong = [
                name
                for name, content in templates.items()
                if "فروشگاه اینترنتی" in (content.html or "")
            ]
            if wrong:
                failures.append(
                    "these templates still carry the hardcoded default: %s"
                    % ", ".join(sorted(wrong))
                )
            else:
                print(
                    "PASS: all %d built-in templates use the operator's name"
                    % len(templates)
                )

            # 5. And the default still works for a caller with no name, so the
            #    signature change did not make the templates unreadable.
            plain = default_email_templates()
            if not any("فروشگاه اینترنتی" in (c.html or "") for c in plain.values()):
                failures.append(
                    "with no name supplied the templates lost their default, so a "
                    "caller without a settings session would render an empty shell"
                )
            else:
                print("PASS: the default is kept for callers with no name")

        finally:
            await SiteOptionsService.set(db, "store.identity", original)
            await db.commit()
            print("restored the original store.identity")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the store name reaches the public endpoint and the emails.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))