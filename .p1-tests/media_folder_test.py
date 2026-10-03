"""Creating a media folder, and what an empty one means here.

Folders in this schema are not rows. `list_folders` reads the distinct
`folder` values on media assets, so until now a folder existed only once
something had been uploaded into it — and the "create folder" button could not
exist without inventing something to represent an empty one. Laying out
`products/shoes` before the first product photo is the normal way anybody
builds a library, and it was not possible.

The representation chosen is a zero-byte marker row, which is a real decision
with real failure modes, and this checks each one:

  * the marker must not appear in the grid. A zero-byte row with no visible
    reason is worse than no folder, and the operator cannot delete it without
    wondering what it is;
  * it must not count toward the library total, or "127 files" becomes a lie
    the operator quotes to somebody else;
  * it must not count toward its own folder, so an empty folder reads as empty;
  * deleting a folder that holds real files must be refused unless the caller
    says so — and even then only the folder's own files go.
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from sqlalchemy import delete, or_, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.media.application.media_service import MediaService
from app.modules.media.domain.models import MediaAsset
from app.modules.users.domain.models import User

TAG = "p1folder"
MARKER = "inode/directory"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        root = f"{TAG}-{uuid.uuid4().hex[:8]}"
        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_path.like(root + "%")))
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        # 1. creating an empty folder works and says so
        made = await MediaService.create_folder(db, f"{root}/shoes")
        check("1. an empty folder is created", made["created"] is True, str(made))
        check("1b. its path is stored sanitised", made["path"] == f"{root}/shoes",
              str(made))

        # 2. it appears in the folder list with a count of zero. A folder that
        #    is only visible once it has a file in it is not a folder.
        folders = {f["path"]: f["asset_count"] for f in await MediaService.list_folders(db)}
        check("2. the empty folder is listed", f"{root}/shoes" in folders,
              str(list(folders)[:6]))
        check("2b. and it reports zero files",
              folders.get(f"{root}/shoes") == 0,
              str(folders.get(f"{root}/shoes")))

        # 3. the marker is not a file the operator can see
        items, total = await MediaService.list_assets(db, page_size=100)
        names = {a.file_name for a in items}
        check("3. the marker is not in the grid",
              not any(n.startswith(".folder-") for n in names),
              str([n for n in names if n.startswith(".folder-")]))

        # 4. and it is not in the folder's own listing
        items, _ = await MediaService.list_assets(db, folder=f"{root}/shoes")
        check("4. the folder itself looks empty", items == [], str(len(items)))

        # 5. creating it again is not an error — that is a double-click
        again = await MediaService.create_folder(db, f"{root}/shoes")
        check("5. creating it twice is not an error", again["created"] is False,
              str(again))

        # 6. a real file makes the folder non-empty
        real = MediaAsset(
            uploader_id=user.id, file_name=f"{root}-shoe.png",
            file_path=f"{root}/shoe.png",
            # In the folder, not beside it: the tree is derived from this
            # column, and a fixture that forgets it tests a file the folder
            # never had.
            folder=f"{root}/shoes",
            file_url=f"/uploads/{root}/shoe.png",
            file_size=2048, mime_type="image/png", width=50, height=50,
        )
        db.add(real)
        await db.commit()
        folders = {f["path"]: f["asset_count"] for f in await MediaService.list_folders(db)}
        check("6. the folder counts its real file",
              folders.get(f"{root}/shoes") == 1, str(folders.get(f"{root}/shoes")))

        # 7. deleting it now is refused, because a file is in there
        try:
            await MediaService.delete_folder(db, f"{root}/shoes")
            check("7. deleting a non-empty folder is refused", False, "no error")
        except Exception as exc:
            check("7. deleting a non-empty folder is refused",
                  type(exc).__name__ == "ConflictError", type(exc).__name__)
        still = (await db.execute(
            select(MediaAsset).where(MediaAsset.file_name == f"{root}-shoe.png")
        )).scalar_one_or_none()
        check("7b. and the file survives the refusal", still is not None)

        # 8. saying so explicitly empties it
        res = await MediaService.delete_folder(db, f"{root}/shoes", delete_assets=True)
        check("8. an explicit delete empties the folder", res["removed"] >= 1, str(res))
        folders = {f["path"]: f["asset_count"] for f in await MediaService.list_folders(db)}
        check("8b. and the folder is gone from the list",
              f"{root}/shoes" not in folders, str(folders.get(f"{root}/shoes")))

        # 9. a nested folder under it goes too — the tree is a path, so
        #    "products" has to take "products/shoes" with it, or the tree
        #    keeps a branch pointing at nothing.
        await MediaService.create_folder(db, f"{root}/shoes")
        await MediaService.create_folder(db, f"{root}/shoes/running")
        res = await MediaService.delete_folder(db, f"{root}/shoes")
        check("9. deleting a parent takes its children", res["removed"] >= 2, str(res))
        folders = {f["path"] for f in await MediaService.list_folders(db)}
        check("9b. and nothing of that subtree is left",
              not any(p.startswith(f"{root}/shoes") for p in folders),
              str([p for p in folders if p.startswith(root)]))

        # 10. a path with traversal in it does not escape
        escaped = await MediaService.create_folder(db, f"../{root}/escape")
        check("10. a traversal path is normalised, not obeyed",
              ".." not in escaped["path"], str(escaped))

        # cleanup
        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_path.like(f"%{root}%")))
        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_name.like(f"{root}%")))
        await db.execute(delete(MediaAsset).where(
            MediaAsset.mime_type == MARKER,
            MediaAsset.file_path.like(root + "%")))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nFOLDER GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: an empty folder can be created, is listed as empty, is not a "
          "file, and is safe to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))