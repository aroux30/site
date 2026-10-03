"""A customer can upload an avatar, and the profile points at it.

P1 "کاربران: آواتار سفارشی". `avatar_url` existed and PATCH /me accepted it,
but the media library is admin-gated so a customer had no upload path — the
field was only fillable by pasting a URL.

Server-side facts over the real route:

  * POST /auth/me/avatar with an image stores a file and returns a profile
    whose avatar_url points at it;
  * a non-image is refused (the media service sniffs bytes, not the declared
    type);
  * the uploader is the caller (owner-scoped), and an unauthenticated call is
    401.

Run:  python .p1-tests/avatar_upload_test.py
"""

from __future__ import annotations

import asyncio
import io
import struct
import sys
import uuid
import zlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.users.domain.models import User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def make_png(size: int = 64) -> bytes:
    """A real, minimal PNG — magic bytes and a decodable image.

    The media service sniffs the bytes and runs them through the image
    pipeline, so a fake header would be rejected for the wrong reason.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * size for _ in range(size))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    phone = "09" + "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])

    created_user_ids: list[uuid.UUID] = []

    try:
        async with Session() as db:
            u = User(
                phone=phone, is_active=True, is_verified=True,
                author_slug=f"p1av{marker}",
            )
            db.add(u)
            await db.flush()
            db.add(UserProfile(user_id=u.id, first_name=f"AV{marker}"))
            await db.commit()
            user_id = u.id
            created_user_ids.append(u.id)

        token = create_access_token(str(user_id), {"roles": ["customer"]})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 0. Unauthenticated is refused.
            r = await client.post(
                "/api/v1/auth/me/avatar",
                files={"file": ("a.png", make_png(), "image/png")},
            )
            check("0. an unauthenticated upload is refused (401)",
                  r.status_code == 401, f"status {r.status_code}")

            # 1. A real PNG uploads and the profile points at it.
            r = await client.post(
                "/api/v1/auth/me/avatar",
                headers=headers,
                files={"file": ("avatar.png", make_png(), "image/png")},
            )
            check("1. an avatar upload answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:220]}")
            avatar_url = (r.json() or {}).get("avatar_url")
            check("1b. the response carries an avatar_url",
                  bool(avatar_url), f"avatar_url={avatar_url!r}")

            async with Session() as db:
                prof = (
                    await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
                ).scalar_one()
                check("1c. the profile row was updated",
                      prof.avatar_url == avatar_url,
                      f"stored={prof.avatar_url!r} returned={avatar_url!r}")

            # 1d. GET /auth/me returns the same URL.
            r = await client.get("/api/v1/auth/me", headers=headers)
            check("1d. /auth/me returns the avatar",
                  r.json().get("avatar_url") == avatar_url,
                  f"me.avatar_url={r.json().get('avatar_url')!r}")

            # 2. A non-image is refused by the byte sniff, not the extension.
            r = await client.post(
                "/api/v1/auth/me/avatar",
                headers=headers,
                files={"file": ("evil.png", b"not an image at all", "image/png")},
            )
            check("2. a non-image with an image content type is refused",
                  r.status_code in (400, 415, 422), f"status {r.status_code} {r.text[:160]}")
    finally:
        # Purge the uploaded assets through the service — trash then purge,
        # because purge refuses a live asset by design. This removes both the
        # row and the bytes on disk; leaving either behind would make the
        # fixture accumulate storage on every run. Collected by folder before
        # the user delete, since the FK nulls uploader_id.
        async with Session() as db:
            from app.modules.media.application.media_service import MediaService
            from app.modules.media.domain.models import MediaAsset

            rows = (
                await db.execute(
                    select(MediaAsset.id).where(
                        MediaAsset.folder == "avatars",
                        MediaAsset.uploader_id.in_(created_user_ids),
                    )
                )
            ).scalars().all()
            for asset_id in rows:
                await MediaService.trash_asset(db, asset_id)
                await MediaService.purge_asset(db, asset_id)
            await db.commit()
        async with Session() as db:
            for uid in created_user_ids:
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            left = (
                await db.execute(select(User.id).where(User.phone == phone))
            ).scalars().all()
            check("3. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nAVATAR GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: a customer avatar uploads, is stored on the profile, is "
          "returned by /auth/me, and non-images are refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))