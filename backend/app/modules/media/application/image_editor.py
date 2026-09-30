"""Image editing service: crop, resize, rotate (WordPress parity).

Provides server-side image manipulation for the admin media library.
Uses Pillow for transformations. Each edit creates a new file (non-destructive),
preserving the original upload.

Usage:
    from app.modules.media.application.image_editor import ImageEditor
    editor = ImageEditor()
    new_path = await editor.crop(file_path, x=100, y=50, width=400, height=300)
    new_path = await editor.resize(file_path, width=800, height=600)
    new_path = await editor.rotate(file_path, degrees=90)
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# A module-level ``MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT",
# "media/uploads"))`` used to live here. It was never read, and it was wrong:
# no env file sets MEDIA_ROOT and ``media/uploads`` is never created, while
# the uploader writes to ``<UPLOAD_DIR>/media``. Anything that genuinely needs
# the directory should ask storage_paths, not reconstruct it here.


class ImageEditor:
    """Server-side image manipulation (non-destructive)."""

    @staticmethod
    def _output_path(original: str, suffix: str) -> Path:
        """Generate output path: original-name_suffix.ext"""
        p = Path(original)
        stem = p.stem
        ext = p.suffix or ".jpg"
        output = p.parent / f"{stem}_{suffix}{ext}"
        return output

    @staticmethod
    async def crop(
        file_path: str,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> str:
        """Crop an image to the specified rectangle. Returns new file path."""
        try:
            from PIL import Image

            img = Image.open(file_path)
            cropped = img.crop((x, y, x + width, y + height))
            output = ImageEditor._output_path(file_path, f"crop_{width}x{height}")
            cropped.save(str(output), quality=90)
            logger.info("image_cropped", src=file_path, output=str(output))
            return str(output)
        except ImportError:
            logger.warning("pillow_not_installed")
            raise
        except Exception as exc:
            logger.error("image_crop_failed", src=file_path, error=str(exc))
            raise

    @staticmethod
    async def resize(
        file_path: str,
        *,
        width: int,
        height: int | None = None,
        maintain_aspect: bool = True,
    ) -> str:
        """Resize an image. If height is None and maintain_aspect, auto-calculates."""
        try:
            from PIL import Image

            img = Image.open(file_path)
            if maintain_aspect and height is None:
                ratio = width / img.width
                height = int(img.height * ratio)
            elif height is None:
                height = img.height

            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            output = ImageEditor._output_path(file_path, f"resize_{width}x{height}")
            resized.save(str(output), quality=90)
            logger.info("image_resized", src=file_path, output=str(output))
            return str(output)
        except ImportError:
            logger.warning("pillow_not_installed")
            raise
        except Exception as exc:
            logger.error("image_resize_failed", src=file_path, error=str(exc))
            raise

    @staticmethod
    async def rotate(
        file_path: str,
        *,
        degrees: int = 90,
    ) -> str:
        """Rotate an image by the specified degrees (90, 180, 270). Returns new file path."""
        try:
            from PIL import Image

            img = Image.open(file_path)
            rotated = img.rotate(-degrees, expand=True)  # negative = clockwise
            output = ImageEditor._output_path(file_path, f"rot{degrees}")
            rotated.save(str(output), quality=90)
            logger.info("image_rotated", src=file_path, degrees=degrees, output=str(output))
            return str(output)
        except ImportError:
            logger.warning("pillow_not_installed")
            raise
        except Exception as exc:
            logger.error("image_rotate_failed", src=file_path, error=str(exc))
            raise

    @staticmethod
    async def flip(
        file_path: str,
        *,
        horizontal: bool = True,
    ) -> str:
        """Flip an image horizontally or vertically."""
        try:
            from PIL import Image

            img = Image.open(file_path)
            if horizontal:
                flipped = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                suffix = "fliph"
            else:
                flipped = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                suffix = "flipv"
            output = ImageEditor._output_path(file_path, suffix)
            flipped.save(str(output), quality=90)
            logger.info("image_flipped", src=file_path, output=str(output))
            return str(output)
        except ImportError:
            logger.warning("pillow_not_installed")
            raise
        except Exception as exc:
            logger.error("image_flip_failed", src=file_path, error=str(exc))
            raise
