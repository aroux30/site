"""Custom image sizes: register one, upload, get the file; delete, lose it.

WordPress's ``add_image_size()``. The four built-in sizes were operator-
editable but no fifth could be registered, so a storefront needing a 2:1 hero
or a 4:5 portrait tile had no way to ask for one.

The assertions are the two halves that matter:

  * a registered size produces ``<uuid>-<name>.<ext>`` on upload, and the
    name is validated (a traversal-shaped name never reaches the filesystem);
  * deleting the asset reclaims that file — the deletion sweep finds derived
    sizes by uuid-prefix glob, not by a hardcoded size list, precisely so a
    custom size's files do not leak.

Run:  python .p1-tests/media_custom_size_test.py
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
from app.modules.media.application.image_processor import parse_custom_image_sizes
from app.modules.media.domain.models import MediaAsset
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = "p1csize"
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    # 1. The parser: pure, so the validation is checked without a database.
    parsed = parse_custom_image_sizes(
        '[{"name":"hero","width":1600,"height":800,"crop":true},'
        ' {"name":"../etc","width":100,"height":100},'
        ' {"name":"UPPER","width":100},'
        ' {"name":"thumb2","width":8},'
        ' {"name":"thumbnail","width":999},'
        ' {"name":"ok","width":300,"height":"","crop":false}]'
    )
    check("1. a valid size is parsed", "hero" in parsed and parsed["hero"]["width"] == 1600,
          f"{parsed.get('hero')}")
    check("1b. a traversal-shaped name is dropped", "../etc" not in parsed)
    check("1c. an uppercase name is dropped (it reaches a filename)",
          "UPPER" not in parsed)
    check("1d. a width below the floor is dropped", "thumb2" not in parsed)
    check("1e. a built-in name cannot be overridden", "thumbnail" not in parsed)
    check("1f. an empty height means proportional", parsed.get("ok") == {"width": 300, "height": None, "crop": False},
          f"{parsed.get('ok')}")
    check("1g. malformed JSON is an empty registry, not a crash",
          parse_custom_image_sizes("not json") == {})
    check("1h. None is an empty registry", parse_custom_image_sizes(None) == {})

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
            async with Session() as db:
                await SiteOptionsService.set(
                    db,
                    "custom_image_sizes",
                    '[{"name":"hero2to1","width":300,"height":150,"crop":true}]',
                )
                await db.commit()

            # 2. Upload a 600x400 image; the registered 300x150 crop must be
            #    produced beside the original.
            buf = io.BytesIO()
            Image.new("RGB", (600, 400), (60, 120, 180)).save(buf, format="PNG")
            r = await client.post(
                "/api/v1/media/upload",
                headers=headers,
                files={"file": (f"{TAG}-a.png", buf.getvalue(), "image/png")},
            )
            assert r.status_code == 201, r.text[:300]
            a = r.json()["asset"]
            made.append(a["id"])
            stem = Path(a["file_path"]).stem
            hero = root / "media" / "media" / f"{stem}-hero2to1.png"
            check("2. the registered size is generated on upload", hero.exists(),
                  f"no file at {hero}")
            if hero.exists():
                # `with`, not a bare open: Pillow keeps the file handle open
                # until the image is loaded or closed, and on Windows an open
                # handle makes the later unlink fail — the delete would "leak"
                # the file and the test would blame the product for the test's
                # own handle.
                with Image.open(hero) as img:
                    check("2b. with the registered dimensions",
                          img.size == (300, 150), f"size={img.size}")

            # 3. Delete reclaims the custom-size file too.
            r1 = await client.delete(f"/api/v1/media/{a['id']}", headers=headers)
            r2 = await client.delete(f"/api/v1/media/trash/{a['id']}", headers=headers)
            if r1.status_code != 200 or r2.status_code != 200:
                check("3. deleting the asset reclaims the custom-size file", False,
                      f"trash={r1.status_code} {r1.text[:120]} purge={r2.status_code} {r2.text[:120]}")
            else:
                check("3. deleting the asset reclaims the custom-size file",
                      not hero.exists(), f"left behind: {hero}")
        finally:
            async with Session() as db:
                await SiteOptionsService.set(db, "custom_image_sizes", "[]")
                await db.commit()
            for asset_id in made:
                await client.delete(f"/api/v1/media/{asset_id}", headers=headers)
                await client.delete(f"/api/v1/media/trash/{asset_id}", headers=headers)

    await eng.dispose()
    if bad:
        print("\nCUSTOM-SIZE GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: a custom size is registered, generated, validated, and "
          "reclaimed on delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
