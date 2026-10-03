"""Negative test for check_comment_resource_addressing.py — prove it can fail.

A peer session caught this exact class of bug after it had been "done": the
storefront was fixed and the admin tab was not, and the nullable `post_id` that
would have caught it was typed `string`. So the guard is exercised against all
three ways this can regress.

    python scripts/wp-parity/negative_test_comment_resource_addressing.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_comment_resource_addressing.py"
BLOG_API = ROOT / "frontend" / "lib" / "api" / "blog.ts"
ADMIN_TAB = ROOT / "frontend" / "components" / "admin" / "blog" / "comments-moderation-tab.tsx"

MODES = [
    (
        "post_id typed as a non-nullable string again",
        BLOG_API,
        "  post_id: string | null;",
        "  post_id: string;",
    ),
    (
        "an admin call site posts by post_id",
        ADMIN_TAB,
        "await submitResourceComment(target.resourceType, target.resourceId, {",
        "await submitPostComment(replyTarget.post_id, {",
    ),
    (
        "resource_type dropped from the comment type",
        BLOG_API,
        '  resource_type: "blog_post" | "cms_page";',
        "",
    ),
]


def run_guard() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)], capture_output=True, text=True, timeout=120
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8") for p in (BLOG_API, ADMIN_TAB)}

    def restore() -> None:
        for p, s in originals.items():
            p.write_text(s, encoding="utf-8")

    try:
        code, out = run_guard()
        if code != 0:
            print("FAIL: the guard is already red on the current tree, so a red "
                  "result below would prove nothing.\n%s" % out)
            return 2
        print("[0/%d] guard passes on the current tree" % (len(MODES) + 1))

        for i, (name, path, old, new) in enumerate(MODES, start=1):
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
                print("FAIL: guard passed while %s." % name)
                print(out)
                return 1
            print("[%d/%d] correctly fails on: %s" % (i, len(MODES) + 1, name))

        code, out = run_guard()
        if code != 0:
            print("FAIL: guard still red after restore.\n%s" % out)
            return 1
        print("[%d/%d] guard is green again after restore" % (len(MODES) + 1, len(MODES) + 1))
    finally:
        restore()

    print("")
    print("PASS: the comment-addressing guard fails on all three regressions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
