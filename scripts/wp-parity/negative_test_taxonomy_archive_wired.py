"""Negative test for check_taxonomy_archive_wired.

Three sabotages, each of which produces the state this item was reported in —
reachable in the API, invisible to a shopper.

  A. Point the term page at the unfiltered blog list. The page renders, the
     heading is right, and every post under it is unrelated to the term. The
     page-level checks pass; only the filter assertion sees it.
  B. Remove the `is_active` filter. A store that retires a taxonomy still
     serves its whole archive, which is the opposite of what the switch means.
  C. Remove the page. The route and the client stay, so every source check on
     the backend passes and the archive links to 404s — which is precisely
     what "route without a consumer" looks like from the shopper's side.

Run:  python scripts/wp-parity/negative_test_taxonomy_archive_wired.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_taxonomy_archive_wired.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog", "api",
                      "wp_parity_routes.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")
TERM = os.path.join(ROOT, "frontend", "app", "(store)", "blog", "taxonomy",
                    "[taxonomy]", "[slug]", "page.tsx")


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

    def drop_active(text: str) -> str:
        needle = "            CustomTaxonomy.is_active.is_(True),\n"
        if needle not in text:
            raise AssertionError("the active filter is not in the expected shape")
        return text.replace(needle, "", 1)

    ok = edit("B: serve a retired taxonomy anyway", ROUTES, drop_active) and ok

    # A: the client stops passing the filter — the page still renders, with
    #    posts that have nothing to do with the term.
    def drop_page_size(text: str) -> str:
        # Scoped to the taxonomy call by the function it sits in. A bare
        # `{ page, page_size }` appears in several list calls, and removing
        # the first one takes some other call — which is how the first
        # version reported a pass it did not earn.
        at = text.index("export async function fetchCustomTaxonomyTermPosts")
        stop = text.index("export async function fetchBlogTags", at)
        block = text[at:stop]
        needle = "{ params: { page, page_size: pageSize } }"
        if needle not in block:
            raise AssertionError("the taxonomy call is not in the expected shape")
        return text[:at] + block.replace(needle, "{ params: { page } }", 1) + text[stop:]

    ok = edit("A: the term call stops asking the server to filter", CLIENT,
              drop_page_size) and ok

    # C: the term page goes.
    hold = TERM + ".hold"
    shutil.move(TERM, hold)
    rc_broken, out_broken = run_gate()
    shutil.move(hold, TERM)
    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAIL: C — the term page was not restored.")
        ok = False
    elif rc_broken == 0:
        print("FAIL: C: removing the term page still passed.")
        ok = False
    else:
        print("  C: remove the term page -> caught")

    if not ok:
        return 1
    print("\nPASS: the gate sees an unfiltered term page, a retired taxonomy "
          "still served, and a missing page the backend knows nothing about.")
    return 0


if __name__ == "__main__":
    sys.exit(main())