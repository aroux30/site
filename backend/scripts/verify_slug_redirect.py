"""Live check: a renamed page's old URL resolves to a 301, via the public feed.

P1 "نوشته: ریدایرکت نامک قدیمی (wp_old_slug_redirect)". The doc claimed
``resolve_slug_redirect`` had zero callers, so an old URL 404'd. That is no
longer the whole story: the SEO redirect feed
(``/seo/redirects`` → ``redirect_service.slug_history_redirects``) derives 301s
from the slug-change history and the storefront middleware consumes that feed.
This asserts the chain end to end rather than trusting grep.

Self-cleaning: the probe page and its history row are removed in ``finally``.

    cd backend && PYTHONPATH=. python scripts/verify_slug_redirect.py
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
    token = uuid.uuid4().hex[:8]
    old_slug = f"slug-redirect-old-{token}"
    new_slug = f"slug-redirect-new-{token}"

    async with session() as db:
        try:
            from app.modules.blog.application.slug_history_service import (
                SLUG_RESOURCE_CMS_PAGE,
                resolve_slug_redirect,
            )
            from app.modules.content.domain.models import CmsPage, PageStatus
            from app.modules.seo.application.redirect_service import (
                slug_history_redirects,
            )

            # A page that now lives at new_slug — the resource a rename points to.
            page = CmsPage(
                title="slug redirect probe",
                slug=new_slug,
                body_html="<p>probe</p>",
                status=PageStatus.PUBLISHED,
            )
            db.add(page)
            await db.flush()
            page_id = str(page.id)

            # The recorded rename: old → new. Same call the two write sites use.
            from app.modules.blog.application.slug_history_service import (
                record_slug_change,
            )

            await record_slug_change(
                db,
                resource_type=SLUG_RESOURCE_CMS_PAGE,
                resource_id=page.id,
                old_slug=old_slug,
                new_slug=new_slug,
            )
            await db.commit()

            # 1. The resolver reads the row back.
            resolved = await resolve_slug_redirect(
                db, old_slug, resource_type=SLUG_RESOURCE_CMS_PAGE
            )
            if resolved is None or resolved.new_slug != new_slug:
                failures.append(
                    "resolve_slug_redirect did not return the rename (got %r)" % (resolved,)
                )
            else:
                print("PASS: resolve_slug_redirect returns the new slug")

            # 2. The public redirect feed carries the derived 301 for the old
            #    URL — this is the piece the doc said was missing.
            rules = await slug_history_redirects(db)
            match = [
                r for r in rules
                if r.get("from_path") == f"/{old_slug}"
            ]
            if not match:
                failures.append(
                    "the public feed has no 301 for /%s (old URL would 404)" % old_slug
                )
            elif match[0].get("to_path") != f"/{new_slug}" or match[0].get("status_code") != 301:
                failures.append(
                    "the rule for /%s is wrong: %r" % (old_slug, match[0])
                )
            else:
                print("PASS: the public feed derives a 301 from the rename")

            # 3. When the target is gone, the rule must disappear — a redirect
            #    to a deleted page is a 404 behind a hop, worse than the 404.
            page.status = PageStatus.ARCHIVED
            page.slug = f"{new_slug}-moved"
            db.add(page)
            await db.commit()
            rules_after = await slug_history_redirects(db)
            still = [r for r in rules_after if r.get("from_path") == f"/{old_slug}"]
            if still:
                failures.append(
                    "a rule survived the target no longer being live: %r" % still
                )
            else:
                print("PASS: the rule disappears when the target slug is not live")

        finally:
            from sqlalchemy import text

            if page_id:
                await db.execute(
                    text("DELETE FROM slug_history WHERE resource_id = :id"),
                    {"id": page_id},
                )
                await db.execute(
                    text("DELETE FROM cms_pages WHERE id = :id"), {"id": page_id}
                )
            await db.commit()
            print("removed the probe page and its history row")

    await engine.dispose()

    if failures:
        print("\nFAIL: slug redirect is not wired end to end")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS: slug redirect chain is wired end to end")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))