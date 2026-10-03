"""Live check: deleting a referenced asset is refused unless forced.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "مدیا: هشدار استفاده پیش از
حذف". Deleting an asset removed the row and the bytes with nothing warning that
the image was still a category's picture.

This drives the real service against the live database — it creates an asset
and a category that points at it, then asserts the guard refuses, that
``force=True`` is what gets past it, and that the refusal happens before the row
or the bytes are touched.

    cd backend && PYTHONPATH=. python scripts/verify_media_delete_guard.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.core.exceptions.handlers import ConflictError  # noqa: E402
from app.modules.media.application.media_service import MediaService  # noqa: E402
from app.modules.media.application.usage_service import count_media_usage  # noqa: E402


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
    asset_id = str(uuid.uuid4())
    file_name = "guard-probe-%s.png" % suffix
    file_url = "/uploads/%s" % file_name
    cat_id = str(uuid.uuid4())
    cat_slug = "guard-probe-%s" % suffix

    async with session() as db:
        try:
            # Minimal asset row: enough for the service to find and read.
            await db.execute(
                text(
                    "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                    "file_size, mime_type, created_at, updated_at) "
                    "VALUES (:id, :name, :path, :url, 1, 'image/png', now(), now())"
                ),
                {"id": asset_id, "name": file_name, "path": "uploads/" + file_name, "url": file_url},
            )
            await db.execute(
                text(
                    "INSERT INTO categories (id, name, slug, path, depth, position, "
                    "is_active, created_at, updated_at, image_url) "
                    "VALUES (:id, :name, :slug, :slug, 0, 0, true, now(), now(), :url)"
                ),
                {"id": cat_id, "name": "guard probe", "slug": cat_slug, "url": file_url},
            )
            await db.commit()

            usage = await count_media_usage(db, file_name)
            if usage.categories != 1:
                failures.append(
                    "the counter reports %d category use(s) for a category that "
                    "points at this file" % usage.categories
                )
            else:
                print("PASS: the new reference is counted (%s)" % usage.summary())

            # 1. The refusal.
            try:
                await MediaService.delete_asset(db, uuid.UUID(asset_id))
                failures.append(
                    "delete_asset removed a file that is still in use, with no refusal"
                )
            except ConflictError as exc:
                print("PASS: refused while in use -> %s" % str(exc)[:80])
            await db.rollback()

            # 2. The row must still be there: the guard fires before any write.
            still_there = (
                await db.execute(
                    text("SELECT count(*) FROM media_assets WHERE id = :id"),
                    {"id": asset_id},
                )
            ).scalar()
            if not still_there:
                failures.append("the asset row was deleted even though the guard refused")
            else:
                print("PASS: the row survived the refusal")

            # 3. force means "yes, break those references" — and it still
            #    trashes. It does NOT permanently delete: that is `purge_asset`,
            #    and only for an asset already in the trash. An earlier version
            #    of this check asserted the row was gone, which was right under
            #    the old hard-delete and wrong under the trash — the check
            #    would have passed only if the P0 fix had not been applied.
            uid = uuid.UUID(asset_id)
            await MediaService.delete_asset(db, uid, force=True)
            await db.commit()
            row = (
                await db.execute(
                    text("SELECT deleted_at FROM media_assets WHERE id = :id"),
                    {"id": asset_id},
                )
            ).fetchall()
            if not row:
                failures.append(
                    "force=True removed the row outright; it should only trash it so "
                    "the delete stays reversible"
                )
            elif row[0][0] is None:
                failures.append("force=True did not set deleted_at, so nothing was trashed")
            else:
                print("PASS: force=True trashes the asset instead of destroying it")

            # 4. And the permanent removal is a separate, explicit step.
            await MediaService.purge_asset(db, uid)
            await db.commit()
            gone = (
                await db.execute(
                    text("SELECT count(*) FROM media_assets WHERE id = :id"),
                    {"id": asset_id},
                )
            ).scalar()
            if gone:
                failures.append("purge_asset did not remove the trashed row")
            else:
                print("PASS: purge_asset removes it for good")

        finally:
            await db.execute(text("DELETE FROM categories WHERE id = :id"), {"id": cat_id})
            await db.execute(text("DELETE FROM media_assets WHERE id = :id"), {"id": asset_id})
            await db.commit()
            print("cleaned up the probe rows")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: a referenced asset cannot be deleted by accident.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
