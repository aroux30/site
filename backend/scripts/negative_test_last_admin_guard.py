"""Negative test: the last-admin check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

Two directions, and the second is the one that matters more:

  - a guard that stops working, so the last admin can be removed
  - a guard that stops *discriminating*, so it refuses everything

The second is a real failure mode and not a hypothetical one. A store that cannot
promote an operator, cannot hire one, and cannot let anyone leave is a store
whose admin area is one mistake away from being unreachable — the guard becomes
the outage. That is why the check asserts both, and why the two-admin case is
staged rather than assumed.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_last_admin_guard.py"
GUARD = BACKEND / "app" / "modules" / "users" / "application" / "last_admin_guard.py"
USERS = BACKEND / "app" / "modules" / "users" / "application" / "user_service.py"
RBAC = BACKEND / "app" / "modules" / "rbac" / "application" / "rbac_service.py"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the count stops excluding the account being removed",
        GUARD,
        "            clauses.append(User.id != excluding_user_id)",
        "            pass",
        "could be blocked",
    ),
    (
        "a deleted account still counts",
        GUARD,
        "        clauses = [User.is_active.is_(True), User.deleted_at.is_(None)]",
        "        clauses = [User.is_active.is_(True)]",
        "a soft-deleted superuser counted as an admin",
    ),
    (
        "the guard refuses unconditionally — the store cannot hire or promote",
        GUARD,
        "    if remaining[\"total\"] > 0:\n        return remaining",
        "    if False:\n        return remaining",
        "refused the operation",
    ),
    (
        # A store whose operators are all role-holders and none is a superuser
        # is a real configuration. Counting only roles there is correct; counting
        # only superusers there refuses every demotion, and the store's own
        # administration becomes the thing that can break it.
        "superusers stop counting, so a role-led store is wrongly locked out",
        GUARD,
        "                            User.is_superuser.is_(True),\n"
        "                            Role.slug.in_(ADMIN_ROLE_SLUGS),",
        "                            Role.slug.in_(ADMIN_ROLE_SLUGS),",
        "a superuser holding no admin role was counted as 0 admins",
    ),
    (
        # The call replaced, not commented out. A `pass` on the line above leaves
        # the real call on the next line, so the guard is still asked and the
        # check still passes — which is the shape of an injection that measures
        # nothing.
        #
        # Reached through `block_user`, not through the guard directly: calling
        # the guard by hand tests the guard, while what ships is the service
        # method wrapping it, and only the real path proves the wrapper kept the
        # call. That distinction is the whole case.
        "the block path stops asking",
        USERS,
        '    await assert_not_last_admin(db, user_id=user_id, operation="block")',
        "    await db.flush()  # the guard was removed from this path",
        "could be blocked",
    ),
    (
        "the delete path stops asking",
        USERS,
        '    await assert_not_last_admin(db, user_id=user_id, operation="delete")',
        "    await db.flush()  # the guard was removed from this path",
        "the last admin could be deleted",
    ),
    (
        "the demotion path stops asking — the quietest lockout of the three",
        RBAC,
        "    await _assert_not_last_admin_after_demotion(db, user_id=user_id, role_ids=role_ids)",
        "    pass  # the guard was removed from this path",
        "the last admin's role could be removed",
    ),
    (
        # The early return is what keeps a *customer* losing a marketing role from
        # being refused. Removing it makes every demotion run the admin check, so
        # a store with one admin can never change anybody's roles at all — the
        # over-refusal that is the more dangerous direction, because it looks like
        # the guard working.
        "demoting a non-admin role is checked as if it were an admin role",
        RBAC,
        "    if not any(slug in ADMIN_ROLE_SLUGS for slug in removing):\n        return",
        "    if False:\n        return",
        "removing an ordinary role was refused",
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
        # The outermost restore. Without it a run that exits before the loop
        # leaves an injected defect on disk — and this check in particular stages
        # itself by deactivating the store's real admins, so a half-finished run
        # is a store left without one.
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