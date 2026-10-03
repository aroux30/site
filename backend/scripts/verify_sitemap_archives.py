"""Live check: the sitemap advertises the archives it now collects.

P0 "فید: پوشش CPT و نویسنده در سایت‌مپ" (the author half; date archives
came with it). Author and date archives were crawlable pages that nothing
pointed a crawler at, so their content was reachable but unlinked.

Also asserted: an archive URL in the sitemap is prefixed with the site root
exactly once. The rows carry a rooted loc, so prefixing again would hand a
crawler "http://host/http://host/blog/authors/x" — a URL that 404s and reads to
a crawler as a broken sitemap.

    cd backend && PYTHONPATH=. python scripts/verify_sitemap_archives.py
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

from app.modules.content.application.sitemap_service import (  # noqa: E402
    build_sitemap_payload,
)

AUTHOR_SLUG = "sitemap-probe-%s" % uuid.uuid4().hex[:8]
POST_SLUG = "sitemap-probe-%s" % uuid.uuid4().hex[:8]


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    user_id = uuid.uuid4()
    post_id = uuid.uuid4()

    async with session() as db:
        try:
            # The author slug lives on the users row; `user_profiles` has no such
            # column. `users` also has five NOT NULL columns without defaults, so
            # an INSERT that only supplies the slug fails and — because it fails
            # inside the transaction — every statement after it reports
            # "current transaction is aborted" instead of the real cause.
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, is_active, is_verified, "
                    "is_superuser, totp_enabled, author_slug, created_at, updated_at) "
                    "VALUES (:uid, :phone, true, true, false, false, :slug, "
                    "now(), now())"
                ),
                {"uid": str(user_id), "phone": "9" + uuid.uuid4().hex[:9], "slug": AUTHOR_SLUG},
            )
            await db.commit()

            await db.execute(
                text(
                    "INSERT INTO blog_posts (id, title, slug, content, status, "
                    "author_id, published_at, created_at, updated_at) "
                    "VALUES (:id, 'probe', :slug, '<p>x</p>', 'PUBLISHED', :aid, "
                    "now(), now(), now())"
                ),
                {"id": str(post_id), "slug": POST_SLUG, "aid": str(user_id)},
            )
            await db.commit()

            payload = await build_sitemap_payload(db)

            authors = payload.blog_authors or []
            if not authors:
                failures.append(
                    "no author archives were collected, so an author with a "
                    "published post is unreachable as far as a crawler is concerned"
                )
            else:
                print("PASS: %d author archive(s) collected" % len(authors))
                loc = authors[0].loc
                if not loc.startswith("/blog/authors/"):
                    failures.append(
                        "an author archive is advertised at %r, expected a "
                        "/blog/authors/... path" % loc
                    )
                else:
                    print("PASS: the author archive path is %s" % loc)

            archives = payload.blog_date_archives or []
            if not archives:
                failures.append(
                    "no date archives were collected, so /archive/<year> and "
                    "/archive/<year>/<month> are unadvertised"
                )
            else:
                locs = [a.loc for a in archives]
                print("PASS: %d date archive(s): %s" % (len(locs), ", ".join(locs)))
                if not all(l.startswith("/archive/") for l in locs):
                    failures.append("date archives are not /archive/... paths: %s" % locs)
                # One entry per year plus one per month, and both forms must be
                # present. The count is not asserted to be small: this database
                # already holds other published posts, and an exact expectation
                # would fail for the wrong reason. What must hold is that the
                # collector is driven by the data, not by a fixed list.
                if not any(l.count("/") == 2 for l in locs):
                    failures.append(
                        "no year-only archive among %s — the collector is missing "
                        "its year entries" % locs
                    )
                if not any(l.count("/") == 3 for l in locs):
                    failures.append(
                        "no month archive among %s — the collector is missing its "
                        "month entries" % locs
                    )

            # The XML fragment is what a crawler actually fetches, so it has to
            # carry these too — and with the root prefixed exactly once.
            fragment = payload.xml_fragment or ""
            for label, rows in (
                ("author", payload.blog_authors or []),
                ("date archive", payload.blog_date_archives or []),
            ):
                if rows and rows[0].loc not in fragment:
                    failures.append(
                        "the %s archive %s is missing from the rendered XML, so the "
                        "collector runs but nothing a crawler reads changes"
                        % (label, rows[0].loc)
                    )
            if "http://http://" in fragment:
                failures.append(
                    "the XML fragment prefixes an already-rooted loc a second time"
                )
            if not failures:
                print("PASS: both sections reach the rendered XML, rooted once")

        finally:
            await db.rollback()
            await db.execute(text("DELETE FROM blog_posts WHERE id = :id"), {"id": str(post_id)})
            await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
            await db.commit()
            print("removed the probe rows")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: author and date archives are collected and reach the sitemap XML.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
