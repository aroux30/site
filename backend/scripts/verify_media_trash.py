"""Live check: the media trash is reversible, and only the trash purges.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "مدیا: سطل زباله". Delete
removed the row and the bytes together, so an image that 20 products
referenced was unrecoverable after one mis-click.

This drives the real service against the live database and a real file on
disk, because the interesting half of a trash is the file: a restore that
brings back a row whose bytes are gone would leave a broken image in the
library. So the sequence asserted here is:

  delete -> the row survives, is hidden from the library, and the bytes survive
  restore -> the asset is back in the library
  trash + purge -> the row and the bytes are gone
  purge on a live asset -> refused, so this cannot be reached by accident

    cd backend && PYTHONPATH=. python scripts/verify_media_trash.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import os
import pkgutil
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.core.exceptions.handlers import NotFoundError, ValidationError  # noqa: E402
from app.modules.media.application.media_service import MediaService  # noqa: E402
from app.modules.media.application.storage_paths import MEDIA_SUBDIR  # noqa: E402


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []

    suffix = uuid.uuid4().hex[:10]
    asset_hex = uuid.uuid4().hex
    asset_id = str(uuid.UUID(hex=asset_hex))
    file_name = "trash-probe-%s.png" % suffix
    # Ask the module that owns the layout where the file goes, instead of
    # guessing. The first version of this probe wrote to `UPLOAD_DIR/<name>`,
    # which is not where the upload writes (`UPLOAD_DIR/media/<name>`), so the
    # restore correctly said the bytes were gone — the probe was wrong, and a
    # probe that lies about the layout cannot verify the thing it exists for.
    from app.core.config import settings as app_settings
    from app.modules.media.application.media_service import MediaService

    base_dir = Path(getattr(app_settings, "UPLOAD_DIR", "media"))
    rel = "%s/%s" % (MEDIA_SUBDIR, file_name)
    url = "/uploads/%s" % rel

    disk = next(
        p
        for p in MediaService._stored_file_candidates(asset_hex, url)
        if p.name == file_name
    )
    disk.parent.mkdir(parents=True, exist_ok=True)
    disk.write_bytes(b"\x89PNG\r\n\x1a\ntrash-probe")
    print("probe file:", disk.resolve())

    async with session() as db:
        try:
            await db.execute(
                text(
                    "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                    "file_size, mime_type, created_at, updated_at) "
                    "VALUES (:id, :name, :path, :url, 24, 'image/png', now(), now())"
                ),
                {"id": asset_id, "name": file_name, "path": rel, "url": url},
            )
            await db.commit()
            uid = uuid.UUID(asset_id)

            # 1. Delete must trash, not destroy.
            await MediaService.delete_asset(db, uid)
            await db.commit()

            row = (
                await db.execute(
                    text("SELECT deleted_at, trashed_at FROM media_assets WHERE id = :id"),
                    {"id": asset_id},
                )
            ).fetchall()
            if not row:
                failures.append("delete removed the row instead of trashing it")
            elif row[0][0] is None:
                failures.append("the row survived but deleted_at was never set")
            elif not disk.exists():
                failures.append("the bytes were deleted by a trash — nothing to restore from")
            else:
                print("PASS: delete trashed the row and kept the bytes on disk")

            # 2. The library must hide it.
            live, live_total = await MediaService.list_assets(db)
            if any(str(a.id) == asset_id for a in live):
                failures.append("a trashed asset still appears in the library listing")
            else:
                print("PASS: the library listing hides the trashed asset")

            trashed, trashed_total = await MediaService.list_trashed(db)
            if not any(str(a.id) == asset_id for a in trashed):
                failures.append("the trash listing does not show the trashed asset")
            else:
                print("PASS: the trash listing shows it (%d item(s))" % trashed_total)

            # 3. Restore must bring it back.
            await MediaService.restore_asset(db, uid)
            await db.commit()
            live, _ = await MediaService.list_assets(db)
            if not any(str(a.id) == asset_id for a in live):
                failures.append("restore did not put the asset back in the library")
            else:
                print("PASS: restore brought the asset back")

            # 4. Purging a live asset must be refused.
            try:
                await MediaService.purge_asset(db, uid)
                failures.append("purge removed a live asset — it should require a trash first")
            except ValidationError:
                print("PASS: purge refuses an asset that is not in the trash")
            await db.rollback()

            # 5. Trash then purge removes both row and bytes.
            await MediaService.trash_asset(db, uid)
            await db.commit()
            await MediaService.purge_asset(db, uid)
            await db.commit()

            left = (
                await db.execute(
                    text("SELECT count(*) FROM media_assets WHERE id = :id"),
                    {"id": asset_id},
                )
            ).scalar()
            if left:
                failures.append("purge left the row behind")
            elif disk.exists():
                failures.append("purge left the bytes behind — the store grows forever")
            else:
                print("PASS: purge removed the row and the bytes")

            # 6. Retention. The scheduled purge must take an old trash entry
            #    and leave a recent one alone — a job that empties the whole
            #    trash would make "restore" a lie the moment it ran.
            # Retention needs a fresh asset: step 5 purged the probe.
            fresh_id = uuid.uuid4()
            await db.execute(
                text(
                    "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                    "file_size, mime_type, created_at, updated_at) "
                    "VALUES (:id, :name, :path, :url, 24, 'image/png', now(), now())"
                ),
                {"id": fresh_id, "name": file_name, "path": rel, "url": url},
            )
            await db.commit()
            await MediaService.trash_asset(db, fresh_id)
            await db.commit()
            old = (
                await db.execute(
                    text(
                        "UPDATE media_assets SET deleted_at = now(), "
                        "trashed_at = now() - interval '45 days' WHERE id = :id"
                    ),
                    {"id": str(fresh_id)},
                )
            ).rowcount
            del old
            await db.commit()
            purged = await MediaService.empty_trash(db, older_than_days=30)
            await db.commit()
            if purged != 1:
                failures.append(
                    "retention purge removed %d item(s), expected the one trashed "
                    "45 days ago" % purged
                )
            else:
                print("PASS: retention purged the entry trashed 45 days ago")

            # A freshly trashed asset must survive a retention run.
            await db.execute(
                text(
                    "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                    "file_size, mime_type, created_at, updated_at, deleted_at, trashed_at) "
                    "VALUES (:id, :name, :path, :url, 1, 'image/png', now(), now(), now(), now())"
                ),
                {"id": str(uuid.uuid4()), "name": file_name, "path": rel, "url": url},
            )
            await db.commit()
            fresh_purged = await MediaService.empty_trash(db, older_than_days=30)
            await db.commit()
            if fresh_purged != 0:
                failures.append(
                    "retention purged %d freshly-trashed item(s); restore would be "
                    "a lie" % fresh_purged
                )
            else:
                print("PASS: retention left the freshly trashed asset alone")

            # 6. Restoring something whose bytes are gone must fail loudly
            #    rather than return a row that would render as a broken image.
            await db.execute(
                text(
                    "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                    "file_size, mime_type, created_at, updated_at, deleted_at) "
                    "VALUES (:id, :name, :path, :url, 1, 'image/png', now(), now(), now())"
                ),
                {"id": str(uuid.uuid4()), "name": file_name, "path": rel, "url": url},
            )
            await db.commit()
            ghost_id = (
                await db.execute(
                    text(
                        "SELECT id FROM media_assets WHERE deleted_at IS NOT NULL "
                        "ORDER BY created_at DESC LIMIT 1"
                    )
                )
            ).scalar()
            try:
                await MediaService.restore_asset(db, uuid.UUID(str(ghost_id)))
                failures.append(
                    "restoring an asset whose file is gone succeeded — the library "
                    "would show a broken image"
                )
            except NotFoundError:
                print("PASS: restore refuses when the bytes are gone")

        finally:
            await db.execute(text("DELETE FROM media_assets WHERE file_name = :n"), {"n": file_name})
            await db.commit()
            if disk.exists():
                disk.unlink()
            print("cleaned up the probe row and file")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the media trash is reversible, and purging is a separate step.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))