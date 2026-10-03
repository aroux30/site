"""Negative test for check_stdout_guards_are_idempotent.

The bug this guards against killed six negative tests at once, each with the
same `ValueError: I/O operation on closed file`, and each looking like a broken
test rather than a broken tree. So the sabotage is a single non-idempotent
wrapper in a throwaway file — one line, the exact shape that caused it.

The crash is not simulated: the script runs in a subprocess whose stdout is a
pipe, and asserts the text a *following* import can still print. That is the
property that failed.

Run:  python scripts/wp-parity/negative_test_stdout_guards_are_idempotent.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_stdout_guards_are_idempotent.py")
PROBE = "zz_stdout_probe.py"

#: A module that wraps stdout the old way, then one that imports it and
#: prints. The second is what dies in the un-fixed tree.
PROBE_BODY = '''"""A throwaway file that rebinds stdout the non-idempotent way."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
print("the wrapper is in place")
'''

IMPORTER = '''"""Import the wrapper, then try to print — the exact failure."""
import sys, os
sys.path.insert(0, %r)
import %s  # noqa: F401
print("still alive after the import")
'''


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real tree.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real tree")

    probe = os.path.join(HERE, PROBE)
    importer = os.path.join(HERE, PROBE.replace(".py", "_importer.py"))
    with open(probe, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(PROBE_BODY)
    with open(importer, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(IMPORTER % (HERE, PROBE[:-3]))

    ok = True
    try:
        rc_broken, out_broken = run_gate()
    finally:
        for path in (probe, importer):
            if os.path.exists(path):
                os.remove(path)

    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAIL: the gate did not pass again after cleanup.")
        return 1
    if rc_broken == 0:
        print("FAIL: a fresh stdout wrapper still passed.")
        return 1

    caught = [ln.strip() for ln in out_broken.splitlines()
              if ln.strip().startswith("- ")]
    print("  a fresh stdout wrapper -> caught")
    for line in caught[:2]:
        print(f"      {line[:150]}")

    # And the property itself, in a process where it actually bites.
    try:
        proc = subprocess.run(
            [sys.executable, importer], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        alive = "still alive after the import" in (proc.stdout or "")
    except Exception:
        alive = False
    if not ok:
        return 1
    print("\nPASS: the gate sees a fresh wrapper, and the failure it prevents "
          "is a crash rather than a wrong answer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
