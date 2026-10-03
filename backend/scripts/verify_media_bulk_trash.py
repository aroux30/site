"""Live check: bulk delete moves many assets and reports each one's outcome.

P0 "مدیا: حذف گروهی در کتابخانه". The library offered only "move selected",
so clearing a folder meant one confirmation and one request per file.

The behaviour that is easy to get wrong, and is asserted here:
  * one file still in use must not stop the other nineteen — that is what the
    per-item savepoint buys, and without it the refused item aborts the
    transaction and the rest of the batch dies with it;
  * the response has to say which ones went and which did not, because "20
    selected, 17 trashed, 3 in use" and "20 trashed" are different facts;
  * the refused ones keep their bytes. A bulk delete that silently purges is
    the opposite of what a single delete does.

    cd backend && PYTHONPATH=. python scripts/verify_media_bulk_trash.py
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

from app.core.exceptions.handlers import ValidationError  # noqa: E402
from app.modules.media.application.media_service import MediaService  # noqa: E402


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

    # Three unused assets and one that a category points at.
    free_ids = [str(uuid.uuid4()) for _ in range(3)]
    used_id = str(uuid.uuid4())
    used_name = f"bulk-used-{suffix}.png"
    cat_id = str(uuid.uuid4())

    async with session() as db:
        try:
            for n, aid in enumerate(free_ids):
                await db.execute(
                    text(
                        "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                        "file_size, mime_type, created_at, updated_at) "
                        "VALUES (:id, :name, :path, :url, 1, 'image/png', now(), now())"
                    ),
                    {
                        "id": aid,
                        "name": f"bulk-free-{suffix}-{n}.png",
                        "path": f"media/bulk-free-{suffix}-{n}.png",
                        "url": f"/uploads/media/bulk-free-{suffix}-{n}.png",
                    },
                )
            await db.execute(
                text(
                    "INSERT INTO media_assets (id, file_name, file_path, file_url, "
                    "file_size, mime_type, created_at, updated_at) "
                    "VALUES (:id, :name, :path, :url, 1, 'image/png', now(), now())"
                ),
                {
                    "id": used_id,
                    "name": used_name,
                    "path": f"media/{used_name}",
                    "url": f"/uploads/media/{used_name}",
                },
            )
            await db.execute(
                text(
                    "INSERT INTO categories (id, name, slug, path, depth, position, "
                    "is_active, created_at, updated_at, image_url) "
                    "VALUES (:id, :name, :slug, :slug, 0, 0, true, now(), now(), :url)"
                ),
                {
                    "id": cat_id,
                    "name": "bulk probe",
                    "slug": f"bulk-probe-{suffix}",
                    "url": f"/uploads/media/{used_name}",
                },
            )
            await db.commit()

            # MediaService is all-static; it takes no session.
            svc = MediaService
            batch = [uuid.UUID(i) for i in free_ids] + [uuid.UUID(used_id)]

            # 1. The whole batch, without force: three go, the used one does not.
            result = await svc.bulk_trash(db, batch, force=False)
            await db.commit()

            if result["total"] != 4:
                failures.append(f"total is {result['total']}, expected 4")
            if result["ok"] != 3:
                failures.append(
                    f"ok is {result['ok']}, expected 3 — a file still in use must "
                    f"not stop the rest of the batch"
                )
            if result["failed"] != 1:
                failures.append(f"failed is {result['failed']}, expected 1")
            else:
                print("PASS: three unused assets moved, the referenced one was refused")
                refusals = [r for r in result["results"] if not r["ok"]]
                if refusals and "استفاده" not in str(refusals[0].get("error", "")):
                    print("      (refusal reason: %s)" % str(refusals[0].get("error"))[:60])

            # 2. Per-item, not one boolean: the response has to name the ids.
            returned = {str(r["id"]) for r in result["results"]}
            if returned != {str(i) for i in batch}:
                failures.append(
                    "the response does not name every submitted id — an operator "
                    "cannot tell which file was skipped"
                )
            else:
                print("PASS: the response names every submitted asset")

            # 3. The refused one keeps its row and stays live.
            row = (
                await db.execute(
                    text("SELECT deleted_at FROM media_assets WHERE id = :id"),
                    {"id": used_id},
                )
            ).fetchall()
            if not row or row[0][0] is not None:
                failures.append("the refused asset was trashed anyway")
            else:
                print("PASS: the refused asset stayed in the library")

            # 4. And it is still in use — nothing was quietly unreferenced.
            still_referenced = (
                await db.execute(
                    text("SELECT count(*) FROM categories WHERE image_url LIKE :u"),
                    {"u": f"%{used_name}"},
                )
            ).scalar()
            if not still_referenced:
                failures.append("the category lost its image reference")
            else:
                print("PASS: the reference that caused the refusal is intact")

            # 5. Force: the operator confirms, and it goes to the trash.
            forced = await MediaService.bulk_trash(db, [uuid.UUID(used_id)], force=True)
            await db.commit()
            if forced["ok"] != 1:
                failures.append(
                    f"force moved {forced['ok']} asset(s), expected the refused one"
                )
            else:
                trashed = (
                    await db.execute(
                        text("SELECT deleted_at FROM media_assets WHERE id = :id"),
                        {"id": used_id},
                    )
                ).scalar()
                if trashed is None:
                    failures.append("force did not actually set deleted_at")
                else:
                    print("PASS: force trashes the referenced asset instead of refusing")

        finally:
            for aid in [*free_ids, used_id]:
                await db.execute(
                    text("DELETE FROM media_assets WHERE id = :id"), {"id": aid}
                )
            await db.execute(text("DELETE FROM categories WHERE id = :id"), {"id": cat_id})
            await db.commit()
            print("cleaned up the probe rows")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: bulk delete reports per item and one refusal does not stop the batch.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))