"""Big-image downscaling — the file that gets stored is the file that was scaled.

`big_image_size_threshold` is WordPress's `big_image_size_threshold`, and the
reason it exists is a phone: a modern camera writes 4000px files that no
storefront ever displays at full size, and serving one is the difference
between a product page that loads and one that does not.

The tempting wrong implementation is a "regenerate thumbnails" button, and it
does not work — the file that is too big is the *original*, and the original is
what gets served when somebody pastes the image URL. So this checks the bytes
on disk, not a derivative.

Three things that can all be wrong while the upload succeeds:

  * the scale ignores the aspect ratio. Capping each side independently turns a
    4000x3000 into 2560x3000, which is a 40% horizontal stretch nobody notices
    until a customer sees a squashed product photo;
  * it upscales. A 400px logo left alone stays 400px — enlarging it to 2560
    costs bytes and adds nothing;
  * the recorded width/height come from the pre-scale image, so the library
    shows a size the file does not have.
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from PIL import Image
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.media.application.media_service import (
    DEFAULT_BIG_IMAGE_THRESHOLD,
    MediaService,
    _fit_within,
)
from app.modules.media.domain.models import MediaAsset
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = "p1bigimg"
bad: list[str] = []


def png(width: int, height: int, colour=(200, 30, 30)) -> bytes:
    """A real PNG, so the upload path takes its normal image branch."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, format="PNG")
    return buf.getvalue()


class FakeUpload:
    """The two attributes `upload_file` reads off an UploadFile."""

    def __init__(self, data: bytes, name: str, content_type: str):
        self.file = io.BytesIO(data)
        self.filename = name
        self.content_type = content_type
        # The upload path sniffs the declared type against the sniffed one, so
        # a stand-in without headers fails the check for the wrong reason.
        self.headers = {}

    async def read(self, *a, **k):  # noqa: ANN002, ANN003
        return self.file.read()

    async def seek(self, *a, **k):  # noqa: ANN002, ANN003
        return self.file.seek(*a, **k)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_name.like(TAG + "%")))
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        async def upload(width, height, name):
            asset = await MediaService.upload_file(
                db, FakeUpload(png(width, height), f"{TAG}-{name}.png", "image/png"),
                uploader_id=user.id,
            )
            return asset

        # 0. the geometry helper, on its own. Pure, so it is the cheapest place
        #    to catch an aspect-ratio bug.
        check("1. a landscape 4000x3000 fits to 2560x1920",
              _fit_within((4000, 3000), 2560) == (2560, 1920),
              str(_fit_within((4000, 3000), 2560)))
        check("1b. a portrait 3000x4000 fits to 1920x2560",
              _fit_within((3000, 4000), 2560) == (1920, 2560),
              str(_fit_within((3000, 4000), 2560)))
        check("1c. a small image is left alone, not enlarged",
              _fit_within((400, 300), 2560) == (400, 300),
              str(_fit_within((400, 300), 2560)))
        check("1d. an exactly-at-threshold image is left alone",
              _fit_within((2560, 2560), 2560) == (2560, 2560))
        check("1e. a one-pixel side never rounds to zero",
              all(min(_fit_within((s, s), 2560)) >= 1 for s in (3000, 2561, 9000)),
              "a scaled dimension collapsed to 0")

        try:
            await SiteOptionsService.set(db, "big_image_size_threshold", "2560")

            # 1. a big image is scaled, and the stored dimensions say so
            big = await upload(4000, 3000, "big")
            check("2. a 4000px image is stored smaller", max(big.width, big.height) <= 2560,
                  f"{big.width}x{big.height}")
            check("2b. its recorded size matches what is stored",
                  (big.width, big.height) == (2560, 1920),
                  f"{big.width}x{big.height}")

            # 2. the file on disk is the scaled one, not the original. Checking
            #    the recorded columns alone would pass while the original bytes
            #    were still on disk.
            from pathlib import Path

            stored = Path(big.file_path)
            on_disk = None
            for root in ("uploads", "media", "static/uploads", "."):
                candidate = Path(root) / big.file_path
                if candidate.is_file():
                    on_disk = candidate
                    break
            if on_disk is None and stored.is_file():
                on_disk = stored
            check("2c. the file on disk is the scaled one",
                  on_disk is not None and max(Image.open(on_disk).size) <= 2560,
                  f"not found or still large ({on_disk})")

            # 3. a small image is untouched
            small = await upload(400, 300, "small")
            check("3. a small image keeps its size", (small.width, small.height) == (400, 300),
                  f"{small.width}x{small.height}")

            # 4. 0 turns it off — an operator who wants the originals
            await SiteOptionsService.set(db, "big_image_size_threshold", "0")
            raw = await upload(4000, 3000, "raw")
            check("4. a threshold of 0 stores the original",
                  (raw.width, raw.height) == (4000, 3000),
                  f"{raw.width}x{raw.height}")

            # 5. a threshold above the image changes nothing
            await SiteOptionsService.set(db, "big_image_size_threshold", "8000")
            tall = await upload(4000, 3000, "tall")
            check("5. a threshold above the image leaves it alone",
                  (tall.width, tall.height) == (4000, 3000),
                  f"{tall.width}x{tall.height}")

            # 6. the default is the documented one, so a deployment that never
            #    opens the settings page still gets it
            await SiteOptionsService.delete(db, "big_image_size_threshold")
            check("6. the default is 2560", DEFAULT_BIG_IMAGE_THRESHOLD == 2560,
                  str(DEFAULT_BIG_IMAGE_THRESHOLD))
            plain = await upload(4000, 3000, "default")
            check("6b. and with no stored value the default applies",
                  max(plain.width, plain.height) <= 2560,
                  f"{plain.width}x{plain.height}")

        finally:
            await SiteOptionsService.set(
                db, "big_image_size_threshold",
                str(DEFAULT_BIG_IMAGE_THRESHOLD))
            await db.execute(delete(MediaAsset).where(
                MediaAsset.file_name.like(TAG + "%")))
            await db.commit()

    await eng.dispose()
    if bad:
        print("\nBIG-IMAGE GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: oversized images are scaled at upload, keep their aspect "
          "ratio, and the setting can turn that off.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))