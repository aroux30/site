"""The media Title field: stored, returned, and nullable.

WordPress's attachment editor has four text fields (Title, Alt, Caption,
Description) and the library had three. The column is nullable with no
backfill, so the two facts to pin are: a title round-trips through PATCH and
the list response, and a row that was never titled stays NULL rather than
gaining an auto-filled name that looks curated.

Run:  python .p1-tests/media_title_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.media.domain.models import MediaAsset
from app.modules.users.domain.models import User

TAG = "p1title"
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


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

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="PNG")

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/v1/media/upload",
            headers=headers,
            files={"file": (f"{TAG}-a.png", buf.getvalue(), "image/png")},
        )
        assert r.status_code == 201, r.text[:300]
        a = r.json()["asset"]
        check("1. a fresh upload has no title (NULL, not auto-filled)",
              a.get("title") is None, f"title={a.get('title')!r}")

        r = await client.patch(
            f"/api/v1/media/{a['id']}",
            headers=headers,
            json={"title": "کفش دویدن قرمز — نمای از پهلو"},
        )
        check("2. PATCH accepts a title", r.status_code == 200,
              f"status {r.status_code} {r.text[:160]}")
        check("2b. and returns it", r.json().get("title") == "کفش دویدن قرمز — نمای از پهلو",
              f"title={r.json().get('title')!r}")

        r = await client.get("/api/v1/media", headers=headers,
                             params={"search": TAG})
        items = {i["id"]: i for i in r.json()["items"]}
        check("3. the list response carries the title",
              items.get(a["id"], {}).get("title") == "کفش دویدن قرمز — نمای از پهلو",
              f"title={items.get(a['id'], {}).get('title')!r}")

        # Clearing it returns to NULL, which is what "never titled" means.
        r = await client.patch(
            f"/api/v1/media/{a['id']}", headers=headers, json={"title": ""}
        )
        check("4. an emptied title is accepted", r.status_code == 200)
        async with Session() as db:
            row = (
                await db.execute(
                    select(MediaAsset).where(MediaAsset.id == a["id"])
                )
            ).scalars().first()
            # Empty string is fine; what must not happen is an auto-fill.
            check("4b. and it is not auto-filled from the file name",
                  row.title in ("", None), f"title={row.title!r}")

        await client.delete(f"/api/v1/media/{a['id']}", headers=headers)
        await client.delete(f"/api/v1/media/trash/{a['id']}", headers=headers)

    await eng.dispose()
    if bad:
        print("\nTITLE GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the media title round-trips, is nullable, and is never "
          "auto-filled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
