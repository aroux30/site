"""Custom avatar: the upload route exists AND the account area calls it.

    python scripts/wp-parity/check_avatar_upload.py

P1 "کاربران: آواتار سفارشی". The failure shape here was the field existing on
the profile with no way to put a file in it — the media library is admin-gated,
so `avatar_url` could only be filled by pasting a URL. This gate asserts the
route, the customer-scoped (not media:write) guard, and the UI caller.
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "avatar_upload_test.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "auth", "api", "routes.py")
DASHBOARD = os.path.join(ROOT, "frontend", "components", "account", "account-dashboard.tsx")
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
    dashboard = read(DASHBOARD)

    check("the avatar upload route exists",
          '"/me/avatar"' in routes, "no POST /auth/me/avatar")
    # Customer-scoped: must NOT be behind media:write, or the customer cannot
    # reach it (the same reasoning as the return-proof upload). The slice runs
    # from the decorator to the NEXT decorator, so it covers the whole function
    # body — stopping at the first `async def` would cut the body off, which is
    # how the first version of this check reported false negatives.
    avatar_block = ""
    start = routes.find('@router.post(\n    "/me/avatar"')
    if start == -1:
        start = routes.find('"/me/avatar"')
    if start != -1:
        end = routes.find("@router", start + 10)
        avatar_block = routes[start : end if end != -1 else len(routes)]
    # Only the decorator's own dependencies count. The docstring in the body
    # legitimately *mentions* media:write (it explains why this route is not
    # behind it), and a prose match would read as a real dependency.
    decorator = avatar_block.split("async def", 1)[0]
    check("the avatar route is not behind media:write",
          "media:write" not in decorator,
          "the customer upload is gated on the staff permission")
    check("the avatar route caps the upload",
          "CUSTOMER_UPLOAD_MAX_BYTES" in avatar_block,
          "no customer ceiling on the avatar upload")
    check("the avatar route stores the uploaded file",
          "MediaService.upload_file" in avatar_block,
          "the route does not call the media service")
    check("the route points the profile at the file",
          "avatar_url" in avatar_block and "asset.file_url" in avatar_block,
          "the uploaded file is never linked to the profile")

    check("the account area has an avatar file input",
          'type="file"' in dashboard and "uploadAvatar" in dashboard,
          "no avatar file input")
    # The call site, not the definition.
    check("the avatar upload is wired to the API",
          "void uploadAvatar(file)" in dashboard and '"/auth/me/avatar"' in dashboard,
          "the upload handler has no caller / does not call the route")
    check("the avatar renders when set",
          "user?.avatar_url" in dashboard and "<img" in dashboard,
          "the uploaded avatar is never displayed")

    if not os.path.isfile(FIXTURE):
        check("the avatar fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the avatar behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the customer avatar upload route is reachable, scoped and "
          "wired to the account area.")
    return 0


if __name__ == "__main__":
    sys.exit(main())