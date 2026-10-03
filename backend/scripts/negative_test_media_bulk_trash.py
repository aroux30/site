"""Negative test for verify_media_bulk_trash.py — prove the check can fail.

The behaviour this check protects is subtle enough to regress silently: the
per-item savepoint in `bulk_trash` is what stops one referenced file from
taking the other nineteen down with it. Without it the batch still returns a
result — just the wrong one, with every item reported as failed.

    cd backend && PYTHONPATH=. python scripts/negative_test_media_bulk_trash.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
SERVICE = BACKEND / "app" / "modules" / "media" / "application" / "media_service.py"
CHECK = BACKEND / "scripts" / "verify_media_bulk_trash.py"

NL = chr(10)
CRLF = chr(13) + NL

# Assembled from NL rather than written as an escape: a literal newline inside
# a plain string silently fails to match a CRLF file, and the test then blames
# the code for a snippet that never got written.
_SAVEPOINT = "                async with db.begin_nested():" + NL
_SAVEPOINT += "                    await MediaService.delete_asset(db, asset_id, force=force)"

# Removing the savepoint alone does not break the batch: a refused file never
# touched the database, so the transaction stays clean. The savepoint earns
# its place on a failure *after* a write, so this injection removes it and
# makes the first item fail the way a filesystem or constraint error would.
_NO_SAVEPOINT = "                await MediaService.delete_asset(db, asset_id, force=force)" + NL
_NO_SAVEPOINT += "                if asset_id == asset_ids[0]:" + NL
_NO_SAVEPOINT += "                    raise OSError('simulated mid-write failure')"

# (label, snippet that must be present, replacement)
MODES = [
    (
        # The one that matters: without a savepoint per item, a refusal aborts
        # the transaction and the remaining files are reported as failed even
        # though nothing was wrong with them.
        "a mid-batch failure with no savepoint takes the whole batch with it",
        _SAVEPOINT,
        _NO_SAVEPOINT,
    ),
]


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        cwd=str(BACKEND),
        env={**os.environ, "PYTHONPATH": str(BACKEND)},
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    # newline="" so the CRLF survives the read; comparisons run on a flat copy.
    original = SERVICE.read_text(encoding="utf-8", newline="")
    flat = original.replace(CRLF, NL)

    def restore() -> None:
        SERVICE.write_text(original, encoding="utf-8", newline="")

    try:
        code, out = run()
        if code != 0:
            print(
                "FAIL: the check is red on the current tree, so a red result below "
                "would prove nothing."
            )
            print(out[-600:])
            return 2
        print("[0/2] check passes on the current tree")

        label, old, new = MODES[0]
        if old not in flat:
            print(f"FAIL: cannot inject {label!r} — the snippet moved. Update this test.")
            return 2
        SERVICE.write_text(flat.replace(old, new, 1), encoding="utf-8", newline="")
        try:
            code, out = run()
        finally:
            restore()
        if code == 0:
            print(f"FAIL: the check passed while {label}.")
            return 1
        print(f"[1/2] correctly fails on: {label}")

        code, out = run()
        if code != 0:
            print("FAIL: the check is still red after restore.")
            print(out[-400:])
            return 1
        print("[2/2] green again after restore")
    finally:
        restore()

    print("")
    print("PASS: the bulk-delete check fails when the batch can go wrong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
