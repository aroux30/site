"""Automatic image watermarking service (Karta Phase 10 - MY_Image_lib.php).

Implements:
- Overlaying semi-transparent branding watermark text/logo on product images and banners
- Preserving image formats (JPEG, PNG, WebP)
- Smart positioning (bottom-right / centered with margin)

The upload pipeline calls :func:`maybe_watermark_uploaded_file` after the
original + thumbnail are written: it reads the ``media_watermark_*`` site
options, and when enabled rewrites the stored raster (jpg/png/webp — never
svg/pdf) in place so the original, the thumbnail and every variant rendered
later from that original carry the mark. Every failure is non-fatal: the
upload continues unwatermarked.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog
from PIL import Image, ImageDraw, ImageFont

from app.modules.settings.application.site_options_service import SiteOptionsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Site options driving the feature (seeded in settings default_options).
WATERMARK_ENABLED_OPTION = "media_watermark_enabled"
WATERMARK_POSITION_OPTION = "media_watermark_position"
WATERMARK_OPACITY_OPTION = "media_watermark_opacity"

#: Only raster formats the overlay can re-encode safely; SVG is not even an
#: allowed upload MIME, PDFs must never be re-written by an image pass.
WATERMARKABLE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

_POSITIONS = ("bottom_right", "center")
_DEFAULT_OPACITY = 0.35
_TRUTHY = {"1", "true", "yes", "on", "فعال", "بله"}


def _is_truthy(raw: str | None) -> bool:
    """``media_watermark_enabled`` is operator-editable text; default off."""
    return str(raw or "").strip().lower() in _TRUTHY


def _parse_position(raw: str | None) -> Literal["bottom_right", "center"]:
    position = str(raw or "").strip().lower()
    return position if position in _POSITIONS else "bottom_right"  # type: ignore[return-value]


def _parse_opacity(raw: str | None) -> float:
    try:
        opacity = float(str(raw).strip())
    except (TypeError, ValueError):
        return _DEFAULT_OPACITY
    return min(1.0, max(0.0, opacity))


def apply_watermark(
    image_bytes: bytes,
    watermark_text: str = "Iranian E-Commerce",
    position: Literal["bottom_right", "center"] = "bottom_right",
    opacity: float = 0.35,
) -> bytes:
    """Apply a semi-transparent watermark text overlay onto image bytes."""
    if not image_bytes:
        return image_bytes

    try:
        base_image = Image.open(io.BytesIO(image_bytes))
        original_format = base_image.format or "JPEG"

        # Convert to RGBA for alpha compositing
        rgba_image = base_image.convert("RGBA")
        width, height = rgba_image.size

        # Create transparent overlay canvas
        overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        font = ImageFont.load_default()

        # Calculate text bounding box
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Calculate placement
        margin = 20
        if position == "center":
            pos_x = (width - text_w) // 2
            pos_y = (height - text_h) // 2
        else:  # bottom_right
            pos_x = max(margin, width - text_w - margin)
            pos_y = max(margin, height - text_h - margin)

        # Draw semi-transparent watermark text
        alpha_int = int(255 * opacity)
        draw.text((pos_x, pos_y), watermark_text, fill=(255, 255, 255, alpha_int), font=font)

        # Composite overlay with base image
        watermarked = Image.alpha_composite(rgba_image, overlay)

        # Convert back to target format
        out_buf = io.BytesIO()
        if original_format.upper() in ("JPEG", "JPG"):
            rgb_final = watermarked.convert("RGB")
            rgb_final.save(out_buf, format="JPEG", quality=90, optimize=True)
        elif original_format.upper() == "WEBP":
            watermarked.save(out_buf, format="WEBP", quality=90)
        else:
            watermarked.save(out_buf, format="PNG")

        return out_buf.getvalue()
    except Exception as exc:
        logger.warning("watermark_application_failed", error=str(exc))
        return image_bytes


def _regenerate_thumbnail(image_bytes: bytes, base_dir: Path, asset_hex: str) -> None:
    """Rewrite the 200px WebP thumbnail from the watermarked bytes.

    Mirrors the thumbnail block of ``MediaService.upload_file`` so the
    listing thumbnail shows the mark too.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        thumb_img = img.copy()
        thumb_img.thumbnail((200, 200))
        thumb_dir = base_dir / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_img.save(thumb_dir / f"thumb_{asset_hex}.webp", "WEBP", quality=85)


def _watermark_file_in_place(
    path: Path,
    *,
    base_dir: Path,
    asset_hex: str,
    position: Literal["bottom_right", "center"],
    opacity: float,
) -> bool:
    """Rewrite ``path`` with its watermarked bytes; returns True when changed.

    Sync helper (file IO stays out of the async function) so the thumbnail is
    regenerated from the marked bytes as well.
    """
    original = path.read_bytes()
    watermarked = apply_watermark(original, position=position, opacity=opacity)
    if watermarked == original:
        return False
    path.write_bytes(watermarked)
    try:
        _regenerate_thumbnail(watermarked, base_dir, asset_hex)
    except Exception as exc:  # thumbnail refresh is cosmetic
        logger.warning("watermark_thumbnail_refresh_failed", error=str(exc))
    return True


async def maybe_watermark_uploaded_file(
    db: AsyncSession,
    *,
    file_path: Path,
    mime_type: str,
    asset_hex: str,
    base_dir: Path,
) -> bool:
    """Apply the site watermark to a freshly uploaded raster image.

    Reads ``media_watermark_enabled`` / ``media_watermark_position`` /
    ``media_watermark_opacity`` via the site options service (defaults: off,
    bottom_right, 0.35). Returns True when the stored file was rewritten.

    Never raises: any failure logs and leaves the upload unwatermarked, so a
    broken font or unreadable file cannot fail the upload itself.
    """
    try:
        if not _is_truthy(await SiteOptionsService.get(db, WATERMARK_ENABLED_OPTION)):
            return False
        if mime_type not in WATERMARKABLE_MIME_TYPES:
            return False

        position = _parse_position(
            await SiteOptionsService.get(db, WATERMARK_POSITION_OPTION)
        )
        opacity = _parse_opacity(
            await SiteOptionsService.get(db, WATERMARK_OPACITY_OPTION)
        )

        changed = _watermark_file_in_place(
            file_path, base_dir=base_dir, asset_hex=asset_hex, position=position, opacity=opacity
        )
        if changed:
            await logger.ainfo(
                "media_watermark_applied",
                asset_hex=asset_hex,
                position=position,
                opacity=opacity,
            )
        return changed
    except Exception as exc:  # watermarking is best-effort
        logger.warning("media_watermark_skipped", asset_hex=asset_hex, error=str(exc))
        return False
