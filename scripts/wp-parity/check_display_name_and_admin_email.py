"""Display name and the admin-email change/review flow are wired end to end.

    python scripts/wp-parity/check_display_name_and_admin_email.py

Both features have the two failure shapes this project keeps meeting:

  * a server field with no consumer — display_name must reach the profile form
    AND come back through /auth/me, or it is a column nobody can set;
  * a route with no caller — the admin-email endpoints must be called by a card
    that is actually mounted on the settings screen, and the confirmation link
    must be redeemable from the page it points at.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "display_name_and_admin_email_test.py")
MODELS = os.path.join(ROOT, "backend", "app", "modules", "users", "domain", "models.py")
AUTH_SCHEMAS = os.path.join(ROOT, "backend", "app", "modules", "auth", "schemas", "auth.py")
AUTH_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "auth", "application", "auth_service.py")
ADMIN_EMAIL_SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "settings", "application", "admin_email_service.py"
)
ADMIN_EMAIL_ROUTES = os.path.join(
    ROOT, "backend", "app", "modules", "settings", "api", "admin_email_routes.py"
)
SETTINGS_API_INIT = os.path.join(ROOT, "backend", "app", "modules", "settings", "api", "__init__.py")
SETTINGS_CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "settings.ts")
DASHBOARD = os.path.join(ROOT, "frontend", "components", "account", "account-dashboard.tsx")
CARD = os.path.join(ROOT, "frontend", "components", "admin", "admin-email-card.tsx")
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

    models = read(MODELS)
    auth_schemas = read(AUTH_SCHEMAS)
    auth_service = read(AUTH_SERVICE)
    admin_email_service = read(ADMIN_EMAIL_SERVICE)
    admin_email_routes = read(ADMIN_EMAIL_ROUTES)
    settings_api_init = read(SETTINGS_API_INIT)
    settings_client = read(SETTINGS_CLIENT)
    dashboard = read(DASHBOARD)
    card = read(CARD)
    settings_page = read(SETTINGS_PAGE)

    # ── Display name ─────────────────────────────────────────────────────────
    check("the display_name column exists",
          "display_name: Mapped[str | None]" in models, "no display_name column")
    check("the update schema accepts it",
          "display_name" in auth_schemas, "no display_name on the update schema")
    check("the response schema returns it",
          auth_schemas.count("display_name") >= 2,
          "display_name missing from the response schema")
    check("the service writes it",
          '"display_name"' in auth_service and "profile_keys" in auth_service,
          "the update path does not carry display_name")
    # Empty must normalise to NULL so the first+last fallback fires.
    check("an empty display name is normalised to NULL",
          'profile_fields.get("display_name") == ""' in auth_service
          and 'profile_fields["display_name"] = None' in auth_service,
          "empty string would be stored instead of NULL")
    check("the profile form has a display-name input",
          'id="displayName"' in dashboard and "display_name" in dashboard,
          "no display-name field on the account profile")

    # ── Admin email ──────────────────────────────────────────────────────────
    check("the admin-email service exists",
          "async def request_admin_email_change" in admin_email_service
          and "async def confirm_admin_email_change" in admin_email_service,
          "missing service functions")
    check("the proposal does NOT write admin_email directly",
          "PENDING_ADMIN_EMAIL_OPTION" in admin_email_service
          and re.search(
              r"async def request_admin_email_change[\s\S]{0,4000}?SiteOptionsService\.set\(\s*db,\s*ADMIN_EMAIL_OPTION",
              admin_email_service,
          )
          is None,
          "request path writes the live admin_email option")
    check("the confirmation moves admin_email",
          "SiteOptionsService.set(db, ADMIN_EMAIL_OPTION, pending)" in admin_email_service,
          "confirmation does not apply the pending address")
    check("the review path records without changing the address",
          "async def confirm_current_admin_email" in admin_email_service
          and "ADMIN_EMAIL_CONFIRMED_AT_OPTION" in admin_email_service,
          "no non-mutating review path")
    check("the routes are mounted",
          "admin_router" in settings_api_init and "admin_email_routes" in settings_api_init,
          "admin-email router is not composed into the package")
    check("the routes exist with the settings prefix",
          "/settings/admin/admin-email" in admin_email_routes,
          "no /settings/admin/admin-email route")
    check("the client has the methods",
          "adminEmailApi" in settings_client
          and "requestChange" in settings_client
          and "confirmCurrent" in settings_client,
          "no admin-email client methods")
    check("the card calls the client",
          "adminEmailApi.status(" in card and "adminEmailApi.requestChange(" in card,
          "the card does not call the client")
    check("the card redeems the emailed token",
          "admin_email_token" in card and "adminEmailApi.confirm(" in card,
          "the confirmation link is not redeemable from the page it points at")
    check("the card is mounted on the settings screen",
          "AdminEmailCard" in settings_page and "<AdminEmailCard" in settings_page,
          "the card exists but is never rendered")

    # ── Live behaviour ───────────────────────────────────────────────────────
    if not os.path.isfile(FIXTURE):
        check("the display-name/admin-email fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the display-name/admin-email behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: display_name stores/clears with the fallback intact, and the "
          "admin email moves only on token redemption with a working review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())