"""Guard: the sitemap advertises the archives the backend collects.

P0 "فید: پوشش نویسنده در سایت‌مپ". The sections were reachable but
unlinked, so a crawler had no way to find an author's posts or a date archive.

Each link is checked separately, because that is where this actually broke:
the section loop in `build_sitemap_payload` catches every exception and logs
it, so a collector that raises looks exactly like one that found nothing. The
live check proves the collectors run; this one proves they stay wired — to the
sections table, to the XML renderer, and to the sitemap the storefront serves.

    python scripts/wp-parity/check_sitemap_archives.py
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
SITEMAP_TS = ROOT / "frontend" / "app" / "sitemap.ts"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    failures: list[str] = []
    service = read(SERVICE)
    cms = read(CMS_SERVICE)
    schema = read(SCHEMA)
    sitemap = read(SITEMAP_TS)

    # 1. Both sections must be in the collection table. Scoped to the table
    #    itself: a name check over the whole module passed while the entry had
    #    been deleted, because the section name still appeared where the rows
    #    are read back out.
    #    Assembled with chr() rather than an escape: a "\n" written here becomes
    #    a real newline and leaves the pattern unterminated, which reads as a
    #    quoting mistake rather than a rule about the code.
    _bs = chr(92)
    table = re.search(
        r"_SECTIONS[^=]*=" + _bs + r"s*" + r"\((.*?)" + _bs + r"n\)",
        service,
        re.S,
    )
    if not table:
        failures.append("the sitemap sections table could not be read")
    else:
        for section in ("blog_authors", "blog_date_archives"):
            if f'"{section}"' not in table.group(1):
                failures.append(
                    "%s is not in the sitemap sections table, so nothing collects it"
                    % section
                )

    # 2. A collector must exist for each, not just a name.
    for collector in ("_collect_authors", "_collect_date_archives"):
        if f"def {collector}" not in service:
            failures.append(f"{collector} does not exist")

    # 3. The rows have to reach the XML, or a collector that works changes
    #    nothing a crawler reads.
    # Matched with surrounding whitespace allowed: the signature writes
    # "blog_authors: list[Any] | None = None", so a bare `f"{param}="` missed it
    # and reported a false failure on correct code.
    for param in ("blog_authors", "blog_date_archives"):
        if not re.search(rf"{param}\s*:", cms):
            failures.append(
                "render_sitemap_entries does not take %s, so the XML omits it" % param
            )
    for loop in ("for author in blog_authors or []:", "for archive in blog_date_archives or []:"):
        if loop not in cms:
            failures.append("the XML renderer never iterates %r" % loop)

    # 4. A loc-shaped row cannot be built if the schema demands a slug: the
    #    archive sections returned nothing at all until this was relaxed.
    row = re.search(r"class SitemapSectionRow\(BaseModel\):(.*?)\n\nclass ", schema, re.S)
    if not row:
        failures.append("SitemapSectionRow is missing from the schema")
    else:
        if "loc" not in row.group(1):
            failures.append(
                "SitemapSectionRow has no loc field, so an archive row (which is a "
                "path, not a slug) cannot be represented"
            )
        if re.search(r"^    slug:\s*str\s*$", row.group(1), re.M):
            failures.append(
                "SitemapSectionRow still requires a slug, so every archive row fails "
                "validation and the section is silently empty"
            )

    # 5. The storefront has to emit them.
    for name in ("blog_authors", "blog_date_archives"):
        if name not in sitemap:
            failures.append(
                "the Next.js sitemap does not read %s from the payload" % name
            )
    # Each route list has to be spread into the returned array. Building one and
    # not spreading it is exactly the shape this caught: the fetch happened, the
    # rows were mapped, and the result was never handed to a crawler.
    returned = re.search(r"return \[([^\]]*)\]", sitemap, re.S)
    body = returned.group(1) if returned else ""
    for routes in ("authorRoutes", "dateArchiveRoutes"):
        if routes not in body:
            failures.append(
                "the sitemap builds %s but never returns it, so the payload is "
                "fetched and dropped" % routes
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d link(s) of the archive chain are missing." % len(failures))
        return 1
    print("PASS: author and date archives are collected, rendered and emitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
