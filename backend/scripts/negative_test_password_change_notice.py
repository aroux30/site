"""Negative test: the password-change notice check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The two worth the trouble are the timestamp and the rollback:

  - stamping ``updated_at`` instead of the rotation's own column produces a
    notice that reads correctly on the day it is sent and wrongly forever after,
    because any later profile edit moves the value a reader would point at
  - letting the notice's exception escape rolls back a rotation that already
    happened, leaving the customer holding a password the server no longer has

    cd backend && PYTHONPATH=. python scripts/negative_test_password_change_notice.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_password_change_notice.py"
AUTH = BACKEND / "app" / "modules" / "auth" / "application" / "auth_service.py"
SERVICE = (
    BACKEND / "app" / "modules" / "auth" / "application" / "registration_email_service.py"
)
MODEL = BACKEND / "app" / "modules" / "users" / "domain" / "models.py"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the rotation stamps updated_at instead of its own column",
        AUTH,
        "    user.password_changed_at = datetime.now(UTC)",
        "    user.updated_at = datetime.now(UTC)",
        "left password_changed_at NULL",
    ),
    (
        "the notice is reported as sent with no recipient",
        SERVICE,
        '        if not user.email:\n            logger.info(\n                "password_changed_notice_skipped_no_recipient", user_id=str(user.id)\n            )\n            return False',
        '        if not user.email:\n            logger.info(\n                "password_changed_notice_skipped_no_recipient", user_id=str(user.id)\n            )\n            return True',
        "was reported as sent for an account with no address",
    ),
    (
        "a mail outage escapes and fails the whole request",
        AUTH,
        "    except Exception as exc:  # noqa: BLE001 — a rotation never fails on its mail\n        await logger.awarning(\"password_change_notice_failed\", error=str(exc))",
        "    except Exception:  # noqa: BLE001\n        raise",
        "failed the change-password request outright",
    ),
    (
        "the notice carries a link, which makes it a phishing target",
        SERVICE,
        '                    "<p>زمان: <code>%s</code></p>"',
        '                    "<p>زمان: <code>%s</code></p>"\n'
        '                    "<p><a href=\\"%s\\">بازیابی رمز عبور</a></p>"',
        "carries a link",
    ),
    (
        "change_password stops calling the notice",
        AUTH,
        "        noticed = await RegistrationEmailService.send_password_changed_notice(\n            db, user_id=user_id\n        )",
        "        noticed = False  # send_password_changed_notice(db, user_id=user_id)",
        "does not call the notice",
    ),
    (
        # The selector that decides what time the notice names. With the rotation
        # stamp ignored, every notice is dated to the account's last update —
        # which is right by accident on the day a profile is touched and wrong
        # forever, and the recipient cannot tell which they are looking at.
        "the notice ignores the rotation's own timestamp",
        SERVICE,
        "    stamp = getattr(user, \"password_changed_at\", None)\n    if stamp is not None:\n        return stamp, True",
        "    stamp = None\n    if stamp is not None:\n        return stamp, True",
        "reports something other than when the password changed",
    ),
    (
        # The other half of the same function: with the flag pinned to True, an
        # account that has never rotated reports a rotation time, and its notice
        # claims a password change that never happened. Nothing raises and the
        # mail is delivered — the only wrong thing is what it says.
        "an account that never rotated is reported as if it had",
        SERVICE,
        '    return getattr(user, \"updated_at\", None), False',
        '    return getattr(user, \"updated_at\", None), True',
        "reports a rotation time",
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
        # The outermost restore, so a run that exits before the loop cannot leave
        # an injected defect on disk and make the next run fail for an unrelated
        # reason.
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