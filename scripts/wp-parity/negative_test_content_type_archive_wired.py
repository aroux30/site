"""Negative test for check_content_type_archive_wired.

The failure this guards against is the one the gap document named: the route
existed, was correct, and had no caller — so a content type an operator had
filled was unreachable on the storefront. That reads as "working" from every
angle that does not open the page.

The sabotages are the three places that disconnect happens, plus the two that
make it worse than an empty page:

  A. Remove the page. The route and the client stay, everything above them
     passes, and nothing renders.
  B. Point the public client at the admin route. It "works" and returns
     unpublished entries — a storefront page showing drafts.
  C. Put a write guard on the public type list. The archive then 403s for every
     customer, which looks like a permissions problem rather than a mistake.
  D. Render `entry.data` raw instead of by its declared fields. The page works
     and looks like a debug view, which a gate checking "does it render" misses.

Run:  python scripts/wp-parity/negative_test_content_type_archive_wired.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_content_type_archive_wired.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "content",
                      "api", "routes.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "cms-admin.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "content", "[slug]",
                    "page.tsx")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit_text(label: str, path: str, fn) -> bool:
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
    for line in caught[:1]:
        print(f"      {line[:140]}")
    return True


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real code")

    ok = True

    # A: the page itself goes. Renamed rather than deleted, so the gate's
    #    existence check fails loudly instead of crashing on a missing file.
    backup = PAGE + ".hold"
    shutil.move(PAGE, backup)
    rc_broken, out_broken = run_gate()
    shutil.move(backup, PAGE)
    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAIL: A — the page was not restored.")
        ok = False
    elif rc_broken == 0:
        print("FAIL: A: removing the archive page still passed.")
        ok = False
    else:
        print("  A: remove the archive page -> caught")

    # B: the public client points at the admin route.
    def to_admin(text: str) -> str:
        needle = "`/content/content-types/${typeSlug}/entries`"
        if needle not in text:
            raise AssertionError("the public entries path is not in the expected shape")
        return text.replace(
            needle, "`/content/admin/content-types/${typeSlug}/entries`", 1)

    ok = edit_text("B: point the public client at the admin route", CLIENT,
                   to_admin) and ok

    # C: a write guard on the public type list.
    def add_guard(text: str) -> str:
        needle = '    "/content-types",\n    summary="List active content types (storefront)",\n)'
        if needle not in text:
            raise AssertionError("the public type route is not in the expected shape")
        return text.replace(
            needle,
            '    "/content-types",\n    summary="List active content types (storefront)",\n'
            '    dependencies=[_require_content_write],\n)',
            1,
        )

    ok = edit_text("C: guard the public type list behind a write permission",
                   ROUTES, add_guard) and ok

    # D: render the raw object instead of the declared fields.
    def raw_dump(text: str) -> str:
        needle = "{entries.map((entry) => renderEntry(entry, type.field_schema))}"
        if needle not in text:
            raise AssertionError("the entry render call is not in the expected shape")
        return text.replace(
            needle,
            "{entries.map((entry) => (\\n"
            "            <pre>{JSON.stringify(entry.data, null, 2)}</pre>\\n"
            "          ))}",
            1,
        )

    ok = edit_text("D: render the raw object instead of its fields", PAGE,
                   raw_dump) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees a missing page, a client pointed at the admin "
          "route, a guard on the public list, and a raw-JSON render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())