"""Negative tests for the live verification scripts.

A live check that runs against the real database is only evidence if it can go
red. These three are the ones that made claims worth trusting — a reversible
trash, a usage counter that sees product images, a delete that refuses while a
file is in use — so each is exercised against a deliberate break and then
against the restored tree.

    cd backend && PYTHONPATH=. python scripts/negative_test_media_checks.py
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent

SERVICE = BACKEND / "app" / "modules" / "media" / "application" / "media_service.py"
USAGE = BACKEND / "app" / "modules" / "media" / "application" / "usage_service.py"

TRASH = BACKEND / "scripts" / "verify_media_trash.py"
USAGE_CHECK = BACKEND / "scripts" / "verify_media_usage.py"
DELETE_CHECK = BACKEND / "scripts" / "verify_media_delete_guard.py"

# (label, script, file, snippet that must exist, replacement)
MODES = [
    (
        "delete destroys again instead of trashing",
        TRASH,
        SERVICE,
        "        await MediaService.trash_asset(db, asset_id)",
        "        await MediaService._delete_row_and_files(db, asset)",
    ),
    (
        "restore stops checking the disk",
        TRASH,
        SERVICE,
        """        if not MediaService._stored_file_exists(asset):
            raise NotFoundError(
                "MediaAsset",
                f"فایل {asset.file_name} روی دیسک نیست و قابل بازگردانی نیست",
            )
""",
        "",
    ),
    (
        "retention ignores the age window",
        TRASH,
        SERVICE,
        """        stmt = select(MediaAsset).where(MediaAsset.deleted_at.is_not(None))
        if older_than_days is not None:""",
        """        stmt = select(MediaAsset).where(MediaAsset.deleted_at.is_not(None))
        if False:""",
    ),
    (
        "the delete stops refusing a referenced file",
        DELETE_CHECK,
        SERVICE,
        """            usage = await count_media_usage(db, Path(asset.file_url).name)
            if usage.total:
                raise ConflictError(
                    "این فایل هنوز استفاده می‌شود (%s)." % usage.summary()
                )""",
        "            pass",
    ),
    (
        "the product-image column leaves the counter",
        USAGE_CHECK,
        USAGE,
        '    ("product_images", "url"),\n',
        "",
    ),
]


def run(script: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        # The child prints Persian messages; a cp1252 console would raise a
        # UnicodeDecodeError here and hide the exit code we came for.
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=str(BACKEND),
        env={**os.environ, "PYTHONPATH": str(BACKEND)},
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8") for p in (SERVICE, USAGE)}

    def restore() -> None:
        for p, s in originals.items():
            p.write_text(s, encoding="utf-8")

    try:
        for script in (TRASH, USAGE_CHECK, DELETE_CHECK):
            # Restore first, then check. A previous run that died before its
            # finally — a crash, a kill, a decode error — leaves the injected
            # source behind, and without this the test reports the tree as
            # broken and exits before proving anything. It also re-arms the
            # restore below, so the tree ends clean either way.
            restore()
            code, out = run(script)
            if code != 0:
                print(
                    "FAIL: %s is red on the current tree, so a red result below "
                    "would prove nothing.\n%s" % (script.name, out[-600:])
                )
                return 2
        print("[0/%d] all three checks pass on the current tree" % (len(MODES) + 1))

        for i, (label, script, path, old, new) in enumerate(MODES, start=1):
            src = path.read_text(encoding="utf-8")
            if old not in src:
                print("FAIL: cannot inject %r — the snippet moved. Update this test." % label)
                restore()
                return 2
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            try:
                code, out = run(script)
            finally:
                path.write_text(src, encoding="utf-8")
            if code == 0:
                print("FAIL: %s passed while %s." % (script.name, label))
                print(out[-400:])
                return 1
            print("[%d/%d] correctly fails on: %s" % (i, len(MODES) + 1, label))

        for script in (TRASH, USAGE_CHECK, DELETE_CHECK):
            code, out = run(script)
            if code != 0:
                print("FAIL: %s still red after restore.\n%s" % (script.name, out[-400:]))
                return 1
        print("[%d/%d] all three are green again after restore" % (len(MODES) + 1, len(MODES) + 1))
    finally:
        restore()

    print("")
    print("PASS: the live media checks fail on every break they exist to catch.")
    return 0


if __name__ == "__main__":
    importlib.import_module("app")  # fail fast if the backend is not importable
    for _m in pkgutil.walk_packages(["app"], "app."):
        pass
    sys.exit(main())