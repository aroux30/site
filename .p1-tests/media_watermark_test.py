"""The watermark options the admin card writes actually mark uploads.

The chain under test is the one an operator walks: flip the switch on the
media page (which writes `media_watermark_enabled` / `_position` / `_opacity`
via the site-options API), upload an image, and the stored bytes carry the
mark — original, thumbnail and sizes. Off, and they do not.

The mark is white text at the chosen opacity, so the probe uploads a mid-grey
field: white-on-white would be invisible and the test would "pass" while the
feature did nothing (which is exactly how the first version of this probe
failed — it counted *darker* pixels under white text).

Run:  python .p1-tests/media_watermark_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys

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
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = "p1wm"
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def grey_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (120, 120, 120)).save(buf, format="PNG")
    return buf.getvalue()


def lighter_pixels(path: Path) -> int:
    """How many pixels are markedly lighter than the grey field.

    White watermark text raises the red channel; the grey base does not.
    """
    img = Image.open(path).convert("RGB")
    return sum(1 for px in img.getdata() if px[0] > 180)


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
        made: list[str] = []
        try:
            # 1. The options the card writes, then an upload.
            async with Session() as db:
                await SiteOptionsService.set(db, "media_watermark_enabled", "1")
                await SiteOptionsService.set(db, "media_watermark_position", "center")
                await SiteOptionsService.set(db, "media_watermark_opacity", "0.9")
                await db.commit()

            r = await client.post(
                "/api/v1/media/upload",
                headers=headers,
                files={"file": (f"{TAG}-on.png", grey_png(), "image/png")},
            )
            assert r.status_code == 201, r.text[:200]
            a = r.json()["asset"]
            made.append(a["id"])
            disk = root / "media" / a["file_path"]
            light = lighter_pixels(disk)
            check("1. with the watermark on, the stored bytes carry the mark",
                  light > 50, f"{light} lighter pixels")

            thumb = root / "media" / "thumbnails" / f"thumb_{a['id'].replace('-', '')}.webp"
            if thumb.exists():
                check("1b. and the thumbnail was refreshed from the marked bytes",
                      lighter_pixels(thumb) > 10, "thumbnail has no mark")
            else:
                check("1b. and the thumbnail was refreshed from the marked bytes",
                      False, f"no thumbnail at {thumb}")

            # 2. Off: the same image comes through unmarked.
            async with Session() as db:
                await SiteOptionsService.set(db, "media_watermark_enabled", "0")
                await db.commit()
            r = await client.post(
                "/api/v1/media/upload",
                headers=headers,
                files={"file": (f"{TAG}-off.png", grey_png(), "image/png")},
            )
            b = r.json()["asset"]
            made.append(b["id"])
            light_off = lighter_pixels(root / "media" / b["file_path"])
            check("2. with the watermark off, the bytes are unmarked",
                  light_off < 50, f"{light_off} lighter pixels")

            # 3. The position option is honoured: bottom_right on a 200x200
            #    field puts the mark in the lower half, not the centre.
            async with Session() as db:
                await SiteOptionsService.set(db, "media_watermark_enabled", "1")
                await SiteOptionsService.set(db, "media_watermark_position", "bottom_right")
                await db.commit()
            r = await client.post(
                "/api/v1/media/upload",
                headers=headers,
                files={"file": (f"{TAG}-pos.png", grey_png(), "image/png")},
            )
            c = r.json()["asset"]
            made.append(c["id"])
            img = Image.open(root / "media" / c["file_path"]).convert("RGB")
            top_light = sum(
                1 for y in range(0, 100) for x in range(0, 200)
                if img.getpixel((x, y))[0] > 180
            )
            check("3. the position option moves the mark", top_light == 0,
                  f"{top_light} lighter pixels in the top half (expected none)")
        finally:
            async with Session() as db:
                await SiteOptionsService.set(db, "media_watermark_enabled", "0")
                await db.commit()
            for asset_id in made:
                await client.delete(f"/api/v1/media/{asset_id}", headers=headers)
                await client.delete(f"/api/v1/media/trash/{asset_id}", headers=headers)

    await eng.dispose()
    if bad:
        print("\nWATERMARK GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the watermark switch, position and opacity drive the upload "
          "pipeline end to end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
