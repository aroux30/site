"""Negative test for check_no_sabotage_left_in_source.

Two shapes, because they are different files and different mistakes:

  A. A backend module with `pass  # sabotaged: ...` in the middle of a
     function. This is the exact line that shipped once: the file imported
     cleanly and no comment could be posted at all.
  B. A frontend module with `if False: // sabotage: ...`. The guard is
     disabled rather than removed, so nothing raises and the check simply
     passes everything.

One of them is a bare statement, one is a guard. A check that only looked for
the bare form would miss the guard, which is the shape a sabotage takes when
it *replaces* a condition instead of replacing a statement.

Run:  python scripts/wp-parity/negative_test_no_sabotage_left_in_source.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wp-parity"))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_no_sabotage_left_in_source.py")

#: Written into a module the gate scans, and removed afterwards. Chosen because
#: nothing imports it: the gate reads files, so an unimported module is enough
#: and it cannot break anything else while it is there.
PY_PROBE = '''"""A module that exists only for one gate run."""
from __future__ import annotations


def f(limit: int) -> None:
    # sabotage: ceiling disabled
    pass  # sabotage
'''

TS_PROBE = '''export function g(a: number, b: number): boolean {
  if (false) {
    // sabotage: guard neutered
  }
  return a !== b; // sabotage
}
'''


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def with_probe(rel: str, body: str) -> tuple[int, str]:
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    try:
        return run_gate()
    finally:
        if os.path.exists(path):
            os.remove(path)


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real tree.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real tree")

    ok = True
    for label, rel, body in (
        ("A: a backend pass # sabotaged", "backend/app/_gate_probe.py", PY_PROBE),
        ("B: a frontend if False with a sabotage guard",
         "frontend/app/_gate_probe.ts", TS_PROBE),
    ):
        rc_broken, out_broken = with_probe(rel, body)
        rc_after, _ = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after cleanup.")
            ok = False
            continue
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            ok = False
            continue
        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("FAIL ")]
        print(f"  {label} -> caught")
        for line in caught[:1]:
            print(f"      {line[:150]}")

    if not ok:
        return 1
    print("\nPASS: the gate sees a bare statement and a neutered guard, in "
          "either language.")
    return 0


if __name__ == "__main__":
    sys.exit(main())