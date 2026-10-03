"""Live check: the privacy policy a form links to actually resolves.

P0 "حریم خصوصی: اطلاع‌رسانی حریم خصوصی در فرم‌ها". WordPress stores the id of
a published page and links it from every form that collects personal data. This
project had neither the setting nor the link, so a visitor who typed a phone
number into the registration form was never told what would happen to it.

Four cases, and the last two are the ones that matter most:

  1. a published, public page resolves — the link a form renders
  2. a *draft* page does not: nobody consented to a document they cannot read
  3. a *published but private* page does not, either — this store models that
     state for posts, and linking a hidden document from a public form would
     leak that it exists
  4. the route is reachable, and reachable as a route rather than swallowed by
     the `/{key}` catch-all sitting below it

    cd backend && PYTHONPATH=. python scripts/verify_privacy_policy.py
"""

from __future__ import annotations

import asyncio
import importlib
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

from app.modules.settings.application.privacy_policy_service import (  # noqa: E402
    PRIVACY_POLICY_OPTION,
    PrivacyPolicyService,
)


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _make_page(db, *, status: str, visibility: str) -> tuple[str, str]:
    slug = "privacy-probe-%s" % uuid.uuid4().hex[:8]
    pid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO cms_pages (id, title, slug, body_html, status, visibility, "
            "created_at, updated_at) VALUES (:i, :t, :s, 'body', :st, :v, now(), now())"
        ),
        {"i": pid, "t": "Probe Policy", "s": slug, "st": status, "v": visibility},
    )
    return pid, slug


async def _set_policy(db, value: str) -> None:
    # The real column names are option_key/option_value, and there is no
    # is_public column — a first guess at `key`/`value` reads as a store with no
    # settings at all rather than as a wrong column, so the probe is written
    # against the schema and checked against it above.
    await db.execute(
        text(
            "INSERT INTO site_options (id, option_key, option_value, autoload, "
            "created_at, updated_at) "
            "VALUES (:i, :k, :v, false, now(), now()) "
            "ON CONFLICT (option_key) DO UPDATE SET option_value = "
            "EXCLUDED.option_value, updated_at = now()"
        ),
        {"i": str(uuid.uuid4()), "k": PRIVACY_POLICY_OPTION, "v": value},
    )


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []
    original_policy = None

    try:
        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'cms_pages'"
                        )
                    )
                ).fetchall()
            }
            required = {"id", "title", "slug", "body_html", "status", "visibility"}
            missing = required - columns
            if missing:
                print("SKIP: cms_pages is missing %s." % ", ".join(sorted(missing)))
                return 0

            options_columns = {
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
            if not {"option_key", "option_value"} <= options_columns:
                print("SKIP: site_options has no option_key/option_value pair.")
                return 0

            original_policy = (
                await db.execute(
                    text("SELECT option_value FROM site_options WHERE option_key = :k"),
                    {"k": PRIVACY_POLICY_OPTION},
                )
            ).scalar()

            public_id, public_slug = await _make_page(
                db, status="PUBLISHED", visibility="PUBLIC"
            )
            draft_id, draft_slug = await _make_page(
                db, status="DRAFT", visibility="PUBLIC"
            )
            private_id, private_slug = await _make_page(
                db, status="PUBLISHED", visibility="PRIVATE"
            )
            created += [
                f"cms_pages:{public_id}",
                f"cms_pages:{draft_id}",
                f"cms_pages:{private_id}",
            ]
            await db.commit()

        # 1. A published, public page resolves.
        async with session() as db:
            await _set_policy(db, public_slug)
            await db.commit()
        async with session() as db:
            policy = await PrivacyPolicyService.get_policy(db)
        if not policy:
            failures.append(
                "a published, public policy page does not resolve, so the consent "
                "form would render no link on a store that has written one"
            )
        elif policy.get("slug") != public_slug:
            failures.append(
                "the resolved policy is %r, not the configured %r"
                % (policy.get("slug"), public_slug)
            )
        elif not (policy.get("url") or "").endswith(public_slug):
            failures.append(
                "the policy URL %r does not point at the page's slug" % policy.get("url")
            )
        elif not policy.get("title"):
            failures.append(
                "the policy has no title, so a form cannot label the link"
            )
        else:
            print("PASS: a published, public policy resolves (%s -> %s)"
                  % (policy["title"], policy["url"]))

        # 2. A draft is not policy.
        async with session() as db:
            await _set_policy(db, draft_slug)
            await db.commit()
        async with session() as db:
            draft_policy = await PrivacyPolicyService.get_policy(db)
        if draft_policy:
            failures.append(
                "a draft page resolves as the privacy policy -- nobody consented to "
                "a document they cannot read"
            )
        else:
            print("PASS: a draft page does not resolve")

        # 3. Published but private is also not linkable from a public form.
        async with session() as db:
            await _set_policy(db, private_slug)
            await db.commit()
        async with session() as db:
            private_policy = await PrivacyPolicyService.get_policy(db)
        if private_policy:
            failures.append(
                "a published-but-private page resolves as the privacy policy, so a "
                "public consent form would link a document the operator hid"
            )
        else:
            print("PASS: a private page does not resolve")

        # 4. Nothing configured at all.
        async with session() as db:
            await _set_policy(db, "")
            await db.commit()
        async with session() as db:
            unset = await PrivacyPolicyService.get_policy(db)
        if unset:
            failures.append(
                "an unset policy setting still resolves to %r" % unset.get("slug")
            )
        else:
            print("PASS: nothing configured resolves to nothing")

        # 5. The route, because a correct service behind a `/{key}` catch-all is
        #    a service no form can reach. FastAPI matches in declaration order,
        #    so this is the difference between the feature working and reading
        #    as "this store has no privacy policy".
        from app.main import app as fastapi_app

        paths = [
            r.path
            for r in fastapi_app.routes
            if "privacy-policy" in getattr(r, "path", "")
        ]
        if not paths:
            failures.append(
                "no /settings/public/privacy-policy route is registered, so no form "
                "can read the policy"
            )
        else:
            order = [
                r.path
                for r in fastapi_app.routes
                if getattr(r, "path", "").startswith("/api/v1/settings/")
            ]
            catch_all = [p for p in order if p == "/api/v1/settings/{key}"]
            # Every registration of the endpoint, not just the first. A duplicate
            # declaration is how the order changes without anyone moving a block:
            # FastAPI keeps the first match, so a correctly-placed copy alongside
            # a misplaced one still serves correctly — while the misplaced one is
            # dead code that a future edit will start depending on.
            late = [
                i for i, p in enumerate(order) if "privacy-policy" in p
            ]
            if catch_all:
                first_catch = order.index(catch_all[0])
                late = [i for i in late if i > first_catch]
            for i in late:
                failures.append(
                    "the privacy-policy route is declared after /{key} (position %d "
                    "of %d in the settings router), so FastAPI matches the catch-all "
                    "first and a caller reaching that position gets a 404 for a "
                    "setting named 'privacy-policy'"
                    % (i, len(order))
                )
            if not late:
                print("PASS: the route is registered ahead of the /{key} catch-all")
    finally:
        async with session() as db:
            await db.rollback()
            for item in created:
                kind, _, ident = item.partition(":")
                if kind == "cms_pages":
                    await db.execute(
                        text("DELETE FROM cms_pages WHERE id = :i"), {"i": ident}
                    )
            if original_policy is None:
                await db.execute(
                    text("DELETE FROM site_options WHERE option_key = :k"),
                    {"k": PRIVACY_POLICY_OPTION},
                )
            else:
                await db.execute(
                    text("UPDATE site_options SET option_value = :v WHERE option_key = :k"),
                    {"k": PRIVACY_POLICY_OPTION, "v": original_policy},
                )
            await db.commit()
        print("restored the policy setting")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: only a published, public policy page is linkable, and it is reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))