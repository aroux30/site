"""The media trash over HTTP, not just over the service.

The service-level checks passed while every trash request the panel makes was
broken: `GET /media/trash` and `POST /media/trash/empty` answered 422 because
`GET /{asset_id}` and `POST /trash/{asset_id}` were declared first and parsed
the literal as an id; `DELETE /media/trash/{id}` answered 405 because the
route did not exist; `DELETE /media/trash` answered 500 after purging because
the return annotation said `dict` and the function returned `int`.

None of those are visible to a service test — the service was fine. They are
visible only by driving the ASGI app, which is what the fixture does: upload,
trash, list, restore, purge, empty, and the refusals, all through HTTP.

Requires the local Postgres. Exits 2 (could-not-check) when the fixture is
absent, so a checkout without it is not reported as green.

    python scripts/wp-parity/check_media_trash_http.py
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


FIXTURE = os.path.join(_repo_root(), ".p1-tests", "media_trash_http_test.py")
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
        print("FAIL: the trash HTTP fixture timed out")
        return 1

    checks = [
        ln.strip()
        for ln in (proc.stdout or "").splitlines()
        if CHECK_LINE.match(ln.strip())
    ]
    for line in checks:
        print(f"     {line}")

    if proc.returncode != 0:
        print(f"FAIL: the trash HTTP fixture exited {proc.returncode}")
        for line in (proc.stdout or "").splitlines():
            if line.strip().startswith(("TRASH-HTTP GAPS:", "  ")) and "GAPS" in line:
                print(line)
        for line in (proc.stderr or "").strip().splitlines()[-5:]:
            print(f"     {line}")
        return 1

    print(f"PASS: {len(checks)} trash-over-HTTP check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
