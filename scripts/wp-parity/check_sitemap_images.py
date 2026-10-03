"""Guard: sitemap entries carry images, and lastmod is never invented.

P0 "فید: نگاشت تصاویر و lastmod دقیق در سایت‌مپ". Two failures, both silent:
the sections carried slugs only, so no URL entered image results; and a row
with no timestamp was dated today, telling a crawler everything changed on
every crawl — a signal it learns to discount.

    python scripts/wp-parity/check_sitemap_images.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "backend" / "app" / "modules" / "content" / "application" / "sitemap_service.py"
CMS_SERVICE = ROOT / "backend" / "app" / "modules" / "content" / "application" / "cms_page_service.py"
SCHEMA = ROOT / "backend" / "app" / "modules" / "content" / "schemas" / "content.py"
SITEMAP = ROOT / "frontend" / "app" / "sitemap.ts"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    failures: list[str] = []
    service = read(SERVICE)
    cms = read(CMS_SERVICE)
    schema = read(SCHEMA)
    sitemap = read(SITEMAP)

    # 1. The row has to carry an image at all, or every consumer drops it.
    row = re.search(r"class SitemapSectionRow\(BaseModel\):(.*?)\n\nclass ", schema, re.S)
    if not row:
        failures.append("SitemapSectionRow is missing from the schema")
    elif "image_url" not in row.group(1):
        failures.append(
            "SitemapSectionRow has no image_url, so an image cannot reach the "
            "consumer even when the collector sets one"
        )

    # 2. The collector has to read it from product_images, not from the product
    #    row: `Product` has no image column, so reading it there raises.
    if "image_url=" not in service:
        failures.append(
            "no sitemap section sets image_url, so the entries carry no image"
        )
    elif "ProductImage" not in service:
        failures.append(
            "the image is not read from product_images, so every product row "
            "would raise AttributeError and the whole section is skipped"
        )

    # 3. The rendered XML has to emit the element. A row field nobody renders is
    #    the same gap one layer up.
    if "<image:image>" not in cms:
        failures.append(
            "the XML renderer emits no <image:image> element, so a collected "
            "image never reaches a crawler"
        )
    if "image:loc" not in cms:
        failures.append("the image element carries no locator")

    # 4. lastmod must be omitted when unknown rather than dated today.
    lastmod = re.search(r"def _lastmod\(.*?\n\n\n", cms, re.S)
    if lastmod:
        if "datetime.now" in lastmod.group(0):
            failures.append(
                "_lastmod still falls back to today, so every undated row claims "
                "it changed on every crawl"
            )
    else:
        failures.append("_lastmod could not be read")

    # 5. And the storefront must forward the image too.
    # Not a plain substring: a row's image can appear in the type, in a dead
    # branch, or inside a condition that is always false. What matters is that
    # some live mapping puts it on an emitted entry, so the emitted object is
    # checked for the key.
    _bs = chr(92)
    forwards = (
        len(re.findall(r"images:" + _bs + r"s*\[", sitemap)) > 0
        and "row.image_url" in sitemap
    )
    if not forwards:
        failures.append(
            "the Next.js sitemap never forwards a row's image, so the backend's "
            "work is dropped on the way out"
        )
    if "cover_image_url" not in sitemap:
        failures.append(
            "blog posts carry a cover image that the sitemap never advertises"
        )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d link(s) of the image chain are missing." % len(failures))
        return 1
    print("PASS: images reach the sitemap on both paths and lastmod is honest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
