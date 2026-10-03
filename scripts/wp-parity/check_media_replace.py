"""Replace media (same URL, new bytes), run as a gate.

    python scripts/wp-parity/check_media_replace.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root() -> str:
    d = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".p1-tests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.normpath(os.path.join(HERE, "..", ".."))


FIXTURE = os.path.join(_repo_root(), ".p1-tests", "media_replace_test.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    if not os.path.isfile(FIXTURE):
        print(f"SKIP: fixture missing at {FIXTURE}")
        print("     this gate did NOT run; do not read this as a pass.")
        return 2

    try:
        proc = subprocess.run(
            [sys.executable, FIXTURE],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("FAIL: the media replace fixture timed out")
        return 1

    checks = [
        ln.strip()
        for ln in (proc.stdout or "").splitlines()
        if CHECK_LINE.match(ln.strip())
    ]
    for line in checks:
        print(f"     {line}")

    if proc.returncode != 0:
        print(f"FAIL: the media replace fixture exited {proc.returncode}")
        for line in (proc.stdout or "").splitlines():
            if line.strip().startswith("REPLACE GAPS"):
                print(line)
        for line in (proc.stderr or "").strip().splitlines()[-5:]:
            print(f"     {line}")
        return 1

    print(f"PASS: {len(checks)} replace-media check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
