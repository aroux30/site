"""Image processing utilities: thumbnail generation + EXIF extraction (WordPress parity).

Generates multiple image sizes on upload (thumbnail, medium, large) and
extracts EXIF metadata from photographs.

Usage:
    from app.modules.media.application.image_processor import ImageProcessor
    sizes = await ImageProcessor.generate_thumbnails(file_path)
    exif = await ImageProcessor.extract_exif(file_path)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# WordPress default image sizes
IMAGE_SIZES = {
    "thumbnail": {"width": 150, "height": 150, "crop": True},
    "medium": {"width": 300, "height": 300, "crop": False},
    "medium_large": {"width": 768, "height": None, "crop": False},
    "large": {"width": 1024, "height": 1024, "crop": False},
}

#: Ceilings for operator-editable sizes. A storefront that can be asked for a
#: 40000px "thumbnail" is a misconfiguration, not a request worth honouring.
_MAX_SIZE_PX = 4096
_MIN_SIZE_PX = 16


def derived_size_name(stem: str, size_name: str, ext: str) -> str:
    """The filename ``generate_thumbnails`` writes for one size.

    The writer and the deleter must agree on this name, so both call here
    rather than each spelling out ``f"{stem}-{size_name}{ext}"``. A registered
    size is only produced when the original is larger than it, so this names
    a candidate that may not exist — callers that delete must tolerate its
    absence.
    """
    return f"{stem}-{size_name}{ext}"


async def resolve_image_sizes(db: "AsyncSession | None") -> dict[str, dict[str, Any]]:
    """The registered sizes, with the admin-configured dimensions applied.

    ``thumbnail_size_w/h``, ``medium_size_w/h`` and ``large_size_w/h`` are
    editable on the settings screen, but nothing read them: the sizes below
    were hardcoded, so changing a value there did nothing until a regeneration
    — which could not resolve its own path. Reads are clamped and fall back on
    unparseable text, so an operator typo degrades to the default rather than
    raising inside an upload.

    ``medium_large`` has no options of its own (WordPress does not expose it
    either) and keeps its default width.
    """
    if db is None:
        return dict(IMAGE_SIZES)

    from app.modules.settings.application.site_options_service import SiteOptionsService

    async def _dim(prefix: str, key: str, default: int | None) -> int | None:
        value = await SiteOptionsService.get_int(
            db,
            f"{prefix}_size_{key}",
            default or _MIN_SIZE_PX,
            minimum=_MIN_SIZE_PX,
            maximum=_MAX_SIZE_PX,
        )
        return value if default is not None else None

    return {
        "thumbnail": {
            "width": await _dim("thumbnail", "w", 150),
            "height": await _dim("thumbnail", "h", 150),
            "crop": (await SiteOptionsService.get(db, "thumbnail_crop", "1")) == "1",
        },
        "medium": {
            "width": await _dim("medium", "w", 300),
            "height": await _dim("medium", "h", 300),
            "crop": False,
        },
        "medium_large": {"width": IMAGE_SIZES["medium_large"]["width"], "height": None, "crop": False},
        "large": {
            "width": await _dim("large", "w", 1024),
            "height": await _dim("large", "h", 1024),
            "crop": False,
        },
    }


class ImageProcessor:
    """Generate thumbnails and extract EXIF metadata."""

    @staticmethod
    async def generate_thumbnails(
        file_path: str,
        *,
        sizes: dict[str, dict[str, Any]] | None = None,
        db: "AsyncSession | None" = None,
    ) -> dict[str, str]:
        """Generate multiple image sizes from the original.

        Pass ``db`` to honour the operator-configured dimensions from the
        settings screen; without it the hardcoded defaults are used, so every
        existing caller keeps working unchanged.

        Returns a dict of size_name -> output_file_path.
        """
        if sizes is None:
            sizes = await resolve_image_sizes(db)

        results: dict[str, str] = {}
        try:
            from PIL import Image

            img = Image.open(file_path)
            p = Path(file_path)
            stem = p.stem
            ext = p.suffix or ".jpg"

            for size_name, config in sizes.items():
                target_w = config["width"]
                target_h = config.get("height")
                crop = config.get("crop", False)

                # Skip if original is smaller than target
                if target_w and img.width <= target_w and (not target_h or img.height <= target_h):
                    continue

                if crop and target_w and target_h:
                    # Center crop to exact dimensions
                    ratio = max(target_w / img.width, target_h / img.height)
                    resized = img.resize(
                        (int(img.width * ratio), int(img.height * ratio)),
                        Image.Resampling.LANCZOS,
                    )
                    left = (resized.width - target_w) // 2
                    top = (resized.height - target_h) // 2
                    result = resized.crop((left, top, left + target_w, top + target_h))
                else:
                    # Proportional resize
                    if target_h is None:
                        ratio = target_w / img.width
                        new_h = int(img.height * ratio)
                        result = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
                    else:
                        # Work on a copy: Image.thumbnail() shrinks the image
                        # in place, so calling it on `img` made every later size
                        # see an already-reduced image and skip itself. Only the
                        # first one or two sizes were ever produced.
                        scaled = img.copy()
                        scaled.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
                        result = scaled

                output = p.parent / derived_size_name(stem, size_name, ext)
                result.save(str(output), quality=85)
                results[size_name] = str(output)

            logger.info("thumbnails_generated", src=file_path, sizes=list(results.keys()))
        except ImportError:
            logger.warning("pillow_not_installed")
        except Exception as exc:
            logger.error("thumbnail_generation_failed", src=file_path, error=str(exc))

        return results

    @staticmethod
    async def extract_exif(file_path: str) -> dict[str, Any]:
        """Extract EXIF metadata from an image file.

        Returns a dict with common EXIF fields (camera, lens, exposure, GPS, etc.).
        """
        exif_data: dict[str, Any] = {}
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            img = Image.open(file_path)
            raw_exif = img.getexif()

            if not raw_exif:
                return exif_data

            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                # Skip binary data
                if isinstance(value, bytes):
                    continue
                try:
                    exif_data[tag_name] = str(value) if not isinstance(value, (int, float)) else value
                except Exception:
                    continue

            # Extract GPS info if available
            gps_info = raw_exif.get_ifd(0x8825)
            if gps_info:
                gps_data: dict[str, Any] = {}
                for gps_tag_id, gps_value in gps_info.items():
                    gps_tag_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                    try:
                        gps_data[gps_tag_name] = str(gps_value)
                    except Exception:
                        continue
                if gps_data:
                    exif_data["GPSInfo"] = gps_data

            logger.debug("exif_extracted", src=file_path, fields=len(exif_data))
        except ImportError:
            logger.warning("pillow_not_installed")
        except Exception as exc:
            logger.debug("exif_extraction_failed", src=file_path, error=str(exc))

        return exif_data
