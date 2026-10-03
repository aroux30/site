"""Negative test for check_admin_search_deeplink_wired.

The handoff was two files that read `?search=`, and the reason the feature
still would not have worked is the half nobody was looking at: the search did
not match the slug. So the sabotages are the three links of that chain, one of
which is the one that actually shipped broken.

  A. Drop `?search=` from one admin page. The other still reads it, so a check
     that asks "do the admin pages read it" once passes.
  B. Drop the slug from the blog search. Every front-end check passes, the
     endpoint still filters, and the contextual link lands on an empty list.
  C. Give the effect a dependency list. It re-seeds on every render and
     overwrites what the operator is typing — the link now "works" by making
     the search box unusable.

Run:  python scripts/wp-parity/negative_test_admin_search_deeplink_wired.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_admin_search_deeplink_wired.py")
BLOG_BAR = os.path.join(ROOT, "frontend", "components", "layout", "admin-bar.tsx")
BAR = os.path.join(ROOT, "frontend", "components", "layout", "admin-bar.tsx")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "blog", "page.tsx")
PAGES_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")
BLOG_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "blog",
                           "application", "blog_service.py")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(label: str, path: str, fn) -> bool:
    with open(path, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)

    try:
        changed = fn(original)
    except AssertionError as exc:
        print(f"FAIL: {label} — {exc}")
        return False
    if changed == original:
        print(f"FAIL: {label} — nothing changed.")
        return False

    write(changed)
    try:
        rc, out = run_gate()
    finally:
        write(original)

    rc_after, _ = run_gate()
    if rc_after != 0:
        print(f"FAIL: {label} — the gate did not pass again after restoring.")
        return False
    if rc == 0:
        print(f"FAIL: {label} still passed. The gate cannot see it.")
        return False

    caught = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("- ")]
    print(f"  {label} -> caught")
    for line in caught[:2]:
        print(f"      {line[:150]}")
    return True


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real code")

    ok = True

    # A: one of the two pages stops reading the param.
    def drop_read(text: str) -> str:
        m = re.search(r'[ \t]*const searchParam = useSearchParams\(\)\?\.get\("search"\);\n', text)
        if not m:
            raise AssertionError("the search-param read is not in the expected shape")
        return text[:m.start()] + text[m.end():]

    ok = edit("A: the pages page stops reading ?search=", PAGES_PAGE,
              drop_read) and ok

    # B: the search stops matching the slug — the half that actually shipped
    #    broken, with every front-end check still green.
    def drop_slug(text: str) -> str:
        needle = "                    BlogPost.slug.ilike(like_q),\n"
        if needle not in text:
            raise AssertionError("the slug clause is not in the expected shape")
        return text.replace(needle, "", 1)

    ok = edit("B: the blog search stops matching the slug", BLOG_SERVICE,
              drop_slug) and ok

    # A2: `words` is built but the href sends something else. The name is in
    #     the file, the link is still broken — which is what a presence check
    #     for `words` reports as healthy.
    def wrong_value(text: str) -> str:
        needle = "const words = second.replace(/-/g, \" \");"
        if needle not in text:
            raise AssertionError("the words line is not in the expected shape")
        return text.replace(needle, "const words = second;", 1)

    ok = edit("A2: words stops being the slug's words", BAR, wrong_value) and ok

    # B2: the href sends the whole pathname instead of the words. `words` is
    #     still built and still unused, and a search for `/blog/my-post`
    #     matches nothing — the exact failure the bar's own comment warns of.
    def send_pathname(text: str) -> str:
        needle = "/admin/blog?search=${encodeURIComponent(words)}"
        if needle not in text:
            raise AssertionError("the href is not in the expected shape")
        return text.replace(needle, "/admin/blog?search=${encodeURIComponent(pathname)}", 1)

    ok = edit("B2: the link sends the whole path", BAR, send_pathname) and ok

    # C: the effect gains a dependency and re-seeds while the operator types.
    def add_dependency(text: str) -> str:
        needle = '  }, []);\n'
        if needle not in text:
            raise AssertionError("the empty dependency list is not in the expected shape")
        return text.replace(
            needle, "  }, [searchParam]);\n", 1)

    ok = edit("C: the effect re-seeds on every render", PAGE,
              add_dependency) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees a page that stopped reading the param, a "
          "search that stopped matching the slug, a link that sends the whole "
          "path or a value it never built, and an effect that overwrites "
          "typing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
