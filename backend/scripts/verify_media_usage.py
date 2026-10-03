"""Live check: the media-usage counter sees real references.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "مدیا: هشدار استفاده پیش
از حذف". Deleting an asset removed the row and the bytes with nothing warning
that the image was a cover of a published post or a vendor's logo.

This runs against the live database and asserts the counter is not vacuously
zero — the failure mode a usage counter ships with. Specifically it:
  1. finds an asset whose name really is referenced, and asserts the count is
     non-zero;
  2. asserts an arbitrary name nobody uses counts zero;
  3. inserts a throwaway reference, asserts the count moves by exactly the
     amount it inserted, then removes it.

Point 3 is the one that matters: a counter that always returns zero would pass
1 and 2 as well if 1 were written carelessly.

    cd backend && PYTHONPATH=. python scripts/verify_media_usage.py
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

from app.modules.media.application.usage_service import count_media_usage  # noqa: E402


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    scratch_id: str | None = None

    async with session() as db:
        # 1. A name that is genuinely referenced somewhere. Prefers a product
        #    image over a post cover: on this database the only asset in use is
        #    referenced by 20 product rows and no post has a cover, so testing
        #    only the post cover made the whole point skip — which is how
        #    product_images.url went missing from the counter unnoticed.
        referenced = None
        source = None
        hit = (
            await db.execute(
                text(
                    "SELECT split_part(url, '/', -1) FROM product_images "
                    "WHERE url IS NOT NULL AND url <> '' LIMIT 1"
                )
            )
        ).scalar()
        if hit:
            referenced, source = hit, "product_images.url"
        else:
            hit = (
                await db.execute(
                    text(
                        "SELECT split_part(cover_image_url, '/', -1) FROM blog_posts "
                        "WHERE cover_image_url IS NOT NULL AND cover_image_url <> '' LIMIT 1"
                    )
                )
            ).scalar()
            if hit:
                referenced, source = hit, "blog_posts.cover_image_url"

        if referenced:
            usage = await count_media_usage(db, referenced)
            if usage.total < 1:
                failures.append(
                    "%s holds %r but the counter reports nothing in use"
                    % (source, referenced)
                )
            else:
                print(
                    "PASS: %r is in use via %s — %s (total %d)"
                    % (referenced, source, usage.summary(), usage.total)
                )
        else:
            failures.append(
                "no product image and no post cover references anything, so the "
                "counter cannot be shown to see a real use; this must not silently skip"
            )

        # 2. A name nothing uses must count zero — otherwise every delete warns.
        usage_zero = await count_media_usage(db, "definitely-not-a-real-file-9f2a.png")
        if usage_zero.total != 0:
            failures.append(
                "an unused file name reported %d use(s): %s"
                % (usage_zero.total, usage_zero.summary())
            )
        else:
            print("PASS: a file name nobody uses counts zero")

        # 3. The counter must move when a reference appears.
        name = "usage-probe-%s.png" % uuid.uuid4().hex[:8]
        probe_url = "/uploads/%s" % name
        before = await count_media_usage(db, name)

        scratch_id = str(uuid.uuid4())
        await db.execute(
            text(
                # depth/path/position/is_active are NOT NULL without a default, so a
                # partial INSERT aborts the transaction and every later
                # statement in this session fails with
                # InFailedSQLTransactionError — which hides the real cause.
                "INSERT INTO categories "
                "(id, name, slug, path, depth, position, is_active, created_at, updated_at, image_url) "
                "VALUES (:id, :name, :slug, :slug, 0, 0, true, now(), now(), :url)"
            ),
            {
                "id": scratch_id,
                "name": "usage probe",
                "slug": "usage-probe-%s" % name,
                "url": probe_url,
            },
        )
        await db.commit()

        after = await count_media_usage(db, name)
        if after.categories != before.categories + 1:
            failures.append(
                "inserting one category reference moved the category count from %d "
                "to %d, expected exactly +1" % (before.categories, after.categories)
            )
        else:
            print(
                "PASS: one inserted reference moved the count from %d to %d"
                % (before.categories, after.categories)
            )

        await db.execute(text("DELETE FROM categories WHERE id = :id"), {"id": scratch_id})
        await db.commit()
        scratch_id = None

        restored = await count_media_usage(db, name)
        if restored.categories != before.categories:
            failures.append(
                "after removing the probe the count is %d, expected %d"
                % (restored.categories, before.categories)
            )
        else:
            print("PASS: removing the probe restored the count")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the media-usage counter sees real references and ignores absent ones.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))