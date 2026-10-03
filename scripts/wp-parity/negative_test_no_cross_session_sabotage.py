"""Negative test for check_no_cross_session_sabotage.

The gate exists after a real incident: three half-written media files, each
from a negative test racing another session's edit. This proves the gate can
still see that class of mistake — by writing a test that does exactly it.

Both sabotages are new files, so nothing in the tree is touched.

Run:  python scripts/wp-parity/negative_test_no_cross_session_sabotage.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_no_cross_session_sabotage.py")
PARITY = os.path.join(ROOT, "scripts", "wp-parity")

#: A test shaped exactly like the ones that caused the incident: a `SERVICE`
#: constant pointing into another session's module, and an open/write/restore
#: around it.
TEMPLATE = '''"""A deliberately mis-scoped test, written only to prove the gate sees it."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

SERVICE = os.path.join(ROOT, "backend", "app", "modules", "media",
                       "application", "media_service.py")


def main() -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

ROUTES_TEMPLATE = TEMPLATE.replace(
    '"media",\n                       "application", "media_service.py"',
    '"settings",\n                       "application", "settings_service.py"',
)


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def gate_with_temp_test(name: str, body: str) -> tuple[int, str]:
    """Write a probe test, run the gate against it, and always remove it.

    Returns the gate's result *while the probe was present*. The cleanup is in
    a `finally` rather than at the call site so a failing probe cannot leave a
    stray file behind — a stray test in this directory is itself something the
    real gate would flag on the next run.
    """
    path = os.path.join(PARITY, name)
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
    for label, name, body in (
        ("A: a test that writes media_service.py",
         "negative_test_zz_probe_media.py", TEMPLATE),
        ("B: a test that writes into settings/",
         "negative_test_zz_probe_settings.py", ROUTES_TEMPLATE),
    ):
        rc_broken, out_broken = gate_with_temp_test(name, body)
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
        for line in caught[:2]:
            print(f"      {line[:150]}")

    if not ok:
        return 1
    print("\nPASS: the gate still catches a negative test aimed at another "
          "session's file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())