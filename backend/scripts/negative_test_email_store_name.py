"""Negative test: the email store-name check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The two cases that are the reason this check is per-path rather than per-resolver:

  - one of the four templates going back to the literal. Three of four still
    carry the operator's name, the check reads as green, and one customer's order
    confirmation names a different store than their shipping notification.
  - the generic send path reading the environment again. That is exactly what
    shipped: the resolver existed and worked while three call sites kept reading
    ``SMTP_FROM_NAME``.

    cd backend && PYTHONPATH=. python scripts/negative_test_email_store_name.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_email_store_name.py"
STORE_NAME = (
    BACKEND / "app" / "modules" / "notifications" / "application" / "store_name.py"
)
EMAIL = BACKEND / "app" / "modules" / "notifications" / "application" / "email_service.py"
NOTIFY = (
    BACKEND / "app" / "modules" / "notifications" / "application" / "notification_service.py"
)
TASKS = BACKEND / "app" / "modules" / "notifications" / "application" / "tasks.py"
RULES = BACKEND / "app" / "modules" / "automation" / "application" / "rules_engine.py"
TEMPLATE_SVC = (
    BACKEND
    / "app"
    / "modules"
    / "notifications"
    / "application"
    / "email_template_service.py"
)

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the resolver stops reading the store's own setting",
        STORE_NAME,
        '            name = _name_from_identity(raw)\n            if name:\n                return name',
        "            name = \"\"\n            if name:\n                return name",
        "the resolver returned",
    ),
    (
        "one of the four templates goes back to the literal",
        EMAIL,
        "        \"order_confirmation\": EmailTemplateContent(\n"
        '            subject="سفارش شما با موفقیت ثبت شد — {{order_number}}",\n'
        "            html=_wrap_html(\n"
        "                name,",
        "        \"order_confirmation\": EmailTemplateContent(\n"
        '            subject="سفارش شما با موفقیت ثبت شد — {{order_number}}",\n'
        "            html=_wrap_html(\n"
        '                "فروشگاه اینترنتی",',
        "order_confirmation template's header reads",
    ),
    (
        "the shared resolver is renamed away",
        EMAIL,
        "async def wrap_html_for_store(db: AsyncSession, body_html: str) -> str:",
        "async def _unused_wrap_for_store(db: AsyncSession, body_html: str) -> str:",
        "could not render an email at all",
    ),
    (
        "the notification service reads the environment again",
        NOTIFY,
        "        html = await email_service.wrap_html_for_store(\n            self._db,",
        "        html = email_service._wrap_html(\n"
        '            email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",\n'
        "            self._db,",
        "header reads",
    ),
    (
        "the dispatch task reads the environment again",
        TASKS,
        "                    html = await email_service.wrap_html_for_store(\n                        db,",
        "                    html = email_service._wrap_html(\n"
        '                        email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",\n'
        "                        f\"<p>{notif.body}</p>\".replace(\"\\n\", \"<br>\"),\n"
        "                    )\n"
        "                    _unused = (",
        "header reads",
    ),
    (
        "the automation engine reads the environment again",
        RULES,
        "        rendered_html = await email_service.wrap_html_for_store(\n            db,",
        "        rendered_html = email_service._wrap_html(\n"
        '            email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",\n'
        "            db,",
        "header reads",
    ),
    (
        "the template service grows its own reader again",
        TEMPLATE_SVC,
        "    from app.modules.notifications.application.store_name import resolve_store_name\n\n    return await resolve_store_name(db)",
        '    import json\n\n    from app.modules.settings.application.site_options_service import (\n'
        "        SiteOptionsService,\n    )\n\n"
        '    raw = (await SiteOptionsService.get(db, "store.identity")) or ""\n'
        "    return raw",
        "admin template preview's header reads",
    ),
]


def run_check() -> tuple[int, str]:
    # The child inherits this process's whole environment and only adds
    # PYTHONPATH: a hand-built env drops SystemRoot, and the Windows socket layer
    # then fails to load at import time -- which looks like a broken check rather
    # than a broken environment.
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
    try:
        return _run(saved)
    finally:
        # The outermost restore, and the reason this function is split in two.
        # The per-case `finally` covers an exception raised by the *check*, but a
        # failure before the loop starts -- the baseline run going red, an
        # interrupt, a missing marker -- returns without ever entering it, and
        # left an injected defect on disk. That is how a broken test suite becomes
        # a broken tree: the next run then fails for a reason that has nothing to
        # do with the code it is testing.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    saved: dict[Path, str] = {}
    for _, path, _, _, _ in CASES:
        if path not in saved:
            saved[path] = path.read_text(encoding="utf-8")

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
