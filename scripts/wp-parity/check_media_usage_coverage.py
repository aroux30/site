"""Guard: the media-usage counter must cover every image column in the database.

A peer session measured the bug this exists to prevent: `product_images.url`
was absent from ``REFERENCE_COLUMNS``, so with 20 product rows pointing at the
database's only media asset, the delete warning said "used nowhere". For a
storefront that is the worst possible miss — the product image is the single
most-referenced file on the site.

Two lists in the same file drifted, and both were caught by a peer rather than
by a test, so they are checked against reality here:

  1. every image-ish text column in the live schema is either counted, or
     explicitly listed as deliberately excluded (revisions are counted but
     reported as non-blocking; a column that holds no file is excluded with a
     reason); and
  2. every integer field on ``MediaUsage`` has a Persian label, so ``total``
     and ``summary`` cannot disagree about which buckets exist.

    python scripts/wp-parity/check_media_usage_coverage.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.modules.media.application.usage_service import (  # noqa: E402
    BUCKET_LABELS,
    HTML_COLUMNS,
    REFERENCE_COLUMNS,
    MediaUsage,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Every text column of a table that stores uploads at all, not just columns
# whose name matches a pattern. The first version of this guard grepped column
# names like `%image%` and `%_url`, and `product_images.url` matched none of
# them — which is exactly how the column that held 20 product references got
# left out of the counter in the first place. Matching on the *table* is what
# catches it.
UPLOAD_TABLES = (
    "product_images",
    "blog_posts",
    "blog_post_revisions",
    "custom_post_entries",
    "categories",
    "brands",
    "vendors",
    "user_profiles",
    "seo_metadata",
    "attachments",
    "ticket_attachments",
    "card_transfer_receipts",
    "shipments",
    "media_assets",
    "cms_pages",
    "cms_page_revisions",
)

# Columns that match the pattern but hold no uploaded file, or that are counted
# without being a live use. Anything absent from REFERENCE_COLUMNS must appear
# here with a reason, so a new image column cannot be added unnoticed.
ALLOWED_UNCOUNTED: dict[tuple[str, str], str] = {
    ("media_assets", "file_url"): "the asset itself; this is the row being asked about",
    ("media_assets", "file_path"): "the asset's own disk path, not a reference to it",
    ("media_assets", "file_name"): "the asset's own name, not a reference to it",
    ("attachments", "file_url"): "a document attachment; counted via attachments.file_url",
    ("attachments", "file_name"): "the attachment's own name, not a reference to it",
    ("ticket_attachments", "file_url"): "a ticket attachment; counted via ticket_attachments.file_url",
    ("ticket_attachments", "file_name"): "the attachment's own name, not a reference to it",
    ("categories", "path"): "the category tree path (e.g. 'a/b/c'), not a file path",
    ("blog_comments", "author_url"): "a commenter's own website, not an upload",
    ("payments", "gateway_url"): "a callback URL, not an upload",
    ("seo_metadata", "canonical_url"): "a canonical link, not an upload",
    ("custom_post_types", "icon"): "an icon name, not an upload",
    ("lucky_wheel_prizes", "icon"): "an icon name, not an upload",
    ("site_menus", "icon"): "an icon name, not an upload",
}


def database_url() -> str:
    for line in open(os.path.join(ROOT, "backend", ".env"), encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in backend/.env")


def check_buckets_are_all_labelled() -> list[str]:
    problems: list[str] = []
    counts = {
        k
        for k, v in vars(MediaUsage()).items()
        if isinstance(v, int) and not isinstance(v, bool)
    }
    labelled = {attr for attr, _ in BUCKET_LABELS}
    for missing in sorted(counts - labelled):
        problems.append(
            "MediaUsage.%s has no entry in BUCKET_LABELS, so it is counted by "
            "`total` but never named in `summary()`" % missing
        )
    for extra in sorted(labelled - counts):
        problems.append(
            "BUCKET_LABELS names %s, which is not an integer field on MediaUsage" % extra
        )
    return problems


async def check_columns_against_schema() -> list[str]:
    problems: list[str] = []
    engine = create_async_engine(database_url())
    async with engine.connect() as c:
        # Every column of the upload tables that could hold a path, plus every
        # column in the whole schema whose name looks like a reference. The
        # first union catches a bare `url`; the second catches a brand-new
        # table nobody listed.
        rows = (
            await c.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND data_type IN ('character varying', 'text', 'character') "
                    "AND ("
                    "  (table_name = ANY(:tables) AND ("
                    "     column_name ILIKE '%url%' OR column_name ILIKE '%image%' "
                    "     OR column_name ILIKE '%img%' OR column_name ILIKE '%src%' "
                    "     OR column_name ILIKE '%photo%' OR column_name ILIKE '%file%' "
                    "     OR column_name ILIKE '%path%' OR column_name ILIKE '%avatar%'"
                    "     OR column_name ILIKE '%logo%' OR column_name ILIKE '%banner%'"
                    "     OR column_name ILIKE '%thumb%' OR column_name ILIKE '%cover%'"
                    "  ))"
                    "  OR column_name ILIKE ANY(:patterns)"
                    ") ORDER BY table_name, column_name"
                ),
                {
                    "tables": list(UPLOAD_TABLES),
                    "patterns": ["%image%", "%_url", "%avatar%", "%logo%", "%banner%"],
                },
            )
        ).fetchall()
    await engine.dispose()

    counted = set(REFERENCE_COLUMNS) | set(HTML_COLUMNS)
    for table, column in rows:
        key = (table, column)
        if key in counted:
            continue
        if key in ALLOWED_UNCOUNTED:
            continue
        problems.append(
            "%s.%s looks like a media reference but is in neither REFERENCE_COLUMNS "
            "nor HTML_COLUMNS, so deleting that file would not be warned about. Add it, "
            "or record it in ALLOWED_UNCOUNTED with a reason." % (table, column)
        )
    return problems


def main() -> int:
    problems = check_buckets_are_all_labelled()
    problems += asyncio.run(check_columns_against_schema())

    for p in problems:
        print("FAIL: %s" % p)
    if problems:
        print("")
        print("%d media column(s) the delete warning would miss." % len(problems))
        return 1
    print("PASS: every image column in the schema is counted, and every bucket is labelled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
