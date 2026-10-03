"""Registration approval is wired end to end.

    python scripts/wp-parity/check_registration_approval.py

P1 "کاربران: تأیید حساب توسط مدیر". The setting existed in spirit (a store
wants to vet signups) but nothing enforced it: registration always issued a
token, so "pending" did not exist. This gate asserts the whole chain — the
setting is read, the flag is set, login is refused with a distinct code, and
the admin has approve/reject actions with a queue filter.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "registration_approval_test.py")
MODELS = os.path.join(ROOT, "backend", "app", "modules", "users", "domain", "models.py")
AUTH_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "auth", "application", "auth_service.py")
AUTH_ROUTES = os.path.join(ROOT, "backend", "app", "modules", "auth", "api", "routes.py")
USER_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "users", "application", "user_service.py")
USER_ROUTES = os.path.join(ROOT, "backend", "app", "modules", "users", "api", "routes.py")
DEFAULTS = os.path.join(ROOT, "backend", "app", "modules", "settings", "application", "default_options.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "users.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "users", "page.tsx")
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
    auth_service = read(AUTH_SERVICE)
    auth_routes = read(AUTH_ROUTES)
    user_service = read(USER_SERVICE)
    user_routes = read(USER_ROUTES)
    defaults = read(DEFAULTS)
    client = read(CLIENT)
    page = read(PAGE)

    check("the pending_approval column exists",
          "pending_approval: Mapped[bool]" in models, "no pending_approval column")
    check("the setting is seeded",
          "registration_approval_required" in defaults,
          "the option is not seeded")
    check("register reads the setting",
          "registration_approval_required" in auth_service,
          "register never reads the approval setting")
    check("register sets the flag on the row",
          "pending_approval=approval_required" in auth_service,
          "the flag is not written at creation")
    check("register withholds tokens for a pending account",
          re.search(r"if approval_required:[\s\S]{0,400}?access_token.{0,20}\"\"", auth_service)
          is not None,
          "a pending account still gets a token pair")
    # Both login paths must refuse a pending account, with a distinct code.
    check("password login refuses a pending account",
          "ACCOUNT_PENDING_APPROVAL" in auth_service, "no pending refusal on login")
    check("the OTP path refuses a pending account",
          auth_service.count("ACCOUNT_PENDING_APPROVAL") >= 2,
          "only one login path checks pending")
    check("the register route does not set cookies for an empty token",
          "if tokens.get(\"access_token\")" in auth_routes,
          "empty-string cookies would be set for a pending signup")

    check("the approve service exists",
          "async def approve_user" in user_service, "no approve_user")
    check("the reject service exists",
          "async def reject_user" in user_service, "no reject_user")
    check("approve/reject are refused for a non-pending account",
          user_service.count("is not awaiting approval") >= 2,
          "a non-pending account would be silently re-decided")
    check("the approve route exists",
          '"/admin/users/{user_id}/approve"' in user_routes, "no approve route")
    check("the reject route exists",
          '"/admin/users/{user_id}/reject"' in user_routes, "no reject route")
    check("the list can filter to pending",
          "pending_approval" in user_routes and "pending_approval=pending_approval" in user_routes,
          "the approval queue has no server-side filter")

    check("the client has approve/reject",
          "approveUser:" in client and "rejectUser:" in client,
          "client methods missing")
    check("the admin page offers approve/reject",
          "decideApproval(" in page
          and re.search(r"void decideApproval\(u\.id, true\)", page) is not None,
          "the admin page never calls approve/reject")
    # The call site, not any mention: the first version matched the word
    # `pending_approval` anywhere on the page, which passed even after the
    # params.set line was removed.
    check("the admin page has a pending queue filter",
          re.search(r'params\.set\("pending_approval"', page) is not None
          and "showPending" in page,
          "no way to find the pending accounts")

    if not os.path.isfile(FIXTURE):
        check("the registration-approval fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the registration-approval behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: a pending signup gets no session, both login paths refuse it "
          "with a distinct code, and approve/reject are reachable from the queue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())