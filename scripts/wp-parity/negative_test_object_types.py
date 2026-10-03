"""Negative test for the object_types guard: sabotage it and require the checks to fail.

`object_types` only earns its column if it stops something. Two sabotages prove
it does:

  A. the attach route stops consulting the taxonomy's object_types
  B. the boundary stops rejecting an unknown content type

Either one silently turns the column into a label, so the checks that read
"refused"/"rejected" must go red. Exit 0 only when they do.

    python scripts/wp-parity/negative_test_object_types.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FIXTURE = os.path.join(ROOT, ".p1-tests", "object_types_test.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog", "api", "wp_parity_routes.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "taxonomy_service.py"
)

# The line that makes the guard real. If this is ever renamed, this test fails
# loudly rather than quietly passing on a file it never edited.
GUARD_LINE = 'wrong = sorted('
UNKNOWN_LINE = 'if unknown:'


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


def lines_of(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def main() -> int:
    if not os.path.isfile(FIXTURE):
        print(f"FAIL: fixture missing at {FIXTURE}")
        return 1

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-500:])
        return 1

    routes_orig = lines_of(ROUTES)
    service_orig = lines_of(SERVICE)
    if not any(GUARD_LINE in l for l in routes_orig):
        print(f"FAIL: could not find the guard ({GUARD_LINE!r}) in {ROUTES}. "
              "This test has to edit the real guard to mean anything.")
        return 1
    if not any(UNKNOWN_LINE in l for l in service_orig):
        print(f"FAIL: could not find {UNKNOWN_LINE!r} in {SERVICE}")
        return 1

    failures = []

    # A. remove the object_types check from the attach route
    patched_routes = [
        l for l in routes_orig if 'if "cms_page" not in (types or [])' not in l
    ]
    with open(ROUTES, "w", encoding="utf-8") as fh:
        fh.write("\n".join(patched_routes))
    try:
        rc_a, out_a = run_fixture()
    finally:
        with open(ROUTES, "w", encoding="utf-8") as fh:
            fh.write("\n".join(routes_orig))
    if rc_a == 0:
        failures.append(
            "A: the attach route still accepted a posts-only term on a page "
            "after the object_types check was removed"
        )
    else:
        print("  A: removing the guard made the checks fail (as it must)")

    # B. accept any content type at the boundary. Scoped to the validator only:
    # `_reject_unknown` (the field allowlist) has its own `if unknown:`, and
    # disabling that too changes which error the call raises, so the check would
    # fail for the wrong reason.
    patched_service = list(service_orig)
    for i, line in enumerate(patched_service):
        if line.strip() != "if unknown:":
            continue
        # The object_types message is a few lines below this one; the field
        # allowlist's is not. That is the whole discriminator.
        window = "\n".join(patched_service[i : i + 4])
        if "نوع محتوای ناشناخته" in window:
            patched_service[i] = "    if False:"
    with open(SERVICE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(patched_service))
    changed = sum(1 for a, b in zip(service_orig, patched_service) if a != b)
    print(f"  (B) the sabotage changed {changed} line(s)")
    try:
        rc_b, out_b = run_fixture()
    finally:
        with open(SERVICE, "w", encoding="utf-8") as fh:
            fh.write("\n".join(service_orig))
    if rc_b == 0:
        failures.append(
            "B: an unknown content type was accepted after the boundary "
            "check was disabled"
        )
    else:
        print("  B: accepting an unknown type made the checks fail (as it must)")

    # The originals must be back and passing, or the run left the tree broken.
    rc_c, out_c = run_fixture()
    if rc_c != 0:
        print("FAIL: the fixture does not pass again after restoring the files — "
              "this test left the repository modified.")
        print(out_c.strip()[-500:])
        return 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("\nPASS: both sabotages were caught, so object_types is enforced "
          "rather than decorative.")
    return 0


if __name__ == "__main__":
    sys.exit(main())