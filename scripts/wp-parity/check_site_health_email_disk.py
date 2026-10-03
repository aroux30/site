"""Site Health reports email configuration and disk space.

    python scripts/wp-parity/check_site_health_email_disk.py
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


ROOT = _repo_root()
FIXTURE = os.path.join(ROOT, ".p1-tests", "site_health_email_disk_test.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    if not os.path.isfile(FIXTURE):
        print(f"SKIP: fixture missing at {FIXTURE}")
        print("     this gate did NOT run; do not read this as a pass.")
        return 2
    try:
        proc = subprocess.run(
            [sys.executable, "-B", FIXTURE],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("FAIL: the site-health fixture timed out")
        return 1
    checks = [
        ln.strip()
        for ln in (proc.stdout or "").splitlines()
        if CHECK_LINE.match(ln.strip())
    ]
    for line in checks:
        print(f"     {line}")
    if proc.returncode != 0:
        print(f"FAIL: the site-health fixture exited {proc.returncode}")
        for line in (proc.stdout or "").splitlines():
            if line.strip().startswith("SITE-HEALTH GAPS"):
                print(line)
        for line in (proc.stderr or "").strip().splitlines()[-5:]:
            print(f"     {line}")
        return 1
    print(f"PASS: {len(checks)} site-health check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())