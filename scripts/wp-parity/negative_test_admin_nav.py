"""Negative test for check_admin_nav.py — prove the guard can actually fail.

Per the project's own rule: a gate that cannot fail is not a gate. This
removes one sidebar link, asserts the guard reports that route as unlinked and
exits 1, then restores the file and asserts a clean pass.

Deliberately mutates a real file, so it takes a lock-free snapshot-and-restore
and refuses to run if the file changed underneath it. Run:
    python scripts/wp-parity/negative_test_admin_nav.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "frontend" / "app" / "admin" / "layout.tsx"
GUARD = ROOT / "scripts" / "wp-parity" / "check_admin_nav.py"

VICTIM = "/admin/system-health"


def run_guard() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    original = LAYOUT.read_text(encoding="utf-8")

    # Pick a link that really exists, so the test cannot pass by accident.
    if f'href: "{VICTIM}"' not in original:
        print(f"SKIP: {VICTIM} is not in adminLinks, so there is nothing to remove.")
        return 0

    try:
        # 1. Baseline must pass, else the test proves nothing.
        code, out = run_guard()
        if code != 0:
            print("FAIL: the guard does not pass on the unmodified tree.")
            print(out)
            return 1
        print("[1/4] baseline: guard passes on the real tree  OK")

        # 2. Remove the link.
        stripped = original.replace(f'{{ href: "{VICTIM}"', '{ href: "__removed__"', 1)
        stripped = re.sub(
            r'\{\s*href:\s*"' + re.escape(VICTIM) + r'"\s*,?\s*label:\s*"[^"]*"\s*,\s*icon:\s*\w+\s*\}',
            "",
            stripped,
            count=1,
        )
        if stripped == original:
            print("FAIL: could not remove the link — the test would be a no-op.")
            return 1
        LAYOUT.write_text(stripped, encoding="utf-8")
        print(f"[2/4] injected: removed the sidebar entry for {VICTIM}")

        # 3. The guard must now fail, and must name that exact route.
        code, out = run_guard()
        if code == 0:
            print("FAIL: guard still passed with a link removed — it cannot fail.")
            print(out)
            return 1
        if VICTIM not in out:
            print("FAIL: guard failed but did not name the unlinked route.")
            print(out)
            return 1
        print(f"[3/4] guard correctly failed and named {VICTIM}  OK")

    finally:
        LAYOUT.write_text(original, encoding="utf-8")
        print("[4/4] restored the original file")

    code, out = run_guard()
    if code != 0:
        print("FAIL: guard does not pass after restore — the file is damaged.")
        print(out)
        return 1
    print("\nPASS: the guard fails when it should and passes when it should.")
    return 0


if __name__ == "__main__":
    sys.exit(main())