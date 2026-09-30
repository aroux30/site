"""Image optimization: compress images on upload (WordPress parity).

Automatically optimizes uploaded images by compressing JPEG quality,
converting to WebP where supported, and stripping unnecessary metadata.

Usage:
    from app.modules.media.application.image_optimizer import ImageOptimizer
    result = await ImageOptimizer.optimize(file_path)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ImageOptimizer:
    """Compress and optimize images."""

    @staticmethod
    async def optimize(
        file_path: str,
        *,
        quality: int = 82,
        convert_to_webp: bool = False,
        strip_metadata: bool = True,
        max_width: int | None = 2560,
        max_height: int | None = 2560,
    ) -> dict[str, Any]:
        """Optimize an image file in-place or create an optimized copy.

        Returns stats about the optimization (original_size, new_size, savings_pct).
        """
        try:
            from PIL import Image

            original_size = os.path.getsize(file_path)
            img = Image.open(file_path)
            p = Path(file_path)

            # Resize if too large
            resized = False
            if max_width and max_height:
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    resized = True

            # Strip EXIF if requested
            if strip_metadata:
                data = list(img.getdata())
                clean = Image.new(img.mode, img.size)
                clean.putdata(data)
                img = clean

            # Save optimized
            if convert_to_webp:
                output_path = p.with_suffix(".webp")
                img.save(str(output_path), "WEBP", quality=quality)
            else:
                output_path = p
                if img.mode in ("RGBA", "P") and p.suffix.lower() in (".jpg", ".jpeg"):
                    img = img.convert("RGB")
                img.save(str(output_path), quality=quality, optimize=True)

            new_size = os.path.getsize(str(output_path))
            savings = round((1 - new_size / original_size) * 100, 1) if original_size > 0 else 0

            logger.info(
                "image_optimized",
                src=file_path,
                original=original_size,
                optimized=new_size,
                savings_pct=savings,
            )
            return {
                "original_size": original_size,
                "new_size": new_size,
                "savings_pct": savings,
                "resized": resized,
                "output_path": str(output_path),
                "format": "webp" if convert_to_webp else p.suffix.lstrip("."),
            }
        except ImportError:
            logger.warning("pillow_not_installed")
            return {"error": "Pillow not installed"}
        except Exception as exc:
            logger.error("image_optimize_failed", error=str(exc))
            return {"error": str(exc)}
