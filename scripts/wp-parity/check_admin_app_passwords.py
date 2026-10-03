"""An admin can list and revoke another account's application passwords.

    python scripts/wp-parity/check_admin_app_passwords.py

P2 "REST: مدیریت Application Password کاربر دیگر". The gap was the same shape
as the session-management one: self-service existed, admin access did not, so
a leaked-token support case had no operator-side action.

Two things this gate treats as load-bearing rather than nice-to-have:

  * **no secret material crosses the admin API** — the response model must be
    a distinct one that cannot hold the hash or the plaintext, not the
    self-service model with fields removed;
  * **owner-scoped like the self-service path** — the revoke must filter by
    the target user as well as the credential id, so a guessed id from another
    account is a 404, not a revocation.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "admin_app_passwords_test.py")
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "auth", "application",
                       "application_password_service.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "users", "api", "routes.py")
SCHEMAS = os.path.join(ROOT, "backend", "app", "modules", "users", "schemas", "user.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "users.ts")
DIALOG = os.path.join(ROOT, "frontend", "components", "admin", "users",
                      "user-sessions-dialog.tsx")
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
    schemas = read(SCHEMAS)
    client = read(CLIENT)
    dialog = read(DIALOG)

    # ── Backend: admin-scoped service + routes ──────────────────────────────
    check("the admin list service exists",
          "async def list_application_passwords_admin" in service,
          "no admin list function")
    check("the admin revoke service exists",
          "async def revoke_application_password_admin" in service,
          "no admin revoke function")
    check("the admin revoke takes the target explicitly",
          "target_user_id" in service,
          "the admin path derives the user from the session — it is not an admin path")
    check("the admin revoke is scoped by owner as well as id",
          service.count("ApplicationPassword.user_id == target_user_id") >= 2,
          "a guessed credential id from another account would be revocable")
    check("the acting admin is recorded",
          "actor_id=str(actor_id)" in service,
          "a forced revocation would not be attributable")
    check("the admin routes exist",
          '"/admin/users/{user_id}/application-passwords"' in routes
          and '"/admin/users/{user_id}/application-passwords/{app_password_id}"' in routes,
          "one or more admin routes are missing")
    # Permission: the admin list needs users:read, the revoke users:write —
    # NOT auth:self, which is what the self-service routes carry.
    list_block = routes[routes.find('"/admin/users/{user_id}/application-passwords"'):]
    list_block = list_block[:list_block.find("@router", 10)] if "@router" in list_block[10:] else list_block
    check("the admin list requires users:read",
          "users:read" in list_block, "the admin list is not permission-gated")
    revoke_at = routes.find('"/admin/users/{user_id}/application-passwords/{app_password_id}"')
    revoke_block = routes[revoke_at:revoke_at + 1200] if revoke_at != -1 else ""
    check("the admin revoke requires users:write",
          "users:write" in revoke_block, "the admin revoke is not permission-gated")

    # ── The security boundary: a response model that cannot hold secrets ────
    check("a distinct admin response model exists",
          "class ApplicationPasswordAdminResponse" in schemas,
          "no dedicated admin response model")
    model_at = schemas.find("class ApplicationPasswordAdminResponse")
    model_block = schemas[model_at:model_at + 1200] if model_at != -1 else ""
    check("the admin model has no token_hash field",
          "token_hash" not in model_block,
          "the admin response can carry the stored hash")
    check("the admin model has no token field",
          re.search(r"^\s+token\s*:", model_block, re.M) is None,
          "the admin response can carry the one-time plaintext")
    check("the admin routes return that model, not the self-service one",
          "ApplicationPasswordAdminResponse" in list_block
          and "ApplicationPasswordAdminResponse" in revoke_block,
          "an admin route returns the self-service response model")

    # ── Frontend: client + a rendered consumer ──────────────────────────────
    check("the client has both admin methods",
          "listUserApplicationPasswords" in client
          and "revokeUserApplicationPassword" in client,
          "client methods missing")
    check("the dialog calls both",
          "listUserApplicationPasswords(" in dialog
          and "revokeUserApplicationPassword(" in dialog,
          "the dialog does not call the admin methods")
    check("the dialog renders the credential list",
          "appPasswords.map(" in dialog, "the credentials are fetched but not rendered")

    # ── Live behaviour ───────────────────────────────────────────────────────
    if not os.path.isfile(FIXTURE):
        check("the admin app-password fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the admin app-password behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: an admin can list and revoke a target's application passwords, "
          "secrets stay out of the admin API, and revocation is owner-scoped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())