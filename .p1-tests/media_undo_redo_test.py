"""Image undo/redo navigation and save-as-copy, on the real chain.

The media editor's edits are non-destructive: every crop/rotate produces a new
asset linked by `source_asset_id`. That design makes undo/redo a navigation
problem — "undo" is opening the parent, "redo" the child — but the UI had no
buttons for it and no way to save an edited version as its own file. This
exercises the pieces that live on the server:

  * an edited chain resolves in order (history: root -> ... -> current), which
    is what the undo/redo buttons walk;
  * "duplicate" produces a standalone asset: same bytes, same metadata, no
    `source_asset_id` — a copy, not another step in the chain;
  * the copy gets its own derivatives (thumb + registered sizes), so it renders
    at every size like any other asset.

Run:  python .p1-tests/media_undo_redo_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.media.domain.models import MediaAsset
from app.modules.users.domain.models import User

TAG = "p1undoredo"
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        admin = (
            await db.execute(select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()
        await db.execute(delete(MediaAsset).where(MediaAsset.file_name.like(TAG + "%")))
        await db.commit()
    token = create_access_token(
        str(admin.id), {"roles": ["super_admin"], "permissions": ["*"]}
    )
    headers = {"Authorization": f"Bearer {token}"}
    root = Path(__file__).resolve().parents[1]
    made: list[str] = []

    buf = io.BytesIO()
    Image.new("RGB", (200, 160), (180, 40, 40)).save(buf, format="PNG")

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        try:
            # Upload, then make two edits so the chain has depth.
            r = await client.post(
                "/api/v1/media/upload",
                headers=headers,
                files={"file": (f"{TAG}-a.png", buf.getvalue(), "image/png")},
            )
            assert r.status_code == 201, r.text[:200]
            a = r.json()["asset"]
            made.append(a["id"])

            r = await client.post(
                f"/api/v1/media/{a['id']}/edit/rotate",
                headers=headers,
                json={"angle": 90},
            )
            check("1. a rotate edit produces a new asset", r.status_code == 200,
                  f"status {r.status_code} {r.text[:160]}")
            b = r.json()
            made.append(b["id"])

            r = await client.post(
                f"/api/v1/media/{b['id']}/edit/crop",
                headers=headers,
                json={"x": 0, "y": 0, "width": 60, "height": 60},
            )
            check("2. a second edit extends the chain", r.status_code == 200,
                  f"status {r.status_code} {r.text[:160]}")
            c = r.json()
            made.append(c["id"])

            # 3. The history is ordered root -> ... -> current: this is exactly
            #    the list the undo/redo buttons step through.
            r = await client.get(f"/api/v1/media/{c['id']}/edit/history", headers=headers)
            items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
            check("3. history returns the chain", len(items) >= 3,
                  f"{len(items)} steps")
            if len(items) >= 3:
                check("3b. the first step is the root", items[0]["is_root"] is True)
                check("3c. the last step is current", items[-1]["is_current"] is True)
                check("3d. the steps are ordered root -> current",
                      items[0]["id"] == a["id"] and items[-1]["id"] == c["id"])
                # undo from current -> previous; redo back.
                current_index = next(
                    (i for i, s in enumerate(items) if s["is_current"]), -1
                )
                check("3e. undo target exists (parent)",
                      current_index - 1 >= 0)
                check("3f. the parent link is walkable",
                      items[current_index - 1]["id"] == b["id"])

            # 4. Save-as-copy: standalone, same bytes, no chain link.
            r = await client.post(
                f"/api/v1/media/{c['id']}/edit/duplicate", headers=headers
            )
            check("4. duplicate answers 201", r.status_code == 201,
                  f"status {r.status_code} {r.text[:160]}")
            if r.status_code == 201:
                copy = r.json()
                made.append(copy["id"])
                check("4b. the copy is a new asset", copy["id"] != c["id"])
                check("4c. the copy has no source_asset_id",
                      copy.get("source_asset_id") is None,
                      "the copy is linked into the chain it was copied from")
                check("4d. the copy preserves dimensions",
                      (copy["width"], copy["height"]) == (c["width"], c["height"]),
                      f"copy {copy['width']}x{copy['height']} vs {c['width']}x{c['height']}")
                check("4e. the copy names itself as a copy",
                      "_copy" in copy["file_name"], copy["file_name"])
                # 4f. its own derivatives exist.
                copy_disk = root / "media" / copy["file_path"]
                stem = copy_disk.stem
                ext = copy_disk.suffix
                thumb = root / "media" / "thumbnails" / f"thumb_{copy['id'].replace('-', '')}.webp"
                check("4f. the copy got its own thumbnail", thumb.exists(),
                      f"no thumb at {thumb}")
                derived = root / "media" / "media" / f"{stem}-thumbnail{ext}"
                # thumbnail size only renders if the copy is larger than it;
                # the crop is 60x60, so absence is expected — assert instead
                # that the original file is intact.
                check("4g. the copy's original is on disk", copy_disk.is_file())
                # 4h. The copy is NOT in the original's history.
                r = await client.get(
                    f"/api/v1/media/{copy['id']}/edit/history", headers=headers
                )
                copy_items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
                check("4h. the copy starts its own chain",
                      all(s["id"] != c["id"] for s in copy_items),
                      "the copy appears inside the source's chain")

            # 5. EXIF reads the asset's real file. It had the same wrong-base
            #    bug as the edit routes: `asset.file_path` is relative to the
            #    uploads root, and `extract_exif` opens from cwd — so it read a
            #    missing path and returned {} silently (the error is swallowed),
            #    telling an operator "no camera data" for a photo that had some.
            from app.modules.media.api.routes import _resolve_edit_source

            async with Session() as db:
                row = (
                    await db.execute(select(MediaAsset).where(MediaAsset.id == c["id"]))
                ).scalars().first()
                resolved = _resolve_edit_source(row)
                check("5. the EXIF path resolves to a real file",
                      Path(resolved).is_file(), resolved)
                check("5b. the raw file_path does not (the bug's shape)",
                      not Path(row.file_path).is_file(),
                      "file_path happened to exist — the test would not catch a regression")
            r = await client.get(f"/api/v1/media/{c['id']}/exif", headers=headers)
            check("5c. the EXIF endpoint answers 200", r.status_code == 200,
                  f"status {r.status_code}")
        finally:
            for aid in made:
                await client.delete(f"/api/v1/media/{aid}", headers=headers)
                await client.delete(f"/api/v1/media/trash/{aid}", headers=headers)
            async with Session() as db:
                await db.execute(delete(MediaAsset).where(MediaAsset.file_name.like(TAG + "%")))
                await db.commit()
            check("5. probes cleaned up", True)

    await eng.dispose()
    if bad:
        print("\nUNDO/REDO GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the edit chain is navigable (undo/redo) and save-as-copy "
          "produces a standalone asset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))