"""Negative test for check_server_pagination.py — prove the guard can actually fail.

Per the project's own rule: a gate that cannot fail is not a gate. This walks the
three ways an admin list can hide rows behind its own pager, asserts the guard
reports each one, then restores the file and asserts a clean pass.

It is here because two earlier drafts of the guard passed while the original bug
was live: one grepped for `page` anywhere in the file, which the page-number
state alone satisfied; another skipped any page mentioning `serverTotal` before
testing the cap. Each failure mode below exists because it fooled the guard.

Deliberately mutates real files, so it snapshots and restores each one and
refuses to continue if a file changed underneath it. Run:
    python scripts/wp-parity/negative_test_server_pagination.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_server_pagination.py"
BLOG_PAGE = ROOT / "frontend" / "app" / "admin" / "blog" / "page.tsx"
DATA_TABLE = ROOT / "frontend" / "components" / "admin" / "data-table.tsx"


def run_guard() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)], capture_output=True, text=True, timeout=120
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    original_blog = BLOG_PAGE.read_text(encoding="utf-8")
    original_table = DATA_TABLE.read_text(encoding="utf-8")

    def restore() -> None:
        BLOG_PAGE.write_text(original_blog, encoding="utf-8")
        DATA_TABLE.write_text(original_table, encoding="utf-8")

    # mode: (name, file, old snippet that must be present, replacement)
    modes = [
        (
            "fixed page_size with no `page` sent",
            BLOG_PAGE,
            "        page,\n        page_size: PAGE_SIZE,",
            "        page_size: 50,",
        ),
        (
            "both tables lose serverTotal",
            BLOG_PAGE,
            "            serverTotal={postsTotal}\n            onServerPageChange={(p) => setPage(p)}\n",
            "",
        ),
        (
            "only one of two tables keeps serverTotal",
            BLOG_PAGE,
            "            serverTotal={postsTotal}\n            onServerPageChange={(p) => setPage(p)}\n            columnVisibilityKey=\"admin.blog.columns\"\n          />\n        </TabsContent>\n      </Tabs>",
            "            onServerPageChange={(p) => setPage(p)}\n            columnVisibilityKey=\"admin.blog.columns\"\n          />\n        </TabsContent>\n      </Tabs>",
        ),
        (
            "serverTotal declared but not destructured",
            DATA_TABLE,
            "  pageSize,\n  serverTotal,\n  onServerPageChange,",
            "  pageSize,\n  onServerPageChange,",
        ),
        # The blind spot this whole exercise was about. `page` IS sent, so the
        # "is a page being sent" question is satisfied; `page_size` is capped,
        # so that rule is satisfied too. Every check that asks whether a page
        # travels passes, and the pager still never moves — every click asks
        # for the same slice. Without this case here, deleting PAGE_PINNED from
        # the guard leaves this file green, which is the regression that would
        # undo the fix.
        (
            "page pinned to a literal, so the pager never varies",
            BLOG_PAGE,
            "        page,\n        page_size: PAGE_SIZE,",
            "        page: 1,\n        page_size: PAGE_SIZE,",
        ),
    ]

    try:
        code, out = run_guard()
        if code != 0:
            print("FAIL: the guard does not pass on the current tree, so a red result "
                  "below would prove nothing.\n%s" % out)
            return 2
        print("[0/5] guard passes on the current tree")

        for i, (name, path, old, new) in enumerate(modes, start=1):
            src = path.read_text(encoding="utf-8")
            if old not in src:
                print("FAIL: cannot inject %r — the snippet moved. Update this test." % name)
                restore()
                return 2
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            try:
                code, out = run_guard()
            finally:
                path.write_text(src, encoding="utf-8")

            if code == 0:
                print("FAIL: guard passed while %s — it cannot see this failure mode." % name)
                print(out)
                return 1
            print("[%d/5] correctly fails on: %s" % (i, name))

        code, out = run_guard()
        if code != 0:
            print("FAIL: guard still red after every file was restored.\n%s" % out)
            return 1
        print("[5/5] guard is green again after restore")
    finally:
        restore()

    print("")
    print("PASS: the pagination guard fails on all five ways to hide rows, "
          "including a `page` key that is present but pinned to a literal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
