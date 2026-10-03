"""Remember-me and registration email verification are wired end to end.

    python scripts/wp-parity/check_remember_me_and_email_verification.py

Two features, each with the recurring failure shape this gate exists to catch:
a server capability with no caller, and a UI token that is present but not
actually connected.

  * remember-me: the login form must send `remember_me` AND the cookie/service
    must honour it — a checkbox that posts nothing is decoration;
  * email verification: a token model, a service, routes, a link target page
    that works signed-out, and a resend affordance — all four, or the email
    link lands on a 404.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "remember_me_and_email_verification_test.py")
AUTH_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "auth", "application", "auth_service.py")
AUTH_ROUTES = os.path.join(ROOT, "backend", "app", "modules", "auth", "api", "routes.py")
AUTH_SCHEMAS = os.path.join(ROOT, "backend", "app", "modules", "auth", "schemas", "auth.py")
VERIFY_SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "users", "application", "email_verification_service.py"
)
MODELS = os.path.join(ROOT, "backend", "app", "modules", "users", "domain", "models.py")
LOGIN_PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "login", "page.tsx")
REGISTER_PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "register", "page.tsx")
VERIFY_PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "verify-email", "page.tsx")
USE_AUTH = os.path.join(ROOT, "frontend", "hooks", "use-auth.ts")
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

    def read(path: str) -> str:
        return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""

    auth_service = read(AUTH_SERVICE)
    auth_routes = read(AUTH_ROUTES)
    auth_schemas = read(AUTH_SCHEMAS)
    verify_service = read(VERIFY_SERVICE)
    models = read(MODELS)
    login_page = read(LOGIN_PAGE)
    register_page = read(REGISTER_PAGE)
    verify_page = read(VERIFY_PAGE)
    use_auth = read(USE_AUTH)

    # ── Remember me ──────────────────────────────────────────────────────────
    check("login schema accepts remember_me",
          "remember_me" in auth_schemas, "no remember_me on LoginRequest")
    check("the login service honours remember_me",
          "remember_me: bool = False" in auth_service and "remember_me=body.remember_me" in auth_routes,
          "route does not pass remember_me into the service")
    # Both branches must appear in the same expression: the setting alone would
    # also be present if the service used it unconditionally.
    check("the remember window is longer than the default",
          re.search(
              r"REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS[\s\S]{0,120}?else settings\.REFRESH_TOKEN_EXPIRE_DAYS",
              auth_service,
          )
          is not None,
          "the service ignores remember_me when minting the session")
    # The cookie must match the session: a long session behind a short cookie
    # forgets itself. Presence of the words is not enough — the branch has to
    # be in the cookie function itself, which is what the regex pins down.
    check("the refresh cookie honours remember_me",
          re.search(
              r"refresh_days\s*=\s*\(?[\s\S]{0,160}?REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS"
              r"[\s\S]{0,80}?else\s+_settings\.REFRESH_TOKEN_EXPIRE_DAYS",
              auth_routes,
          )
          is not None,
          "cookie lifetime is not derived from remember_me")
    check("the login form sends remember_me",
          "remember_me: rememberMe" in login_page,
          "the checkbox state never reaches login()")
    check("the login hook forwards remember_me",
          "remember_me: credentials.remember_me" in use_auth,
          "use-auth drops remember_me")

    # ── Email verification ───────────────────────────────────────────────────
    check("the token model exists",
          "class EmailVerificationToken" in models, "no EmailVerificationToken model")
    check("the service stores only a hash",
          "def hash_verification_token" in verify_service and "secrets.token_urlsafe" in verify_service,
          "no hashed token issuance")
    check("the service is single-use and address-bound",
          "already_used" in verify_service and "row.email" in verify_service,
          "no single-use/stale guard")
    check("the verify route exists",
          '"/me/email/verify"' in auth_routes, "no verify route")
    check("the resend route exists",
          '"/me/email/resend-verification"' in auth_routes, "no resend route")
    check("registration accepts an email",
          "email: str | None = None" in auth_service and "email=body.email" in auth_routes,
          "register does not take/pass an email")
    check("registration issues a verification link",
          "issue_verification(" in auth_service, "registration never issues verification")
    check("the emailed link lands outside the auth-guarded group",
          "/verify-email?token=" in verify_service,
          "the link points at an auth-guarded route and 404s for signed-out clicks")
    check("the link target page exists",
          os.path.isfile(VERIFY_PAGE), f"missing {VERIFY_PAGE}")
    check("the link target page redeems the token",
          "confirmEmailVerification" in verify_page, "the page never calls the verify endpoint")
    check("the register form offers an email field",
          'id="register-email-input"' in register_page and "email.trim()" in register_page,
          "no email field / it is not sent")
    check("the account screen offers a resend",
          "resendEmailVerification" in read(
              os.path.join(ROOT, "frontend", "components", "account", "account-dashboard.tsx")
          ),
          "no resend affordance on the account screen")

    # ── Live behaviour ───────────────────────────────────────────────────────
    if not os.path.isfile(FIXTURE):
        check("the remember-me/verification fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the remember-me/verification behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: remember-me lengthens only its own session, and registration "
          "email verification is issued, single-use, address-bound, and reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())