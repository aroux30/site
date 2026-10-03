"""Negative test for the content tools: sabotage both and require a failure.

  A. the converter is no longer idempotent — a second run double-tags, which
     is how a store ends up with every post carrying its category twice
  B. the purge ignores the age window, so a nightly job would delete what an
     admin trashed five minutes ago and is about to restore
  C. the purge reaches posts that are not trashed at all

    python scripts/wp-parity/negative_test_content_tools.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FIXTURE = os.path.join(ROOT, ".p1-tests", "tools_test.py")
BLOG = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "blog_service.py"
)
CONTENT = os.path.join(
    ROOT, "backend", "app", "modules", "content", "application", "cms_page_service.py"
)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def run_fixture() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, FIXTURE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    for path in (FIXTURE, BLOG, CONTENT):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    blog_orig, content_orig = read(BLOG), read(CONTENT)

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-700:])
        return 1

    failures: list[str] = []

    def sabotage(label: str, path: str, original: str, old: str, new: str) -> None:
        if old not in original:
            failures.append(f"{label}: the sabotage matched nothing — the code "
                            f"moved and this test is pointing at nothing")
            return
        patched = original.replace(old, new, 1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(patched)
        try:
            rc_s, _ = run_fixture()
        finally:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(original)
        if rc_s == 0:
            failures.append(f"{label}: the checks still passed")
        else:
            print(f"  {label}: caught (as it must be)")

    # A. the converter stops checking whether the link already exists
    sabotage(
        "A: the converter double-tags on a second run",
        BLOG,
        blog_orig,
        "            if already is None:\n"
        "                self.db.add(BlogPostTag(post_id=post.id, tag_id=tag.id))",
        "            self.db.add(BlogPostTag(post_id=post.id, tag_id=tag.id))"
        "  # sabotaged: no duplicate check",
    )

    # B. the post purge ignores the retention window
    sabotage(
        "B: the post purge ignores its age window",
        BLOG,
        blog_orig,
        "            stmt = stmt.where(BlogPost.deleted_at <= cutoff)",
        "            pass  # sabotaged: the age window is not applied",
    )

    # C. the page purge stops filtering to the trash
    sabotage(
        "C: the page purge reaches live pages",
        CONTENT,
        content_orig,
        "    stmt = select(CmsPage).where(CmsPage.deleted_at.is_not(None))",
        "    stmt = select(CmsPage)  # sabotaged: no trash filter",
    )

    rc_final, out_final = run_fixture()
    if rc_final != 0:
        print("FAIL: the fixture does not pass again after restoring the files — "
              "this test left the repository modified.")
        print(out_final.strip()[-700:])
        return 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("\nPASS: all three sabotages were caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())