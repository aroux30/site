"""Negative test: the stdlib-logger kwarg gate can actually fail.

A gate that only ever prints PASS is not a gate. This breaks each property the
check depends on, one at a time, and requires the check to go red for the
stated reason.

The sabotages land on a **copy** of one source file in a temp directory, and
the gate is pointed at the copy with its optional ROOT argument. Nothing in
the real tree is ever written to.

    cd backend && python scripts/negative_test_stdlib_logger_kwargs.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parent.parent
CHECK = BACKEND / "scripts" / "check_stdlib_logger_kwargs.py"

# A minimal stand-in for a real source file: stdlib logger + one call site.
BASELINE = """\
import logging
logger = logging.getLogger(__name__)

def run():
    logger.info("all_good")
"""

# (name, source, expected substring in the check's output)
CASES: list[tuple[str, str, str]] = [
    (
        "a structlog-style kwarg on a stdlib logger (the shipped bug)",
        'logger.info("evt", posts=3)\n',
        "posts=",
    ),
    (
        "multiple kwargs, only one invalid",
        'logger.warning("evt", extra={"a": 1}, count=5)\n',
        "count=",
    ),
    (
        "an error call with a kwarg",
        'logger.error("evt", reason="boom")\n',
        "reason=",
    ),
]

# Calls that must NOT be flagged: the valid stdlib kwargs and a structlog
# logger used the structlog way (different object entirely).
CLEAN_CASES: list[tuple[str, str]] = [
    ("exc_info is a valid stdlib kwarg", 'logger.exception("evt", exc_info=True)\n'),
    ("extra is a valid stdlib kwarg", 'logger.info("evt", extra={"k": 1})\n'),
    ("format args are not kwargs", 'logger.info("evt posts=%d", 3)\n'),
]


def run_check(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK), str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": "."},
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="logger-kwarg-gate-") as tmp:
        copy = Path(tmp) / "sample.py"

        print("baseline (clean copy):")
        copy.write_text(BASELINE, encoding="utf-8")
        code, out = run_check(Path(tmp))
        if code != 0:
            print(out)
            print("FAIL: the check does not pass on the clean copy, so a red "
                  "run below would mean nothing")
            return 1
        print("  PASS as expected")
        print("")

        for name, call, expected in CASES:
            copy.write_text(BASELINE + call, encoding="utf-8")
            code, out = run_check(Path(tmp))
            if code == 0:
                failures.append(f"{name}: the check still passed")
                print(f"  FAIL {name} — the check still passed")
            elif expected not in out:
                failures.append(
                    f"{name}: red for the wrong reason — expected {expected!r} "
                    f"in the output"
                )
                print(f"  FAIL {name} — red for the wrong reason")
                print("    " + out.strip().replace("\n", "\n    "))
            else:
                print(f"  PASS {name} -> check went red for the right reason")

        print("")
        print("clean cases (must stay green):")
        for name, call in CLEAN_CASES:
            copy.write_text(BASELINE + call, encoding="utf-8")
            code, out = run_check(Path(tmp))
            if code != 0:
                failures.append(f"{name}: false positive — {out.strip()}")
                print(f"  FAIL {name} — false positive")
                print("    " + out.strip().replace("\n", "\n    "))
            else:
                print(f"  PASS {name}")

    # The real tree must be green (the copy took every hit).
    code, out = run_check(BACKEND / "app")
    if code != 0:
        failures.append("the check is red on the real tree: " + out.strip())
    else:
        print("")
        print("PASS: the real tree is green.")

    if failures:
        print("")
        for f in failures:
            print("FAILURE: " + f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
