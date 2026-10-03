"""Negative test for the live slug check: sabotage it and require the failure.

The editor's inline check is a convenience; the server's create guard is the
guarantee. A sabotaged check that still reports "available" for a taken slug
would let an operator fill in a name, see it accepted, and only find out on
submit — which is the exact failure the check existed to remove.

    python scripts/wp-parity/negative_test_page_slug.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "page_slug_test.py")
SERVICE = os.path.join(
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
    for path in (FIXTURE, SERVICE):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    original = read(SERVICE)

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-600:])
        return 1

    failures = []

    # A. the check stops consulting the database: every slug reads free
    patched = original.replace(
        "    if await _slug_exists(db, candidate, exclude_id=exclude_id):\n"
        '        return {"slug": candidate, "available": False, "reason": "taken"}\n',
        "    # sabotaged: the taken-slug branch removed\n",
        1,
    )
    if patched == original:
        failures.append(
            "A: the sabotage matched nothing — check_slug_available has moved "
            "and this test is pointing at nothing"
        )
    else:
        with open(SERVICE, "w", encoding="utf-8") as fh:
            fh.write(patched)
        try:
            rc_a, _ = run_fixture()
        finally:
            with open(SERVICE, "w", encoding="utf-8") as fh:
                fh.write(original)
        if rc_a == 0:
            failures.append("A: a taken slug still reported available")
        else:
            print("  A: removing the taken-slug check was caught (as it must be)")

    # B. the reserved-route guard is dropped
    patched_b = original.replace(
        '    if candidate in RESERVED_SLUGS:\n'
        '        return {"slug": candidate, "available": False, "reason": "reserved"}\n',
        "    # sabotaged: the reserved-slug branch removed\n",
        1,
    )
    if patched_b == original:
        failures.append("B: the sabotage matched nothing — the reserved-slug branch moved")
    else:
        with open(SERVICE, "w", encoding="utf-8") as fh:
            fh.write(patched_b)
        try:
            rc_b, _ = run_fixture()
        finally:
            with open(SERVICE, "w", encoding="utf-8") as fh:
                fh.write(original)
        if rc_b == 0:
            failures.append("B: a reserved store route still reported available")
        else:
            print("  B: removing the reserved-slug check was caught (as it must be)")

    rc_final, out_final = run_fixture()
    if rc_final != 0:
        print("FAIL: the fixture does not pass again after restoring the file — "
              "this test left the repository modified.")
        print(out_final.strip()[-600:])
        return 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("\nPASS: both sabotages were caught, so the slug check reflects the "
          "database and the reserved-route list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())