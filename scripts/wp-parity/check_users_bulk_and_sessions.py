"""Bulk user operations and admin session management are wired end to end.

    python scripts/wp-parity/check_users_bulk_and_sessions.py

Two features, one shape: a route/service exists AND something calls it. The
recurring failure this guards against is a shipped endpoint with no consumer —
the bulk route and the session dialog each have to be reachable from the admin
users page, not merely present in the API.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "users_bulk_and_sessions_test.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "users", "api", "routes.py")
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "users", "application", "user_service.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "users.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "users", "page.tsx")
DIALOG = os.path.join(ROOT, "frontend", "components", "admin", "users", "user-sessions-dialog.tsx")
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

    routes = read(ROUTES)
    service = read(SERVICE)
    client = read(CLIENT)
    page = read(PAGE)
    dialog = read(DIALOG)

    # ── Backend: the routes and the service they call ────────────────────────
    check("the bulk route exists",
          '"/admin/users/bulk"' in routes, "no /admin/users/bulk route")
    check("the bulk route calls the bulk service",
          "user_service.bulk_users(" in routes, "route does not call bulk_users")
    check("the bulk service re-checks the per-account guard",
          "_check_admin_target_guard" in service and "BULK_USER_ACTIONS" in service,
          "bulk path bypasses the single-account guard")
    check("the admin session list route exists",
          '"/admin/users/{user_id}/sessions"' in routes,
          "no admin session list route")
    check("the admin session revoke route exists",
          '"/admin/users/{user_id}/sessions/{session_id}"' in routes,
          "no admin session revoke route")
    check("the revoke is scoped to the owning user",
          "UserSession.user_id == user_id" in service,
          "revoke is not scoped by owner — cross-account revocation possible")

    # The path must not be /bulk/{action}: it would be shadowed by the
    # single-account /{user_id}/block routes, which match the same shape with
    # user_id="bulk" and reject it as a non-UUID. Match the decorator's own
    # argument, not any prose that mentions the bad path.
    decorated_bulk_paths = re.findall(r'@router\.\w+\(\s*"([^"]*bulk[^"]*)"', routes)
    check("the bulk route is a fixed path, not a shadowed /{action} one",
          bool(decorated_bulk_paths) and all("{" not in p for p in decorated_bulk_paths),
          f"bulk route paths={decorated_bulk_paths}")

    # ── Frontend: a client method AND a caller ───────────────────────────────
    check("the client has a bulk method", "bulkUsers:" in client,
          "no bulkUsers client method")
    check("the client has a session list method", "listUserSessions:" in client,
          "no listUserSessions client method")
    check("the client has a session revoke method", "revokeUserSession:" in client,
          "no revokeUserSession client method")

    # Presence is not wiring. `bulkActions={` also matches `bulkActions={[]}`,
    # so assert the named, non-empty list is actually passed to the table.
    check("the users page is selectable",
          re.search(r"\bselectable\b(?!\s*=)", page) is not None,
          "the list is not markable selectable")
    check("the users page passes a non-empty bulk-action list to the table",
          "bulkActions={bulkActions}" in page
          and re.search(r"const bulkActions:\s*BulkAction<UserItem>\[\]\s*=\s*\[\s*\{", page)
          is not None,
          "bulkActions is present but empty or not passed to the table")
    check("the users page calls bulkUsers",
          "bulkUsers(" in page, "the bulk client method has no caller")
    check("the users page opens the sessions dialog",
          "UserSessionsDialog" in page and "setSessionsTargetId" in page,
          "the sessions dialog is never opened")
    check("the sessions dialog calls the client",
          "listUserSessions(" in dialog and "revokeUserSession(" in dialog,
          "the sessions dialog does not call the client")

    # ── Live behaviour ───────────────────────────────────────────────────────
    if not os.path.isfile(FIXTURE):
        check("the bulk/sessions fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the bulk/sessions behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: bulk user actions and admin session management are wired "
          "end to end and behave.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
