"""Negative test: the admin-client reachability guard can actually fail.

A reachability guard is the easiest kind to write and the easiest to make
decorative: a name-search that finds the symbol in the file that defines it
reports green forever, whether or not any UI calls it. So each case breaks the
*consumer* rather than the client, which is the shape this guard exists to catch.

    python scripts/wp-parity/negative_test_admin_api_clients_are_called.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import io
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_admin_api_clients_are_called.py"
EDITOR = ROOT / "frontend" / "components" / "admin" / "users" / "user-roles-editor.tsx"
DIALOG = ROOT / "frontend" / "components" / "admin" / "users" / "user-dialog.tsx"
CLIENT = ROOT / "frontend" / "lib" / "api" / "rbac.ts"

# (name, file, original, broken, expected substring in the guard's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the assign call is replaced by a comment naming it",
        EDITOR,
        "        await rbacApi.assignUserRoles(userId, [role.id]);",
        "        // await rbacApi.assignUserRoles(userId, [role.id]);",
        "has no call under",
    ),
    (
        "the remove call is replaced by a comment naming it",
        EDITOR,
        "        await rbacApi.removeUserRoles(userId, [role.id]);",
        "        // await rbacApi.removeUserRoles(userId, [role.id]);",
        "has no call under",
    ),
    (
        "the roles are never read back",
        EDITOR,
        "        rbacApi.getUserRoles(userId),",
        "        Promise.resolve({ user_id: String(userId), roles: [] }),",
        "has no call under",
    ),
    (
        "the editor is deleted from the dialog's tree",
        DIALOG,
        "              <UserRolesEditor userId={user.id} />\n",
        "",
        "is not rendered by any admin screen",
    ),
]


def run_guard() -> tuple[int, str]:
    # A subprocess, not an import: both scripts rebind sys.stdout at import time
    # and share a buffer, so importing closes the stream this one prints to.
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
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
        # The outermost restore, so a run that exits early — the baseline going
        # red, an interrupt, a missing marker — cannot leave an injected defect
        # on disk. A broken negative test that breaks the tree makes every later
        # run fail for a reason unrelated to the code it is testing.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    print("baseline (unbroken tree):")
    code, out = run_guard()
    if code != 0:
        print(out)
        print(
            "FAIL: the guard is not green on the unbroken tree, so a red run below "
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
            code, out = run_guard()
        finally:
            path.write_text(source, encoding="utf-8")

        if code == 0:
            failures.append("%s: the guard still passed" % name)
            print("  FAIL %s -- the guard still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the guard went red, but not for this reason -- expected %r in "
                "the output" % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason" % name)
            print("    " + out.strip().replace("\n", "\n    "))
        else:
            print("  PASS %s -> guard went red for the right reason" % name)

    code, out = run_guard()
    if code != 0:
        print(out)
        failures.append("the guard is red again after restoring every file")
    else:
        print("")
        print("PASS: the tree is green again after every injection was reverted.")

    if failures:
        print("")
        for f in failures:
            print("FAIL: %s" % f)
        return 1
    print("")
    print("PASS: every assertion in this guard can fail, for its own reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())