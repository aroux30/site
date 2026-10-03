"""Negative test: the registration-email check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The case worth the trouble is the outage one, and it is asymmetric. Making the
welcome *fail to send* changes nothing an operator can see — the account exists
either way, which is the intended behaviour. What is dangerous is the opposite:
the mail step raising and taking the token pair with it. A check that only
asserted "a mail was sent" would pass on the broken version, because the broken
version sends no mail and the exception happens after.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_registration_emails.py"
AUTH = BACKEND / "app" / "modules" / "auth" / "application" / "auth_service.py"
SERVICE = (
    BACKEND / "app" / "modules" / "auth" / "application" / "registration_email_service.py"
)

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the welcome is reported as sent with no recipient",
        SERVICE,
        "        if not user.email:\n            logger.info(\"welcome_email_skipped_no_recipient\", user_id=str(user.id))\n            return False",
        "        if not user.email:\n            logger.info(\"welcome_email_skipped_no_recipient\", user_id=str(user.id))\n            return True",
        "was reported as sent for an account with no address",
    ),
    (
        # The recipient is hardcoded, so the notice goes to an address nobody
        # owns. Every observable signal stays green — a real mail is produced, the
        # log says sent — and only the address is wrong. A check on "did it send"
        # passes on this; only a check on where the address came from catches it.
        "the notice is delivered to a hardcoded address",
        SERVICE,
        '    raw = await SiteOptionsService.get(db, "admin_email")\n    if raw and "@" in raw:\n        return raw.strip()',
        '    return "nobody@example.invalid"',
        "not the address configured in",
    ),
    (
        "the store's admin address is read from a setting of its own",
        SERVICE,
        '    raw = await SiteOptionsService.get(db, "admin_email")',
        '    raw = await SiteOptionsService.get(db, "smtp_from_address")',
        "the admin signup notice was not attempted",
    ),
    (
        "a mail outage costs the customer their token pair",
        AUTH,
        "    except Exception as exc:  # noqa: BLE001 — a signup never fails on its mail\n        await logger.awarning(\"registration_emails_failed\", error=str(exc))",
        "    except Exception:  # noqa: BLE001\n        raise",
        "a mail outage took the signup with it",
    ),
    (
        "the welcome stops being sent at all",
        SERVICE,
        "        if not user.email:",
        "        if True:",
        "no welcome was attempted",
    ),
    (
        "register stops calling the service",
        AUTH,
        "        sent = await send_registration_emails(db, user_id=user.id)",
        "        sent = {}  # send_registration_emails(db, user_id=user.id)",
        "register does not call the email service",
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