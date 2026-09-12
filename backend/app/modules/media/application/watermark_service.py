"""Automatic image watermarking service (Karta Phase 10 - MY_Image_lib.php).

Implements:
- Overlaying semi-transparent branding watermark text/logo on product images and banners
- Preserving image formats (JPEG, PNG, WebP)
- Smart positioning (bottom-right / centered with margin)
"""

from __future__ import annotations

import io
from typing import Literal

import structlog
from PIL import Image, ImageDraw, ImageFont

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
