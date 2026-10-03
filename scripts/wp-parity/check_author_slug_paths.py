"""Every user-creation path writes an author_slug.

    python scripts/wp-parity/check_author_slug_paths.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "author_slug_paths_test.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else label)

    # The static half: every creation site that constructs a bare `User(` must
    # pass author_slug. Read the files, because a creation path added later
    # without the column is exactly the regression this guards.
    sources = {
        "auth_service.register": os.path.join(
            ROOT, "backend", "app", "modules", "auth", "application", "auth_service.py"
        ),
        "sso_service": os.path.join(
            ROOT, "backend", "app", "modules", "auth", "application", "sso_service.py"
        ),
        "user_service": os.path.join(
            ROOT, "backend", "app", "modules", "users", "application", "user_service.py"
        ),
    }
    for label, path in sources.items():
        text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
        check(f"{label} writes author_slug somewhere", "author_slug=" in text,
              "no author_slug assignment in the file")

    # The behaviour half: OTP registration must produce a unique slug.
    if not os.path.isfile(FIXTURE):
        print(f"SKIP: fixture missing at {FIXTURE}")
        return 2
    try:
        proc = subprocess.run(
            [sys.executable, "-B", FIXTURE],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=200,
        )
    except subprocess.TimeoutExpired:
        check("the OTP-path fixture ran", False, "timed out")
    else:
        for ln in (proc.stdout or "").splitlines():
            if CHECK_LINE.match(ln.strip()):
                print(f"     {ln.strip()}")
        check("the OTP path writes a unique slug",
              proc.returncode == 0, (proc.stdout or "")[-400:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: author_slug is written on every creation path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())