"""Privacy email confirmation, ZIP consumer, and the policy-page picker.

    python scripts/wp-parity/check_privacy_email_zip_policy.py

Three items, each with the recurring "route with no consumer" shape:

  * 133 — the emailed confirmation link must be issued by a route AND
    redeemable by the page the email points at, which must itself be reachable
    signed-out (guard + middleware relaxed);
  * 130 — the ZIP route existed with no frontend caller; the client method and
    the download button must both exist and be wired;
  * 132 — the policy option and service existed with no picker; the card must
    call the options client and be mounted on the settings screen.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "privacy_email_confirm_and_policy_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "settings", "application", "privacy_request_service.py"
)
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "settings", "api", "privacy_confirm_routes.py")
API_INIT = os.path.join(ROOT, "backend", "app", "modules", "settings", "api", "__init__.py")
MODELS = os.path.join(ROOT, "backend", "app", "modules", "settings", "domain", "models.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "privacy.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "(account)", "account", "privacy", "page.tsx")
GUARD = os.path.join(ROOT, "frontend", "components", "account", "account-auth-guard.tsx")
MIDDLEWARE = os.path.join(ROOT, "frontend", "middleware.ts")
POLICY_CARD = os.path.join(ROOT, "frontend", "components", "admin", "privacy-policy-card.tsx")
SETTINGS_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "settings", "page.tsx")
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

    service = read(SERVICE)
    routes = read(ROUTES)
    api_init = read(API_INIT)
    models = read(MODELS)
    client = read(CLIENT)
    page = read(PAGE)
    guard = read(GUARD)
    middleware = read(MIDDLEWARE)
    policy_card = read(POLICY_CARD)
    settings_page = read(SETTINGS_PAGE)

    # ── 133: email confirmation for privacy requests ─────────────────────────
    check("the confirm-token columns exist",
          "confirm_token_hash" in models and "confirm_token_expires_at" in models,
          "no token columns on PrivacyRequest")
    check("the service issues an email confirmation",
          "async def issue_email_confirmation" in service,
          "no issue_email_confirmation")
    check("the service redeems a token",
          "async def confirm_by_email_token" in service,
          "no confirm_by_email_token")
    check("the service stores only a hash",
          "_hash_confirm_token" in service and "hashlib.sha256" in service,
          "token is not hashed")
    check("redemption is single-use and expiry-checked",
          "confirm_token_hash = None" in service
          and "confirm_token_expires_at" in service,
          "no consume/expiry guard")
    check("the routes exist",
          "send-email-confirmation" in routes and "confirm-by-email" in routes,
          "routes missing")
    check("the routes are mounted",
          "privacy_confirm_router" in api_init, "router not composed into the package")
    check("the client has both methods",
          "sendPrivacyEmailConfirmation" in client
          and "confirmPrivacyRequestByEmail" in client,
          "client methods missing")
    check("the page redeems the emailed token",
          "privacy_confirm_token" in page and "confirmPrivacyRequestByEmail(" in page,
          "the page never redeems the token it is linked to")
    check("the page offers the email-confirm button",
          "sendPrivacyEmailConfirmation(" in page,
          "no way to request the email link")
    # The link must work signed-out: guard AND middleware both relaxed.
    check("the auth guard lets the token through",
          "privacy_confirm_token" in guard, "guard still bounces token clicks")
    check("the middleware lets the token through",
          "privacy_confirm_token" in middleware, "middleware still bounces token clicks")

    # ── 130: ZIP consumer ────────────────────────────────────────────────────
    check("the client has a ZIP method",
          "fetchPrivacyExportZip" in client and "result.zip" in client,
          "no ZIP client method")
    # The call site, not the definition: `downloadZip` alone also matches
    # `const downloadZip = ...`, which is how a removed button slipped past
    # the first version of this check.
    check("the page offers a ZIP download",
          "fetchPrivacyExportZip(" in page
          and re.search(r"void downloadZip\(item\.id\)", page) is not None,
          "the ZIP client method has no caller")

    # ── 132: policy page picker ──────────────────────────────────────────────
    check("the policy card calls the options client",
          "siteOptionsApi" in policy_card and "privacy.policy_page" in policy_card,
          "the card does not call the options client")
    check("the policy card only offers published public pages",
          'status: "published"' in policy_card and '"public"' in policy_card,
          "the picker can select a page the service will never serve")
    check("the policy card is mounted",
          "<PrivacyPolicyCard" in settings_page, "the card is never rendered")

    # ── Live behaviour ───────────────────────────────────────────────────────
    if not os.path.isfile(FIXTURE):
        check("the privacy email/zip/policy fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the privacy email/zip/policy behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the privacy confirmation email is issued and redeemable, the "
          "ZIP has a caller, and the policy picker is mounted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())