#!/usr/bin/env python3
"""Fail when stored HTML is not what the sanitizer would produce.

The editor allowlist gate (`check_editor_allowlists.py`) proves the two
allowlists agree. It cannot prove anything about the rows already in the
database, and those rows are the thing that actually renders.

``sanitize_html`` runs on create and on update, so anything written through the
API is clean by construction. That leaves three ways a dirty value gets in, and
all three are silent:

* a content import (WXR/JSON, blog transfer, the data-exchange module) that
  writes the column directly,
* a migration or a data fix that runs UPDATE,
* a row that predates the sanitizer shipping at all.

The consequence is not cosmetic: the sanitizer strips ``<script>``,
``<iframe>`` from an unknown host, ``on*`` attributes and ``style`` values the
CSS allowlist rejects. A row holding any of those renders it.

Run:  python scripts/wp-parity/check_stored_html.py [--limit N]

Exit 1 on any row that sanitize_html would change, printing the column, the id
and the first offending fragment so the row can be fixed by id.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

#: (table, column, label, mode). One row per HTML-bearing content column.
#:
#: ``mode`` is what the column actually holds, and the two are not the same
#: thing:
#:
#: * ``"html"`` — the value is markup. An unescaped ``&`` is a real difference.
#: * ``"text"`` — the value is prose that a renderer escapes: React renders
#:   ``{comment.content}`` as text, and the feed runs it through
#:   ``_escape_xml``. Re-running the HTML sanitizer over it would flag every
#:   comment containing an ampersand, a quote or an angle bracket, and the gate
#:   would report the whole comment table forever. The check that matters for a
#:   text column is the opposite direction: does it contain anything that only
#:   makes sense as markup?
TARGETS: list[tuple[str, str, str, str]] = [
    ("blog_posts", "content", "blog post body", "html"),
    ("cms_pages", "body_html", "CMS page body", "html"),
    ("blog_comments", "content", "comment", "text"),
]

#: A tag that means a value was authored as markup rather than prose. Prose can
#: contain a lone ``<`` or a comparison, but not a closing tag.
_TAG_RE = re.compile(r"</?[a-z][a-z0-9-]*(?:\s[^<>]*)?/?>", re.IGNORECASE)


def _diff_summary(before: str, after: str) -> str:
    """The first place the two strings diverge, for a report line."""
    limit = min(len(before), len(after))
    i = 0
    while i < limit and before[i] == after[i]:
        i += 1
    start = max(0, i - 30)
    return f"...{after[start:i + 90]!r}"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="stop after this many offending rows (0 = no limit)",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine-readable output for CI"
    )
    args = parser.parse_args()

    # Imported here so a missing backend simply fails with a clear error rather
    # than a traceback from a path mistake.
    from sqlalchemy import select, text

    from app.core.database.session import async_session_factory
    from app.shared.content.html_sanitizer import sanitize_html

    offenders: list[dict[str, str]] = []
    checked = 0

    async with async_session_factory() as db:
        for table, column, label, mode in TARGETS:
            rows = (
                await db.execute(
                    text(f"SELECT id, {column} AS body FROM {table} "  # noqa: S608 - fixed table names above
                         "WHERE " + column + " IS NOT NULL AND " + column + " <> ''")
                )
            ).all()
            for row_id, body in rows:
                checked += 1
                if not isinstance(body, str):
                    continue
                if mode == "text":
                    # See TARGETS: a text column is escaped by its renderers, so
                    # the finding is embedded markup, not an unescaped ampersand.
                    if not _TAG_RE.search(body):
                        continue
                    cleaned = sanitize_html(body)
                else:
                    cleaned = sanitize_html(body)
                if cleaned == body:
                    continue
                offenders.append(
                    {
                        "table": table,
                        "label": label,
                        "mode": mode,
                        "id": str(row_id),
                        "fragment": _diff_summary(body, cleaned),
                    }
                )
                if args.limit and len(offenders) >= args.limit:
                    break
            if args.limit and len(offenders) >= args.limit:
                break

    if args.json:
        print(json.dumps({"checked": checked, "offenders": offenders}, indent=2))
        return 1 if offenders else 0

    print(f"checked {checked} rows across {len(TARGETS)} columns")
    if not offenders:
        print("\nPASS: every stored body is already what the sanitizer produces.")
        return 0

    print(f"\nFAIL: {len(offenders)} stored row(s) hold markup the sanitizer would strip.")
    print("These render unsanitized until they are rewritten. Fix by id:")
    for item in offenders[:20]:
        print(f"  {item['table']}.{item['id']}  ({item['label']})")
        print(f"      {item['fragment']}")
    if len(offenders) > 20:
        print(f"  ... and {len(offenders) - 20} more")
    print(
        "\nTo repair, re-run the value through the sanitizer rather than deleting "
        "it:\n"
        "  UPDATE blog_posts SET content = <sanitize_html(content)> WHERE id = ..."
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))