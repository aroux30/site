"""Recovery mode's invitation key: the whole lifecycle, plus its routes.

    python scripts/wp-parity/check_recovery_invitation.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "recovery_invitation_test.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "settings", "api", "routes.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else label)

    # Static: the two routes exist, and the key is never returned in the HTTP
    # response (it goes to the mailbox; putting it in a body hands it to anyone
    # who can reach the route).
    routes = open(ROUTES, encoding="utf-8").read() if os.path.isfile(ROUTES) else ""
    check("the send-invitation route exists",
          "/admin/recovery-mode/send-invitation" in routes)
    check("the verify-invitation route exists",
          "/admin/recovery-mode/verify-invitation" in routes)
    check("the send route does not return the key in its response",
          '"key": issued' not in routes and "key=issued" not in routes,
          "the recovery key is echoed in the HTTP response")

    if not os.path.isfile(FIXTURE):
        print(f"SKIP: fixture missing at {FIXTURE}")
        return 2
    try:
        proc = subprocess.run(
            [sys.executable, "-B", FIXTURE],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
    except subprocess.TimeoutExpired:
        check("the recovery fixture ran", False, "timed out")
    else:
        for ln in (proc.stdout or "").splitlines():
            if CHECK_LINE.match(ln.strip()):
                print(f"     {ln.strip()}")
        check("the recovery key lifecycle behaves", proc.returncode == 0,
              (proc.stdout or "")[-400:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: recovery mode issues, hashes, verifies and expires its "
          "invitation key.")
    return 0


if __name__ == "__main__":
    sys.exit(main())