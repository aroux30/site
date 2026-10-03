"""Live check: the static front page can be set, and a stale slug degrades.

P0 "تنظیمات: انتخاب صفحهٔ نخست (show_on_front/page_on_front)". The resolver on
the backend was complete — it even degrades to the default home when the chosen
page is gone — but no screen could set the two keys, so the storefront's
front-page branch was unreachable.

Asserted here: the write path, the resolver reading it, and the degradation,
which is the part that silently breaks a storefront when a page is deleted.

    cd backend && PYTHONPATH=. python scripts/verify_front_page.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
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

PAGE_SLUG = "front-probe-%s" % uuid.uuid4().hex[:8]


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    page_id: str | None = None

    async with session() as db:
        originals = {
            k: await SiteOptionsService.get(db, k)
            for k in ("show_on_front", "page_on_front")
        }
        try:
            from app.modules.content.domain.models import CmsPage, PageStatus

            # A published page, so the resolver's own lookup succeeds.
            page = CmsPage(
                title="front page probe",
                slug=PAGE_SLUG,
                body_html="<p>probe</p>",
                status=PageStatus.PUBLISHED,
            )
            db.add(page)
            await db.flush()
            page_id = str(page.id)
            await db.commit()

            from app.modules.settings.api.routes import get_public_front_page

            # 1. The default: no page pinned.
            await SiteOptionsService.set(db, "show_on_front", "posts")
            await SiteOptionsService.set(db, "page_on_front", "")
            await db.commit()
            default = await get_public_front_page(db)
            if default["slug"] is not None:
                failures.append(
                    "with no page pinned the resolver returns %r, expected None"
                    % default["slug"]
                )
            else:
                print("PASS: unpinned resolves to the default home")

            # 2. Pinned: the page is served at "/".
            await SiteOptionsService.set(db, "show_on_front", "page")
            await SiteOptionsService.set(db, "page_on_front", PAGE_SLUG)
            await db.commit()
            pinned = await get_public_front_page(db)
            if pinned["slug"] != PAGE_SLUG:
                failures.append(
                    "the pinned page resolves to %r, expected %r"
                    % (pinned["slug"], PAGE_SLUG)
                )
            else:
                print("PASS: a pinned published page resolves")

            # 3. A slug that does not exist must degrade, never 404 the store.
            await SiteOptionsService.set(db, "page_on_front", "no-such-page-xyz")
            await db.commit()
            missing = await get_public_front_page(db)
            if missing["slug"] is not None:
                failures.append(
                    "a stale slug still resolves to %r — the storefront would serve "
                    "a page that is gone" % missing["slug"]
                )
            else:
                print("PASS: a stale slug degrades to the default home")

            # 4. An unpublished page is the same case: the resolver asks for
            #    only_published, so a draft cannot be pinned.
            await SiteOptionsService.set(db, "page_on_front", PAGE_SLUG)
            page.status = PageStatus.DRAFT
            await db.commit()
            draft = await get_public_front_page(db)
            if draft["slug"] is not None:
                failures.append(
                    "an unpublished page still resolves to %r" % draft["slug"]
                )
            else:
                print("PASS: an unpublished page is not served at the front")

        finally:
            for key, value in originals.items():
                await SiteOptionsService.set(db, key, value)
            if page_id:
                from sqlalchemy import text

                await db.execute(
                    text("DELETE FROM cms_pages WHERE id = :id"), {"id": page_id}
                )
            await db.commit()
            print("restored the settings and removed the probe page")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the front page can be pinned, and a stale pin degrades safely.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))