"""Negative test: the email store-name guard can actually fail.

A source-reading guard is the shape most likely to be decorative, and this one
has five files to be decorative about, none of them executed. So each link in the
chain is broken in turn.

The case worth the trouble is the last one. A preview that fills
``store_name`` from a hardcoded sample passes the argument check above it — the
name *is* a variable called store_name — and only the separate assertion that it
came from the resolver catches it. That is the same two-layer shape as the
``/server_pagination`` guard, and the reason this one has two assertions where
one would read as enough.

    python scripts/wp-parity/negative_test_email_store_name.py
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

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent; a plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is why this
# script died with "I/O operation on closed file" when it imported a guard
# that did the same thing.

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_email_store_name.py"
BASE = ROOT / "backend" / "app"

RESOLVER = BASE / "modules" / "notifications" / "application" / "store_name.py"
EMAIL = BASE / "modules" / "notifications" / "application" / "email_service.py"
NOTIFY = BASE / "modules" / "notifications" / "application" / "notification_service.py"
TASKS = BASE / "modules" / "notifications" / "application" / "tasks.py"
TEMPLATE_SVC = BASE / "modules" / "notifications" / "application" / "email_template_service.py"
RULES = BASE / "modules" / "automation" / "application" / "rules_engine.py"
ADMIN = BASE / "modules" / "settings" / "api" / "routes.py"

# (name, file, original, broken, expected substring in the guard's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the resolver stops existing",
        RESOLVER,
        "async def resolve_store_name(db: AsyncSession | None = None) -> str:",
        "async def _unused_store_name(db: AsyncSession | None = None) -> str:",
        "no resolve_store_name",
    ),
    (
        "the resolver stops reading the store's own option",
        RESOLVER,
        'STORE_IDENTITY_OPTION = "store.identity"',
        'STORE_IDENTITY_OPTION = "store.branding"',
        "no longer reads 'store.identity'",
    ),
    (
        "the resolver loses its site-title fallback",
        RESOLVER,
        'BLOGNAME_OPTION = "blogname"',
        'BLOGNAME_OPTION = "site_title"',
        "no longer reads 'blogname'",
    ),
    (
        "the resolver has no environment fallback",
        RESOLVER,
        "        return (get_settings().SMTP_FROM_NAME or \"\").strip() or DEFAULT_STORE_NAME",
        "        return DEFAULT_STORE_NAME",
        "no environment fallback",
    ),
    (
        "the notification service goes back to the SMTP config",
        NOTIFY,
        "        html = await email_service.wrap_html_for_store(\n            self._db,",
        "        html = email_service._wrap_html(\n"
        '            email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",\n'
        "            f\"<p>{body}</p>\".replace(\"\\n\", \"<br>\"),\n"
        "        )",
        "renders an email header from the SMTP config",
    ),
    (
        "the automation engine goes back to the SMTP config",
        RULES,
        "        rendered_html = await email_service.wrap_html_for_store(\n            db,",
        "        rendered_html = email_service._wrap_html(\n"
        '            email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",\n'
        '            f"<p>{rendered_text}</p>".replace("\\n", "<br>"),\n'
        "        )",
        "renders an email header from the SMTP config",
    ),
    (
        "the dispatch task goes back to the SMTP config",
        TASKS,
        "                    html = await email_service.wrap_html_for_store(\n                        db,",
        "                    html = email_service._wrap_html(\n"
        '                        email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",\n'
        '                        f"<p>{notif.body}</p>".replace("\\n", "<br>"),\n'
        "                    )",
        "renders an email header from the SMTP config",
    ),
    (
        "the shared helper disappears",
        EMAIL,
        "async def wrap_html_for_store(db: AsyncSession, body_html: str) -> str:",
        "async def _unused_wrap_for_store(db: AsyncSession, body_html: str) -> str:",
        "no wrap_html_for_store",
    ),
    (
        # Replaced whole, not line-edited. The guard's assertion is that this
        # function's *body* delegates; editing only its return leaves the import
        # of resolve_store_name in the module, and a name search over the whole
        # file is satisfied by an import nobody calls. Which is precisely the
        # "a route without a consumer is a gap" shape, in a module.
        "the template service grows its own reader again",
        TEMPLATE_SVC,
        "    from app.modules.notifications.application.store_name import resolve_store_name\n\n    return await resolve_store_name(db)",
        '    raw = (await SiteOptionsService.get(db, "store.identity")) or ""\n    return raw',
        "delegating to resolve_store_name",
    ),
    (
        # The two-layer case. The argument check above sees a variable called
        # store_name and is satisfied; only the assertion about where it came
        # from catches this.
        "the admin preview's store name is a hardcoded sample again",
        TEMPLATE_SVC,
        '            "store_name": await _operator_store_name(db),',
        '            "store_name": "فروشگاه نمونه",',
        "rather than the resolved name",
    ),
]


def run_guard() -> tuple[int, str]:
    # A subprocess, not an import: this script and the guard both rebind
    # sys.stdout to a fresh TextIOWrapper at import time, and the two wrappers
    # share a buffer, so importing the guard closes the stream this script is
    # still printing to.
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
    print("PASS: every link in this chain can break, and the guard notices each one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
