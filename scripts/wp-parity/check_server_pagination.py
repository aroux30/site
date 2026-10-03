"""Guard: an admin list must not page over a fixed client-side slice.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "نوشته: صفحه‌بندی فهرست
نوشته‌های ادمین". The page fetched a hard-coded ``page_size: 50`` and gave the
table that one slice, so the pager stepped through 50 rows while posts 51+
were unreachable — an admin with 300 posts could only ever see the first 50.

The rule: if a page hands DataTable a ``pageSize`` and does *not* hand it a
``serverTotal``, then the pager is counting only the rows already in hand, so
the fetch must be unbounded or complete. A capped ``page_size`` in that state
is the bug. Two versions of this guard missed it — one grepped for ``page``
anywhere in the file, which the page-number state alone satisfied; another
skipped pages that mentioned ``serverTotal`` before testing the cap. So the
checks below are deliberately independent, and each one is exercised against
this bug by negative_test_server_pagination.py.

    python scripts/wp-parity/check_server_pagination.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "frontend" / "app" / "admin"
DATA_TABLE = ROOT / "frontend" / "components" / "admin" / "data-table.tsx"

# fetch calls whose first argument object carries the query params
FETCH_CALL = re.compile(r"\b\w*[Aa]pi\.\w+\(\{(.*?)\}\)", re.S)
PAGE_SIZED = re.compile(r"(?<![\w.])page_size\s*:\s*(\w+)")
PAGE_SENT = re.compile(r"(?<![\w.])page\s*[,:]")
#: A *varying* page value. `page: page` (the state variable) passes; `page: 1`
#: and `page: 3` do not — a literal is the same request on every click, so the
#: pager steps and the table keeps showing the first slice. Asking only "does
#: the fetch send a page" let that through, which is the same class of blind
#: spot as the two earlier versions of this guard.
PAGE_PINNED = re.compile(r"(?<![\w.])page\s*:\s*\d+")


def main() -> int:
    failures: list[str] = []

    table_src = DATA_TABLE.read_text(encoding="utf-8")
    for token in ("serverTotal", "onServerPageChange"):
        if token not in table_src:
            failures.append(
                "data-table.tsx no longer supports %s, so a server-paginated "
                "admin list has no way to render a pager" % token
            )
    # The prop has to be destructured, not merely mentioned in a doc comment:
    # dropping it from the parameter list leaves `serverTotal` referenced in the
    # body as an undefined name, which TypeScript catches but a grep does not.
    destructured = re.search(r"export function DataTable<T>\(\{(.*?)\}\)", table_src, re.S)
    if not destructured or "serverTotal" not in destructured.group(1):
        failures.append(
            "data-table.tsx declares serverTotal but does not destructure it, so the "
            "prop is never bound and every server-paginated list reads an undefined total"
        )

    for path in sorted(ADMIN.rglob("page.tsx")):
        src = path.read_text(encoding="utf-8")
        if "pageSize={" not in src:
            continue  # renders no pager, so it cannot hide rows behind one

        rel = path.relative_to(ROOT).as_posix()

        # 1. Every DataTable that gets a pageSize must also get a serverTotal,
        #    otherwise its pager counts only the rows in hand. This is counted
        #    per table, not per file: a page with two tables, one of them
        #    missing the total, still hides rows — a whole-file check would
        #    pass on the strength of the other table.
        pagers = src.count("pageSize={")
        totals = src.count("serverTotal=")
        if totals < pagers:
            failures.append(
                "%s renders %d pager(s) but passes serverTotal %d time(s), so %d "
                "pager(s) count only the rows they were handed"
                % (rel, pagers, totals, pagers - totals)
            )
            continue

        # 2. In server mode every fetch must send a page, or the pager
        #    navigates while the request keeps returning the same first page.
        blocks = FETCH_CALL.findall(src)
        if not blocks:
            failures.append(
                "%s paginates in server mode but no fetch call with an inline "
                "params object was found to verify" % rel
            )
            continue
        # `break` is not used: a page with three fetches would be checked once
        # and the two remaining fetches skipped, so pinning the page in the
        # *last* of them passed. Every block is checked, and the reasons are
        # collected so one run names all of them.
        for block in blocks:
            if PAGE_SIZED.search(block) and not PAGE_SENT.search(block):
                failures.append(
                    "%s caps a fetch with page_size but never sends `page`, so "
                    "paging navigates over one fixed slice" % rel
                )
            elif PAGE_PINNED.search(block):
                failures.append(
                    "%s sends a literal `page` (e.g. page: 1) instead of the "
                    "pager's value, so every click asks for the same slice and "
                    "the table never changes" % rel
                )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d problem(s). No admin list may hide rows behind its own pager." % len(failures))
        return 1

    print("PASS: every admin pager is told the real total, and every capped fetch sends a page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
