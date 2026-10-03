"""Application passwords authenticate over HTTP Basic, as WordPress does.

    python scripts/wp-parity/check_basic_auth_app_password.py

P2 "REST: احراز Basic با Application Password". The item was reported as a gap
("only Bearer is accepted"). Recon and a live probe showed the path is in fact
complete — so this gate exists to *keep* it complete: a working feature with
no gate is one refactor away from silently reverting, and the failure is quiet
(a WordPress client script gets 401 and its author concludes the store does
not support application passwords at all).

The load-bearing property is not "Basic parses" — it is that **the username is
not trusted**. The credential is looked up by the password's own record, and
the record's subject is who the request is; a caller who sends a different
username gets the identity the password actually belongs to. A gate that only
checked "Basic returns 200" would miss the version that trusts the username,
which is an identity-spoofing bug.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "basic_auth_app_password_test.py")
DEPS = os.path.join(ROOT, "backend", "app", "core", "security", "dependencies.py")
CHECK_LINE = re.compile(r"^\d+\.")


def _run_fixture(path: str) -> int:
    try:
        proc = subprocess.run(
            [sys.executable, "-B", path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"  {os.path.basename(path)}: timed out")
        return 1
    for ln in (proc.stdout or "").splitlines():
        if CHECK_LINE.match(ln.strip()):
            print(f"     {ln.strip()}")
    return proc.returncode


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else detail)

    src = open(DEPS, encoding="utf-8").read() if os.path.isfile(DEPS) else ""

    # 1. A Basic scheme is declared, with auto_error=False so an absent header
    #    falls through to the other schemes instead of 401ing immediately.
    check("a Basic scheme is declared",
          "HTTPBasic" in src, "no HTTPBasic scheme")
    check("it does not hard-fail on a missing header",
          re.search(r"HTTPBasic\(auto_error=False\)", src) is not None,
          "a request without Basic would 401 before Bearer/cookie are tried")

    # 2. The extraction path reads basic.password.
    check("the extractor reads the Basic password",
          "basic.password" in src, "the Basic password is never consumed")

    # 3. The password is looked up by its own record — the username must not
    #    reach the credential lookup. If `basic.username` were used to find the
    #    user, the property below would be a spoofing bug.
    check("the username is not used to resolve the identity",
          "basic.username" not in src,
          "the Basic username is consulted — a caller could name somebody else")

    # 4. The app-password branch runs before JWT decoding (a non-JWT token
    #    would fail decode), and both schemes advertise on the 401.
    app_at = src.find("_looks_like_application_password(token)")
    jwt_at = src.find('verify_token(token, expected_type="access")')
    check("the app-password branch precedes JWT verification",
          app_at != -1 and jwt_at != -1 and app_at < jwt_at,
          "a Basic app password would be fed to the JWT decoder")
    check("the 401 advertises both schemes",
          'Bearer, Basic realm="api"' in src,
          "a WordPress client is not told Basic is available")

    if not os.path.isfile(FIXTURE):
        check("the Basic auth fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the Basic auth behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: application passwords authenticate over Basic as well as "
          "Bearer, the username is not trusted, and revocation closes both.")
    return 0


if __name__ == "__main__":
    sys.exit(main())