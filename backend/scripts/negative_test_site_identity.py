"""Negative test for verify_site_identity.py — prove the check can fail.

    cd backend && PYTHONPATH=. python scripts/negative_test_site_identity.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
SERVICE = BACKEND / "app" / "modules" / "settings" / "application" / "site_options_service.py"
ROUTES = BACKEND / "app" / "modules" / "blog" / "api" / "routes.py"
CHECK = BACKEND / "scripts" / "verify_site_identity.py"

NL = chr(10)
CRLF = chr(13) + NL

# (label, file, snippet that must be present, replacement)
#
# Two different failures, because they break the gap in different places:
#   1. the write stops working — the setting is a field nobody fills in;
#   2. the write works but no reader sees it — the "stored but decorative"
#      case, which is the shape most of this project's gaps actually take.
_WRITE = "            existing.option_value = value" + NL + "            existing.autoload = autoload"
_NO_WRITE = "            existing.autoload = autoload  # option_value no longer written"

_READ = '        "site_title": await SiteOptionsService.get(db, "blogname") or "وبلاگ",'
_DEAD_READ = '        "site_title": "وبلاگ",  # the setting is no longer read'

MODES = [
    ("the write stops persisting the value", SERVICE, _WRITE, _NO_WRITE),
    ("the feed no longer reads the setting", ROUTES, _READ, _DEAD_READ),
]


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=str(BACKEND),
        env={**os.environ, "PYTHONPATH": str(BACKEND)},
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8", newline="") for p in (SERVICE, ROUTES)}

    def restore() -> None:
        for p, s in originals.items():
            p.write_text(s, encoding="utf-8", newline="")

    try:
        code, out = run()
        if code != 0:
            print(
                "FAIL: the check is red on the current tree, so a red result below "
                "would prove nothing."
            )
            print(out[-600:])
            return 2
        print("[0/%d] check passes on the current tree" % (len(MODES) + 1))

        for i, (label, path, old, new) in enumerate(MODES, start=1):
            raw = originals[path]
            flat = raw.replace(CRLF, NL)
            if old not in flat:
                print(f"FAIL: cannot inject {label!r} — the snippet moved. Update this test.")
                return 2
            path.write_text(flat.replace(old, new, 1), encoding="utf-8", newline="")
            try:
                code, out = run()
            finally:
                restore()
            if code == 0:
                print(f"FAIL: the check passed while {label}.")
                return 1
            print("[%d/%d] correctly fails on: %s" % (i, len(MODES) + 1, label))

        code, out = run()
        if code != 0:
            print("FAIL: the check is still red after restore.")
            print(out[-400:])
            return 1
        print("[%d/%d] green again after restore" % (len(MODES) + 1, len(MODES) + 1))
    finally:
        restore()

    print("")
    print("PASS: the identity check fails when the setting is unwritable or unread.")
    return 0


if __name__ == "__main__":
    sys.exit(main())