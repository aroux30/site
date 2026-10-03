"""Replace media: same URL, new bytes, rebuilt derivatives.

WordPress's "Enable Media Replace". The point of the feature is the URL: a
product photo lives in pages, feeds and ads, and re-uploading breaks every one
of those references. So the assertions are:

  * the URL and the row id are unchanged;
  * the bytes on disk are the new ones;
  * the recorded size/dimensions describe the new file, not the old;
  * the derivatives were rebuilt from the new bytes (the thumbnail is not the
    old picture);
  * a replacement of the wrong type is refused, because the URL ends in the
    old extension and the server derives Content-Type from it;
  * a replacement of a trashed asset is refused.

Run:  python .p1-tests/media_replace_test.py
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

TAG = "p1replace"
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def png_bytes(color: tuple[int, int, int], size: tuple[int, int] = (40, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (
            await db.execute(select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()
        await db.execute(delete(MediaAsset).where(MediaAsset.file_name.like(TAG + "%")))
        await db.commit()
    token = create_access_token(
        str(user.id), {"roles": ["super_admin"], "permissions": ["*"]}
    )
    headers = {"Authorization": f"Bearer {token}"}
    root = Path(__file__).resolve().parents[1]

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        # Upload a red 40x30 png.
        r = await client.post(
            "/api/v1/media/upload",
            headers=headers,
            files={"file": (f"{TAG}-a.png", png_bytes((255, 0, 0)), "image/png")},
        )
        assert r.status_code == 201, r.text[:300]
        a = r.json()["asset"]
        old_url, old_id = a["file_url"], a["id"]
        old_size = a["file_size"]
        disk = root / "media" / a["file_path"]

        # 1. Replace with a blue 120x90 png.
        r = await client.post(
            f"/api/v1/media/{old_id}/replace",
            headers=headers,
            files={"file": (f"{TAG}-b.png", png_bytes((0, 0, 255), (120, 90)), "image/png")},
        )
        check("1. replace answers 200", r.status_code == 200,
              f"status {r.status_code} {r.text[:220]}")
        if r.status_code != 200:
            return 1
        b = r.json()
        check("2. the URL is unchanged", b["file_url"] == old_url,
              f"{old_url} -> {b['file_url']}")
        check("2b. the id is unchanged", b["id"] == old_id)
        check("3. the recorded dimensions are the new ones",
              (b["width"], b["height"]) == (120, 90),
              f"{b['width']}x{b['height']}")

        # 4. the bytes on disk are the new ones — decode and look at a pixel
        img = Image.open(disk)
        check("4. the stored file is the replacement",
              img.size == (120, 90) and img.convert("RGB").getpixel((0, 0)) == (0, 0, 255),
              f"size={img.size} px={img.convert('RGB').getpixel((0, 0))}")
        check("4b. and the recorded size matches the file",
              b["file_size"] == disk.stat().st_size,
              f"{b['file_size']} vs {disk.stat().st_size}")
        check("4c. and the size changed from the original", b["file_size"] != old_size,
              "the replacement is byte-identical to the original?")

        # 5. the derivatives were rebuilt: the thumbnail must be blue, not red.
        thumb = root / "media" / "thumbnails" / f"thumb_{uuid.UUID(old_id).hex}.webp"
        if thumb.exists():
            t = Image.open(thumb).convert("RGB")
            check("5. the thumbnail was rebuilt from the new bytes",
                  t.getpixel((0, 0)) == (0, 0, 255),
                  f"thumb px={t.getpixel((0, 0))}")
        else:
            check("5. the thumbnail was rebuilt from the new bytes", False,
                  f"no thumbnail at {thumb}")

        # 6. a different type is refused: the URL says .png and must keep meaning png.
        jpg = io.BytesIO()
        Image.new("RGB", (10, 10), (0, 255, 0)).save(jpg, format="JPEG")
        r = await client.post(
            f"/api/v1/media/{old_id}/replace",
            headers=headers,
            files={"file": (f"{TAG}-c.jpg", jpg.getvalue(), "image/jpeg")},
        )
        check("6. a type mismatch is refused", r.status_code in (400, 422),
              f"status {r.status_code} {r.text[:160]}")
        check("6b. and the file was not touched",
              Image.open(disk).size == (120, 90))

        # 7. a trashed asset cannot be replaced — restore first, same rule as
        #    every other write on a trashed row.
        await client.post(f"/api/v1/media/trash/{old_id}", headers=headers)
        r = await client.post(
            f"/api/v1/media/{old_id}/replace",
            headers=headers,
            files={"file": (f"{TAG}-d.png", png_bytes((1, 2, 3)), "image/png")},
        )
        check("7. replacing a trashed asset is refused",
              r.status_code in (400, 409, 422), f"status {r.status_code}")
        await client.post(f"/api/v1/media/{old_id}/restore", headers=headers)

        # 8. anonymous callers are refused.
        r = await client.post(
            f"/api/v1/media/{old_id}/replace",
            files={"file": (f"{TAG}-e.png", png_bytes((9, 9, 9)), "image/png")},
        )
        check("8. anonymous replace is refused", r.status_code in (401, 403),
              f"status {r.status_code}")

        # Clean up: trash then purge the probe.
        await client.delete(f"/api/v1/media/{old_id}", headers=headers)
        await client.delete(f"/api/v1/media/trash/{old_id}", headers=headers)
        check("9. the probe was cleaned up", not disk.exists())

    await eng.dispose()
    if bad:
        print("\nREPLACE GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: replace keeps the URL, swaps the bytes, rebuilds the "
          "derivatives, and refuses mismatches and trashed assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
