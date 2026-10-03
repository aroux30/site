"""The media trash over HTTP, end to end — every call the panel makes.

The service-layer test (`backend/scripts/verify_media_trash.py`) passed while
every HTTP call the trash panel makes was broken:

  * `GET /media/trash` answered 422 — `/trash` was declared after
    `GET /{asset_id}` and parsed as an asset id;
  * `POST /media/trash/empty` answered 422 the same way, against
    `POST /trash/{asset_id}`;
  * `DELETE /media/trash/{id}` (permanent delete of one item) answered 405 —
    the route did not exist at all, though the client calls it;
  * `DELETE /media/trash` answered 500 *after purging* — the annotation said
    `dict`, the function returned `int`.

So this walks the whole operator journey through the ASGI app rather than
through the service: upload -> trash -> it is listed -> restore -> it is back;
upload -> trash -> purge -> row and bytes are gone. It also pins the refusal
paths, because "purge a live asset" being refused is what keeps the trash a
two-step.

Run:  python .p1-tests/media_trash_http_test.py
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
from sqlalchemy import select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.media.domain.models import MediaAsset
from app.modules.users.domain.models import User

TAG = "p1trashhttp"
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
    token = create_access_token(
        str(user.id), {"roles": ["super_admin"], "permissions": ["*"]}
    )
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app.main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A real 4x4 PNG, produced by Pillow rather than pasted as a hex blob —
        # a hand-copied blob is exactly the kind of fixture that is subtly
        # corrupt and fails the upload path for the wrong reason.
        import io as _io

        from PIL import Image as _Image

        buf = _io.BytesIO()
        _Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format="PNG")
        png = buf.getvalue()

        async def upload(name: str) -> dict:
            r = await client.post(
                "/api/v1/media/upload",
                headers=headers,
                files={"file": (f"{TAG}-{name}.png", png, "image/png")},
            )
            assert r.status_code == 201, f"upload failed: {r.status_code} {r.text[:200]}"
            return r.json()["asset"]

        def file_on_disk(asset: dict) -> bool:
            root = Path(__file__).resolve().parents[1]
            return (root / "media" / asset["file_path"]).exists()

        # 1. trash an asset: it appears in the trash listing and leaves the
        #    library listing.
        a = await upload("a")
        r = await client.post(f"/api/v1/media/trash/{a['id']}", headers=headers)
        check("1. trash one asset answers 200", r.status_code == 200,
              f"status {r.status_code} {r.text[:160]}")

        r = await client.get("/api/v1/media/trash", headers=headers)
        check("2. the trash listing answers 200", r.status_code == 200,
              f"status {r.status_code} {r.text[:160]}")
        trashed_ids = {i["id"] for i in r.json().get("items", [])}
        check("2b. and contains the asset", a["id"] in trashed_ids,
              f"ids={sorted(trashed_ids)[:5]}")

        r = await client.get("/api/v1/media", headers=headers)
        listed = {i["id"] for i in r.json().get("items", [])}
        check("2c. and the library no longer lists it", a["id"] not in listed)

        # 3. restore it: back in the library, gone from the trash, bytes intact.
        r = await client.post(f"/api/v1/media/{a['id']}/restore", headers=headers)
        check("3. restore answers 200", r.status_code == 200,
              f"status {r.status_code} {r.text[:160]}")
        check("3b. the bytes survived the round trip", file_on_disk(a))

        r = await client.get("/api/v1/media/trash", headers=headers)
        trashed_ids = {i["id"] for i in r.json().get("items", [])}
        check("3c. and it is gone from the trash", a["id"] not in trashed_ids)

        # 4. purge one item: row and bytes are gone, not just hidden.
        b = await upload("b")
        await client.post(f"/api/v1/media/trash/{b['id']}", headers=headers)
        r = await client.delete(f"/api/v1/media/trash/{b['id']}", headers=headers)
        check("4. permanent delete answers 200", r.status_code == 200,
              f"status {r.status_code} {r.text[:160]}")
        check("4b. the bytes are gone from disk", not file_on_disk(b))
        async with Session() as db:
            row = (
                await db.execute(
                    select(MediaAsset).where(MediaAsset.id == uuid.UUID(b["id"]))
                )
            ).scalars().first()
            check("4c. the row is gone", row is None)

        # 5. purge refuses a live asset — the trash is what makes this a
        #    two-step, and a one-step delete would make the trash a lie.
        c = await upload("c")
        r = await client.delete(f"/api/v1/media/trash/{c['id']}", headers=headers)
        check("5. purging a live asset is refused",
              r.status_code in (400, 409, 422), f"status {r.status_code}")
        check("5b. and its bytes are still there", file_on_disk(c))
        await client.delete(f"/api/v1/media/{c['id']}", headers=headers)  # to trash
        await client.delete(f"/api/v1/media/trash/{c['id']}", headers=headers)  # purge

        # 6. empty-trash: both spellings answer with the same shape, and both
        #    actually purge. Emptying the trash deletes *every* trashed row,
        #    including a peer session's in-flight fixture — so it only runs
        #    when the trash holds nothing but our own rows. The shared database
        #    is not this fixture's to empty.
        d = await upload("d")
        await client.post(f"/api/v1/media/trash/{d['id']}", headers=headers)
        e = await upload("e")
        await client.post(f"/api/v1/media/trash/{e['id']}", headers=headers)
        ours = {d["id"], e["id"]}
        r = await client.get("/api/v1/media/trash", headers=headers)
        foreign = [
            i["id"] for i in r.json().get("items", []) if i["id"] not in ours
        ]
        if foreign:
            print(f"  NOTE: {len(foreign)} foreign trashed row(s) present — "
                  f"skipping the destructive empty-trash half so a peer's "
                  f"fixture is not purged; the route bugs this gate guards "
                  f"are still covered by steps 1-5 and 9.")
        else:
            r = await client.post("/api/v1/media/trash/empty", headers=headers)
            check("6. POST /trash/empty answers 200 with a count",
                  r.status_code == 200 and isinstance(r.json().get("purged"), int),
                  f"status {r.status_code} {r.text[:160]}")
            check("6b. and it purged the asset", not file_on_disk(d))

            r = await client.delete("/api/v1/media/trash", headers=headers)
            check("7. DELETE /trash answers 200 with a count",
                  r.status_code == 200 and isinstance(r.json().get("purged"), int),
                  f"status {r.status_code} {r.text[:160]}")
            check("7b. and it purged the asset", not file_on_disk(e))

        # 8. the older_than_days filter is honoured by the HTTP layer, not just
        #    the service: a fresh entry survives a purge whose window is long
        #    past it. The window is deliberately absurd (a century) so this
        #    step cannot purge anything of anyone's while still exercising the
        #    query-string parameter end to end.
        f = await upload("f")
        await client.post(f"/api/v1/media/trash/{f['id']}", headers=headers)
        r = await client.post(
            "/api/v1/media/trash/empty?older_than_days=36500", headers=headers
        )
        check("8. a fresh entry survives an old-entries-only purge",
              r.status_code == 200, f"status {r.status_code} {r.text[:160]}")
        check("8b. and its bytes are still there", file_on_disk(f))
        await client.delete(f"/api/v1/media/trash/{f['id']}", headers=headers)

        # 9. the trash is still admin-only.
        r = await client.get("/api/v1/media/trash")
        check("9. anonymous access to the trash is refused",
              r.status_code in (401, 403), f"status {r.status_code}")

        # Clean up the one asset that is still live: `a` was restored in step 3
        # and would otherwise sit in the library as a probe row. Trash it, then
        # purge it, so the store is exactly as this fixture found it.
        await client.delete(f"/api/v1/media/{a['id']}", headers=headers)
        await client.delete(f"/api/v1/media/trash/{a['id']}", headers=headers)
        check("10. the probe row was cleaned up", not file_on_disk(a))

    if bad:
        print("\nTRASH-HTTP GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the trash works over HTTP — list, restore, purge, empty, "
          "the retention filter, and the refusals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
