"""Negative test for check_page_lock_autosave_wired.

The gate caught the real state of this feature when it was first written: the
routes existed, the client could address both object types, and the page editor
called none of it. The check that failed was the consumer — which is the whole
reason it is in the gate.

So the sabotages are the two ways it goes back to being decorative:

  A. Remove the page lock routes. The posts keep theirs, so a check that only
     asks "are there lock routes" passes.
  B. Remove the consumer from the page editor. Everything still exists and
     still works when called — and nobody ever calls it.

Run:  python scripts/wp-parity/negative_test_page_lock_autosave_wired.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_page_lock_autosave_wired.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog", "api", "routes.py")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")

LOCK_BANNER_RE = re.compile(
    r"[ \t]*\{lockedByOther && \(.*?\n[ \t]*\)\}\n", re.S
)


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

    def drop_page_routes(text: str) -> str:
        # Every route whose path mentions pages/{page_id} and is lock/autosave.
        # Renaming the path segment is enough: the gate looks for the literal
        # string, and so does anything reading the OpenAPI schema.
        count = 0
        for suffix in ("/lock", "/lock/heartbeat", "/autosave"):
            needle = f'"/pages/{{page_id}}{suffix}"'
            if needle in text:
                text = text.replace(needle, needle.replace("pages", "articles"), 1)
                count += 1
        if count != 3:
            raise AssertionError(f"removed {count} page routes, expected 3")
        return text

    def drop_consumer(text: str) -> str:
        new, n = LOCK_BANNER_RE.subn("", text, count=1)
        if n != 1:
            raise AssertionError(f"the lock banner matched {n} times")
        return new

    ok = True
    for label, path, fn in (
        ("A: remove the page lock and autosave routes", ROUTES, drop_page_routes),
        ("B: remove the consumer from the page editor", PAGE, drop_consumer),
    ):
        ok = edit(label, path, fn) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees both missing routes and a feature nobody calls.")
    return 0


if __name__ == "__main__":
    sys.exit(main())