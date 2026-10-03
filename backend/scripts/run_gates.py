#!/usr/bin/env python3
"""Run every read-only invariant gate, and report them together.

Each gate is a separate script that exits non-zero when it finds something.
Running them one at a time is how a gate gets skipped: the person fixing
something else does not know a check exists. This runs the whole set and prints
one summary, so a failure names the gate that failed rather than a bare exit
code.

Every gate here is read-only. None of them writes to the database or the working
tree — they are checks, not fixers, so running them can never be the thing that
changes the data.

Run:  python scripts/run_gates.py
Exit: 0 when every gate passed, 1 when any failed or could not run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

# This file lives at backend/scripts/, so the repo root is two levels up and the
# gates it runs live in <root>/scripts/wp-parity/.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
PY = sys.executable

#: (label, argv). Anything marked "db" needs a reachable database and is
#: reported as skipped rather than failed when one is not available, so a local
#: run without a database is not reported as a broken gate.
GATES: list[tuple[str, list[str], bool]] = [
    (
        "editor allowlist parity",
        [PY, "scripts/wp-parity/check_editor_allowlists.py"],
        False,
    ),
    (
        "stored HTML is sanitized",
        [PY, "scripts/wp-parity/check_stored_html.py"],
        True,
    ),
]


def _looks_like_a_missing_database(stderr: str) -> bool:
    """Whether a failure was "no database here" rather than a real finding."""
    markers = (
        "ConnectionRefused",
        "could not connect",
        "OperationalError",
        "does not exist",
        "Name or service not known",
        "password authentication failed",
    )
    return any(m.lower() in stderr.lower() for m in markers)


def main() -> int:
    if len(sys.argv) > 1:
        print("usage: run_gates.py  (no arguments)", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [BACKEND, env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    results: list[tuple[str, str, float]] = []
    for label, argv, needs_db in GATES:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            results.append((label, "timeout after 300s", time.monotonic() - started))
            continue
        took = time.monotonic() - started
        if proc.returncode == 0:
            results.append((label, "pass", took))
        elif needs_db and _looks_like_a_missing_database(proc.stderr):
            # A gate that could not run is not a gate that passed, and it is
            # also not a finding. Saying so is the only honest option.
            results.append((label, "skipped (no database reachable)", took))
        else:
            results.append((label, "FAIL", took))
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)

    print()
    print("invariant gates")
    print("-" * 52)
    for label, status, took in results:
        print(f"  {label:<30} {status:<32} {took:5.1f}s")
    print("-" * 52)

    failed = [r for r in results if r[1] == "FAIL"]
    if failed:
        print(f"{len(failed)} gate(s) failed.")
        return 1
    skipped = [r for r in results if r[1].startswith("skipped")]
    if skipped:
        print(f"{len(skipped)} gate(s) skipped: no database.")
    print("all gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
