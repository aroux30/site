"""Negative test for check_every_gate_is_registered.

The failure this guards against happened for real: three gates sat on disk
passing and had never been run by the suite. So the sabotage is the shape of
that mistake rather than a variant of it — a gate file that exists, works, and
is not in the registry.

Both directions, because both leave the suite green:

  A. Add a gate file that nobody registers. It passes when run by hand and is
     never executed by the runner — the exact state that hid the original three.
  B. Remove a registration, leaving the gate on disk. Now the suite runs one
     gate fewer and reports green.

Run:  python scripts/wp-parity/negative_test_every_gate_is_registered.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_every_gate_is_registered.py")
PARITY = os.path.join(HERE)
RUNNER = os.path.join(ROOT, "scripts", "run_all_gates.py")

PROBE = '''"""A gate that exists and is not registered — written only to prove the check sees it."""
import os
import sys

sys.exit(0)
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

    ok = True

    # A: an unregistered gate file.
    probe = os.path.join(PARITY, "check_zz_unregistered_probe.py")
    with open(probe, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(PROBE)
    try:
        rc_broken, out_broken = run_gate()
    finally:
        if os.path.exists(probe):
            os.remove(probe)
    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAIL: A — the gate did not pass again after cleanup.")
        ok = False
    elif rc_broken == 0:
        print("FAIL: A: an unregistered gate file still passed.")
        ok = False
    else:
        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("- ")]
        print("  A: an unregistered gate file -> caught")
        for line in caught[:1]:
            print(f"      {line[:150]}")

    # B: a registration removed, gate left in place.
    with open(RUNNER, encoding="utf-8") as fh:
        original = fh.read()
    m = re.search(r'^\s*\("(check_[a-z0-9_]+)", (?:True|False)\),\n', original, re.M)
    if not m:
        print("FAIL: B — no registration line found to remove.")
        return 1
    with open(RUNNER, "w", encoding="utf-8", newline="") as fh:
        fh.write(original[:m.start()] + original[m.end():])
    try:
        rc_broken, out_broken = run_gate()
    finally:
        with open(RUNNER, "w", encoding="utf-8", newline="") as fh:
            fh.write(original)
    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAIL: B — the runner was not restored.")
        ok = False
    elif rc_broken == 0:
        print("FAIL: B: removing a registration still passed.")
        ok = False
    else:
        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("- ")]
        print("  B: a removed registration -> caught")
        for line in caught[:1]:
            print(f"      {line[:150]}")

    if not ok:
        return 1
    print("\nPASS: the gate sees both an unregistered gate and a missing one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())