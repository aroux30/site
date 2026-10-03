"""Negative test for check_store_identity_reaches.py — prove the guard can fail.

The gap this guard covers is a chain, so each mode breaks one link and the
rest are left intact: the endpoint stops exposing the name, the emails stop
resolving it, the templates print the placeholder again, or the storefront
goes back to a hardcoded title.

    python scripts/wp-parity/negative_test_store_identity_reaches.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import io
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_store_identity_reaches.py"

BRANDING_ROUTE = ROOT / "backend" / "app" / "modules" / "settings" / "api" / "routes.py"
EMAIL_SERVICE = (
    ROOT / "backend" / "app" / "modules" / "notifications" / "application" / "email_service.py"
)
LAYOUT = ROOT / "frontend" / "app" / "layout.tsx"
HEADER = ROOT / "frontend" / "components" / "layout" / "header.tsx"
SITE_CARD = ROOT / "frontend" / "components" / "admin" / "site-identity-card.tsx"

NL = chr(10)
CRLF = chr(13) + NL
# The literal the built-in email templates used to print everywhere.
TEMPLATE_PLACEHOLDER = "".join(chr(c) for c in (0x0641, 0x0631, 0x0648, 0x0634, 0x06af, 0x0627, 0x0647, 0x20, 0x0627, 0x06cc, 0x0646, 0x062a, 0x0631, 0x0646, 0x062a, 0x06cc))

# (label, file, snippet that must be present, replacement)
MODES = [
    (
        "the public endpoint stops exposing the name",
        BRANDING_ROUTE,
        '        "store_name": await _public_store_name(db),' + NL,
        "",
    ),
    (
        "the endpoint no longer reads the setting the admin writes",
        BRANDING_ROUTE,
        'raw = (await SiteOptionsService.get(db, "store.identity")) or ""',
        'raw = ""  # the option blob is no longer read',
    ),
    (
        "the templates print the placeholder again",
        EMAIL_SERVICE,
        "_wrap_html(" + NL + "                name,",
        # The placeholder itself, which is what "the templates print the
        # placeholder again" means. An earlier version substituted an unrelated
        # string, so nothing in the file carried the literal and the guard had
        # nothing to catch — the test passed because the break was not a break.
        # Built from code points: a Persian literal in a Python string here is
        # written through a patch, which turns \u escapes into the characters
        # but leaves the surrounding quoting fragile. This is unambiguous.
        "_wrap_html(" + NL + '                "' + TEMPLATE_PLACEHOLDER + '",',
    ),
    (
        "the template lookup stops passing the resolved name",
        EMAIL_SERVICE.with_name("email_template_service.py"),
        "default_email_templates(await _operator_store_name(db)).get(name)",
        "default_email_templates().get(name)",
    ),
    (
        "the storefront title is hardcoded again",
        LAYOUT,
        "  const name = branding.store_name || \"فروشگاه آنلاین\";",
        '  const name = "فروشگاه آنلاین";',
    ),
    (
        "the settings screen cannot set the front page",
        SITE_CARD,
        '      [KEYS.pageOnFront, showOnFront === "page" ? pageOnFront : ""],',
        "",
    ),
    (
        "the header shows a hardcoded brand",
        HEADER,
        "{siteName}",
        "فروشگاه آنلاین",
    ),
]


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        capture_output=True,
        text=True,
        encoding="utf-8",  # the guard prints Persian
        errors="replace",
        timeout=300,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8", newline="") for p in {m[1] for m in MODES}}

    def restore() -> None:
        for p, s in originals.items():
            p.write_text(s, encoding="utf-8", newline="")

    try:
        code, out = run()
        if code != 0:
            print(
                "FAIL: the guard is red on the current tree, so a red result below "
                "would prove nothing.\n%s" % out[-600:]
            )
            return 2
        print("[0/%d] guard passes on the current tree" % (len(MODES) + 1))

        for i, (label, path, old, new) in enumerate(MODES, start=1):
            raw = originals[path]
            flat = raw.replace(CRLF, NL)
            if old not in flat:
                print("FAIL: cannot inject %r — the snippet moved. Update this test." % label)
                return 2
            # Every occurrence, not the first: the wrapper is shared by four
            # templates, so replacing one left three correct ones and the guard
            # had nothing to report.
            written = flat.replace(old, new) if old in flat else flat.replace(old, new, 1)
            path.write_text(written, encoding="utf-8", newline="")
            try:
                code, out = run()
            finally:
                restore()
            if code == 0:
                print("FAIL: guard passed while %s." % label)
                return 1
            print("[%d/%d] correctly fails on: %s" % (i, len(MODES) + 1, label))

        code, out = run()
        if code != 0:
            print("FAIL: guard still red after restore.\n%s" % out[-400:])
            return 1
        print("[%d/%d] green again after restore" % (len(MODES) + 1, len(MODES) + 1))
    finally:
        restore()

    print("")
    print("PASS: the guard catches a break at every link of the chain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())