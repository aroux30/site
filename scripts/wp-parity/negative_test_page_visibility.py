"""Negative test for the page visibility guard, including the backfill that shipped wrong once.

Three sabotages, all of which have to be caught:

  A. the public path stops checking ``visibility`` — a private page is served
  B. a password is stored in plaintext
  C. the backfill matches ``status = 'published'`` (lowercase) instead of
     ``upper(status)`` — the exact bug this migration shipped with, which
     quietly made every already-published page private

C is the interesting one: it passes migration-time, applies cleanly, and
takes the storefront down. A guard that only checks the endpoint would not
notice.

    python scripts/wp-parity/negative_test_page_visibility.py
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
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FIXTURE = os.path.join(ROOT, ".p1-tests", "page_visibility_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "content", "application", "cms_page_service.py"
)
MIGRATION = os.path.join(
    ROOT, "backend", "alembic", "versions",
    "2026_10_02_v3w4x5y6z7a8_add_cms_page_cover_and_visibility.py",
)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


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
    for path in (FIXTURE, SERVICE, MIGRATION):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-600:])
        return 1

    service_orig, migration_orig = read(SERVICE), read(MIGRATION)
    failures = []

    def sabotage(label: str, path: str, original: str, patched: str) -> None:
        nonlocal failures
        if patched == original:
            failures.append(f"{label}: the sabotage changed nothing — this "
                            f"negative test is pointing at code that moved")
            return
        write(path, patched)
        try:
            rc_s, _ = run_fixture()
        finally:
            write(path, original)
        if rc_s == 0:
            failures.append(f"{label}: the checks still passed")
        else:
            print(f"  {label}: caught (as it must be)")

    # A. the storefront stops honouring visibility
    sabotage(
        "A: public path ignores visibility",
        SERVICE,
        service_orig,
        service_orig.replace(
            "            CmsPage.visibility == PageVisibility.PUBLIC,\n", "", 1
        ),
    )

    # B. the password is stored as given
    sabotage(
        "B: password stored in plaintext",
        SERVICE,
        service_orig,
        service_orig.replace(
            "    return hash_password(raw)", "    return raw  # sabotaged", 1
        ),
    )

    # C. the backfill's case handling. It cannot be sabotaged through the
    #    fixture — the fixture reads rows the migration already wrote, so a
    #    broken backfill would need a real re-run to show up. It is checked
    #    directly instead: the stored status is the enum *member name*
    #    ("PUBLISHED"), so the comparison has to be case-insensitive.
    c_ok = "upper(status) = 'PUBLISHED'" in migration_orig
    if not c_ok:
        failures.append(
            "C: the backfill compares the status case-sensitively against "
            "'published' while the column holds 'PUBLISHED' — every "
            "already-published page would be backfilled to private"
        )
    else:
        print("  C: the backfill is case-insensitive (checked directly)")

    rc_final, out_final = run_fixture()
    if rc_final != 0:
        print("FAIL: the fixture does not pass again after restoring the files — "
              "this test left the repository modified.")
        print(out_final.strip()[-600:])
        return 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("\nPASS: all three sabotages were caught, so the visibility guard, "
          "the password hashing and the backfill are all real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())