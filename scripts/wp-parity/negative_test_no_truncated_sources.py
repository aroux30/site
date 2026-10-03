"""Negative test for check_no_truncated_sources.

The gate guards against a mistake that has now happened twice in this project:
a script read a file line by line, hit a `break`, and wrote back only what it
had accumulated. Both times a several-hundred-line file became a handful of
lines and nothing failed until something tried to use it.

So the sabotage is that mistake, applied literally, to a real module — and the
gate has to notice without booting the app.

Two cuts, because they break different things:

  A. Cut a file down to a stub that still parses: the imports are gone, the
     definitions are gone, and the file is a valid Python file with nothing in
     it. Nothing raises on import.
  B. Cut a file mid-statement so it no longer parses. This is what happened to
     `media/api/routes.py`: the decorator was there and its body was not.

Run:  python scripts/wp-parity/negative_test_no_truncated_sources.py
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
GATE = os.path.join(HERE, "check_no_truncated_sources.py")

#: A small, real module. Chosen because nothing else imports it in a way that
#: would turn a broken copy into a second failure — the gate reads files, it
#: does not import them, so the test needs the file intact on disk afterwards
#: and nothing else.
TARGET = os.path.join(ROOT, "backend", "app", "shared", "identifiers", "uuid.py")

STUB = '"""Placeholder."""\n'


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    if not os.path.isfile(TARGET):
        print(f"FAIL: target missing at {TARGET}")
        return 1

    with open(TARGET, encoding="utf-8") as fh:
        original = fh.read()
    lines = original.count("\n") + 1

    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-900:])
        return 1
    print(f"gate passes on the real code ({lines} lines of source)")

    ok = True
    cases = [
        # A valid Python file with nothing in it: parses, imports, and is a
        # stub. This is the cut that does not raise.
        ("A: truncate a module to a valid stub", STUB),
        # A decorator with no body — the exact shape the routes file was in.
        ("B: cut a file mid-statement",
         original[: int(len(original) * 0.3)] + "\n    dependencies=[_x],\n"),
    ]

    for label, payload in cases:
        with open(TARGET, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)
        try:
            rc_broken, out_broken = run_gate()
        finally:
            with open(TARGET, "w", encoding="utf-8", newline="") as fh:
                fh.write(original)

        rc_after, out_after = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after restoring.")
            print(out_after.strip()[-700:])
            ok = False
            continue
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            ok = False
            continue

        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("FAIL ") or ln.strip().startswith("- ")]
        print(f"  {label} -> caught")
        for line in caught[:2]:
            print(f"      {line[:150]}")

    if not ok:
        return 1
    print("\nPASS: the gate goes red on a stub that parses and on a file cut "
          "mid-statement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())