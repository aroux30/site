"""Negative test: the scripts-runnable guard can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This injects the two defects the guard
exists to catch:

  1. an `.mts` check using `process.cwd()` in code — which broke when run from
     any subdirectory, because paths resolved against the wrong base
  2. an `.mts` check that actually exits non-zero from a subdirectory

    python scripts/wp-parity/negative_test_scripts_runnable.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import io
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_scripts_runnable.py"
MTS_FILE = ROOT / "scripts" / "wp-parity" / "verify_content_srcset.mts"

CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "process.cwd() is used in code rather than resolved from fileURLToPath",
        MTS_FILE,
        "const HERE = dirname(fileURLToPath(import.meta.url));",
        "const HERE = process.cwd();",
        "resolves paths from process.cwd()",
    ),
    (
        "the script fails when run from elsewhere",
        MTS_FILE,
        "process.exit(0);",
        'if (process.cwd().includes("frontend")) process.exit(1); else process.exit(0);',
        "exits 1 when run from",
    ),
]


def run_guard() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    saved: dict[Path, str] = {}
    for _, path, _, _, _ in CASES:
        if path not in saved:
            saved[path] = path.read_text(encoding="utf-8")

    try:
        return _run(saved)
    finally:
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    print("baseline (unbroken tree):")
    code, out = run_guard()
    if code != 0:
        print(out)
        print("FAIL: the guard is not green on the unbroken tree")
        return 1
    print("  PASS as expected\n")

    failures: list[str] = []
    for name, path, original, broken, expected in CASES:
        source = saved[path]
        if original not in source:
            failures.append("%s: marker not found in %s" % (name, path.name))
            continue
        path.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_guard()
        finally:
            path.write_text(source, encoding="utf-8")

        if code == 0:
            failures.append("%s: the guard still passed" % name)
            print("  FAIL %s -- the guard still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the guard went red for the wrong reason -- expected %r"
                % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason\n    %s" % (name, out.strip()))
        else:
            print("  PASS %s -> guard went red for the right reason" % name)

    code, out = run_guard()
    if code != 0:
        print(out)
        failures.append("the guard is red after restoring")
    else:
        print("\nPASS: the tree is green again after all injections reverted.")

    if failures:
        print("")
        for f in failures:
            print("FAIL: %s" % f)
        return 1
    print("\nPASS: every assertion in check_scripts_runnable can fail for its own reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())