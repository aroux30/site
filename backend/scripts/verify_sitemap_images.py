"""Live check: sitemap image entries and an honest lastmod.

P0 "فید: نگاشت تصاویر و lastmod دقیق در سایت‌مپ". Neither existed: the
sections carried slugs only, and a row with no timestamp was dated today, so a
crawler was told every page changed on every single crawl — a signal it learns
to discount, which weakens the entries that do carry a real date.

    cd backend && PYTHONPATH=. python scripts/verify_sitemap_images.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.content.application.cms_page_service import _sitemap_url  # noqa: E402
from app.modules.content.application.sitemap_service import (  # noqa: E402
    _collect_products,
)
from app.modules.content.schemas.content import SitemapSectionRow  # noqa: E402


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
        rows = await _collect_products(db)
        with_image = [r for r in rows if r.image_url]
        print(
            "collected %d product(s), %d with an image" % (len(rows), len(with_image))
        )
        if rows and not with_image:
            failures.append(
                "no product carried an image, so the join that reads "
                "product_images.is_primary is not working"
            )

        # The rendered XML has to carry the image element, not just the row:
        # a row field nobody renders is the same gap one layer up.
        if with_image:
            xml = _sitemap_url(
                "http://shop.example/products/x",
                with_image[0],
                changefreq="daily",
                priority="0.7",
            )
            if "image:image" not in xml or "image:loc" not in xml:
                failures.append(
                    "the rendered <url> has no image element: %s" % xml[:200]
                )
            elif with_image[0].image_url not in xml:
                failures.append(
                    "the image element does not carry the product's image URL"
                )
            else:
                print("PASS: the rendered XML carries an <image:image> entry")

        # No timestamp must mean no lastmod, not today's date.
        undated = _sitemap_url(
            "http://shop.example/products/x",
            SitemapSectionRow(slug="x"),
            changefreq="daily",
            priority="0.7",
        )
        if "<lastmod>" in undated:
            failures.append(
                "a row with no timestamp is dated anyway: %s" % undated[:200]
            )
        else:
            print("PASS: an undated row emits no <lastmod>")

        # A real timestamp must still be emitted, or the fix went too far.
        from datetime import datetime, timezone

        dated = _sitemap_url(
            "http://shop.example/products/x",
            SitemapSectionRow(slug="x", updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            changefreq="daily",
            priority="0.7",
        )
        if "<lastmod>2026-01-02</lastmod>" not in dated:
            failures.append("a real timestamp is not emitted: %s" % dated[:200])
        else:
            print("PASS: a dated row emits its own <lastmod>")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: images reach the sitemap XML and lastmod is never fabricated.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))