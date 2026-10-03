"""Negative test: the admin password-reset check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The case worth the trouble is the delegation one. Reimplementing the reset is
the tempting shortcut — the function is short, and everything it needs is on the
user row — and it passes every assertion about tokens and honest reporting. What
it breaks is the *next* change to the shared rules: the admin path keeps its own
copy and drifts. That is why the check looks at the delegation specifically
rather than only at the outcome.

    cd backend && PYTHONPATH=. python scripts/negative_test_admin_password_reset.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_admin_password_reset.py"
AUTH = BACKEND / "app" / "modules" / "auth" / "application" / "auth_service.py"
SERVICE = BACKEND / "app" / "modules" / "users" / "application" / "user_service.py"
ROUTES = BACKEND / "app" / "modules" / "users" / "api" / "routes.py"
PAGE = BACKEND.parent / "frontend" / "app" / "admin" / "users" / "page.tsx"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the reset reports success without issuing anything",
        AUTH,
        "    if not user.email or not user.password_hash:",
        "    if False:",
        "reported a reset as sent",
    ),
    (
        "an account with no address is told the reset went out",
        AUTH,
        "    if not user.email or not user.password_hash:",
        "    if False:",
        "reported a reset as sent",
    ),
    (
        "the admin path stops delegating and reimplements the rules",
        AUTH,
        "    await request_password_reset(\n        db, email=user.email, ip_address=ip_address, user_agent=\"admin-panel\"\n    )",
        "    db.add(\n        PasswordResetToken(\n            user_id=user.id,\n            token_hash=user.password_hash or \"probe\",\n            expires_at=datetime.now(UTC) + timedelta(minutes=30),\n        )\n    )",
        "does not delegate to request_password_reset",
    ),
    (
        # The lookup has to return the row. A projection returns a scalar, so
        # `user.email` raises AttributeError — and an exception here reads as "the
        # reset broke" rather than as the vacuous guard it is, because the column
        # is never read at all. Removed whole rather than projected, so the
        # failure is the honest one: the route's own 404 path.
        "the user lookup stops returning the row itself",
        SERVICE,
        "    result = await db.execute(select(User).where(User.id == user_id))\n    return result.scalar_one_or_none()",
        "    return None",
        "the probe user vanished before the reset",
    ),
    (
        "the route is gone",
        ROUTES,
        '@router.post(\n    "/admin/users/{user_id}/password-reset",',
        '@router.post(\n    "/admin/users/{user_id}/send-link",',
        "no admin password-reset route is registered",
    ),
    (
        "the button disappears from the users page",
        PAGE,
        "            onClick={() => void sendPasswordReset(u.id)}",
        "            onClick={() => undefined}",
        "no control calls it",
    ),
]


def run_check() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": "."},
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    saved: dict[Path, str] = {}
    for _, path, _, _, _ in CASES:
        if path not in saved:
            saved[path] = path.read_text(encoding="utf-8")

    try:
        return _run(saved)
    finally:
        # The outermost restore. The per-case `finally` covers a check that
        # fails; this covers a run that exits before the loop — and without it a
        # broken negative test leaves an injected defect on disk, which makes
        # every later run fail for an unrelated reason.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    print("baseline (unbroken tree):")
    code, out = run_check()
    if code != 0:
        print(out)
        print(
            "FAIL: the check does not pass on the unbroken tree, so a red run below "
            "would mean nothing"
        )
        return 1
    print("  PASS as expected")
    print("")

    failures: list[str] = []
    for name, path, original, broken, expected in CASES:
        source = saved[path]
        if original not in source:
            failures.append(
                "%s: the marker to break is not in %s, so this case would prove "
                "nothing -- update it for the current source" % (name, path.name)
            )
            continue
        path.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_check()
        finally:
            path.write_text(source, encoding="utf-8")

        if code == 0:
            failures.append("%s: the check still passed" % name)
            print("  FAIL %s -- the check still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the check went red, but not for this reason -- expected %r in "
                "the output" % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason" % name)
            print("    " + out.strip().replace("\n", "\n    "))
        else:
            print("  PASS %s -> check went red for the right reason" % name)

    code, out = run_check()
    if code != 0:
        print(out)
        failures.append("the check is red again after restoring every file")
    else:
        print("")
        print("PASS: the tree is green again after every injection was reverted.")

    if failures:
        print("")
        for f in failures:
            print("FAIL: %s" % f)
        return 1
    print("")
    print("PASS: every defect this check targets makes it go red, for its own reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())