"""Negative test for check_sitemap_archives.py — prove the guard can fail.

A section that is collected but not emitted is invisible without this: the
backend logs "sitemap_section_skipped" and returns an empty list, so the payload
is well-formed and the page loads, just without the archives.

    python scripts/wp-parity/negative_test_sitemap_archives.py
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
GUARD = ROOT / "scripts" / "wp-parity" / "check_sitemap_archives.py"
SERVICE = ROOT / "backend" / "app" / "modules" / "content" / "application" / "sitemap_service.py"
SCHEMA = ROOT / "backend" / "app" / "modules" / "content" / "schemas" / "content.py"
SITEMAP = ROOT / "frontend" / "app" / "sitemap.ts"

NL = chr(10)
CRLF = chr(13) + NL

# (label, file, snippet, replacement)
MODES = [
    (
        "a section leaves the collection table",
        SERVICE,
        '    ("blog_authors", _collect_authors, "weekly", "0.5"),' + NL,
        "",
    ),
    (
        "the schema demands a slug again, so archive rows cannot be built",
        SCHEMA,
        "    slug: str | None = None" + NL,
        "    slug: str" + NL,
    ),
    (
        "the storefront stops emitting the routes",
        SITEMAP,
        "    ...authorRoutes," + NL,
        "",
    ),
]


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        capture_output=True,
        text=True,
        encoding="utf-8",
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
            flat = originals[path].replace(CRLF, NL)
            if old not in flat:
                print("FAIL: cannot inject %r — the snippet moved. Update this test." % label)
                return 2
            path.write_text(flat.replace(old, new, 1), encoding="utf-8", newline="")
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
    print("PASS: the guard catches an archive section dropped at any link.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
