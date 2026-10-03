"""The users list filters by role server-side, and a restore view exists.

    python scripts/wp-parity/check_users_role_filter.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "users_role_filter_test.py")
CREATE_FIXTURE = os.path.join(ROOT, ".p1-tests", "users_create_role_test.py")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "users", "page.tsx")
DIALOG = os.path.join(ROOT, "frontend", "components", "admin", "users", "user-dialog.tsx")
CHECK_LINE = re.compile(r"^\d+\.")


def _run_fixture(path: str) -> int:
    try:
        proc = subprocess.run(
            [sys.executable, "-B", path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=200,
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

    # The UI half: the page must send the role to the server, offer the restore
    # view, and let an operator set the role at creation. A server feature with
    # no caller is a backend feature, not a fixed admin screen.
    page = open(PAGE, encoding="utf-8").read() if os.path.isfile(PAGE) else ""
    dialog = open(DIALOG, encoding="utf-8").read() if os.path.isfile(DIALOG) else ""
    check("the users page sends the role to the server",
          'params.set("role"' in page, "role is not sent as a query param")
    check("the users page offers the restore (deleted) view",
          "include_deleted" in page and "showDeleted" in page,
          "no include_deleted wiring")
    check("the users page has a restore action",
          "restoreUser" in page and "RotateCcw" in page,
          "no restore button on a deleted row")
    check("the create dialog can set a role",
          "role_slug" in dialog and "role_slugs" in dialog,
          "no role field on the create form")
    # The role must be sent to the API, not merely held in state.
    check("the create dialog sends the role to the API",
          "role_slugs:" in dialog, "role is collected but not sent")

    for label, path in (
        ("role filter and restore view", FIXTURE),
        ("create-with-role", CREATE_FIXTURE),
    ):
        if not os.path.isfile(path):
            check(f"the {label} fixture exists", False, path)
            continue
        rc = _run_fixture(path)
        check(f"the {label} behaves", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the users list filters by role server-side, offers a restore "
          "view, and assigns a role at creation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())