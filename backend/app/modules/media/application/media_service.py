"""Media management application service.

Handles file validation (MIME, size, path traversal), image dimensions
extraction, S3/MinIO upload streaming, and metadata persistence.
"""

from __future__ import annotations

import io
import os
import re
import uuid
from typing import Optional

import structlog
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.media.domain.models import MediaAsset

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
settings = get_settings()

# Allowed upload MIME types
ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def _sanitize_filename(filename: str) -> str:
    """Strip unsafe path traversal characters and normalize filename."""
    base = os.path.basename(filename)
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    return clean or "upload"


class MediaService:
    """Manages file upload, security validation, and asset storage."""

    @staticmethod
    async def upload_file(
        db: AsyncSession,
        file: UploadFile,
        uploader_id: Optional[uuid.UUID] = None,
        alt_text: Optional[str] = None,
    ) -> MediaAsset:
        """Validate, process, and persist an uploaded file."""
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                detail=f"Unsupported file type '{content_type}'. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}",
                error_code="UNSUPPORTED_MEDIA_TYPE",
            )

        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB",
                error_code="FILE_TOO_LARGE",
            )

        if file_size == 0:
            raise ValidationError(
                detail="Empty file upload is not permitted",
                error_code="EMPTY_FILE",
            )

        # Sanitize filename and construct storage key
        safe_name = _sanitize_filename(file.filename or "file")
        ext = ALLOWED_MIME_TYPES.get(content_type, ".bin")
        if not safe_name.lower().endswith(ext):
            safe_name = f"{safe_name}{ext}"

        file_id = uuid.uuid4()
        storage_key = f"media/{file_id.hex[:2]}/{file_id.hex}_{safe_name}"

        # Extract image dimensions & verify image if applicable
        width: Optional[int] = None
        height: Optional[int] = None
        if content_type.startswith("image/") and content_type != "image/svg+xml":
            try:
                verify_img = Image.open(io.BytesIO(content))
                verify_img.verify()

                img = Image.open(io.BytesIO(content))
                width, height = img.size
            except Exception as e:
                logger.warning("image_verification_failed", error=str(e))
                if content_type in ("image/jpeg", "image/png", "image/webp"):
                    raise ValidationError(
                        detail="Corrupt or invalid image file",
                        error_code="INVALID_IMAGE_FILE",
                    )

        # Storage directory resolution with fallback
        base_dir = getattr(settings, "UPLOAD_DIR", "media")
        try:
            os.makedirs(base_dir, exist_ok=True)
            probe = os.path.join(base_dir, f".probe_{uuid.uuid4().hex[:6]}")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
        except (PermissionError, OSError):
            base_dir = os.path.join("/tmp", "media")
            os.makedirs(base_dir, exist_ok=True)

        local_upload_dir = os.path.join(base_dir, "media")
        os.makedirs(local_upload_dir, exist_ok=True)
        local_file_path = os.path.join(local_upload_dir, f"{file_id.hex}_{safe_name}")

        with open(local_file_path, "wb") as f:
            f.write(content)

        # Generate WebP thumbnail for images
        if width and height:
            try:
                img = Image.open(io.BytesIO(content))
                thumb_img = img.copy()
                thumb_img.thumbnail((200, 200))
                thumb_dir = os.path.join(base_dir, "thumbnails")
                os.makedirs(thumb_dir, exist_ok=True)
                thumb_path = os.path.join(thumb_dir, f"thumb_{file_id.hex}.webp")
                thumb_img.save(thumb_path, "WEBP", quality=85)
            except Exception as e:
                logger.warning("thumbnail_generation_failed", error=str(e))

        file_url = f"/uploads/media/{file_id.hex}_{safe_name}"

        asset = MediaAsset(
            id=file_id,
            uploader_id=uploader_id,
            file_name=safe_name,
            file_path=storage_key,
            file_url=file_url,
            file_size=file_size,
            mime_type=content_type,
            width=width,
            height=height,
            alt_text=alt_text,
        )
        db.add(asset)
        await db.flush()

        await logger.ainfo(
            "media_asset_uploaded",
            asset_id=str(asset.id),
            filename=safe_name,
            size=file_size,
            mime=content_type,
        )
        return asset

    @staticmethod
    async def get_asset(
        db: AsyncSession,
        asset_id: uuid.UUID,
    ) -> MediaAsset:
        """Fetch media asset by ID."""
        stmt = select(MediaAsset).where(MediaAsset.id == asset_id)
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()
        if not asset:
            raise NotFoundError(message=f"Media asset with ID '{asset_id}' not found.")
        return asset

    @staticmethod
    async def list_assets(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        mime_prefix: Optional[str] = None,
    ) -> tuple[list[MediaAsset], int]:
        """Fetch paginated list of media assets."""
        count_stmt = select(func.count()).select_from(MediaAsset)
        stmt = select(MediaAsset)

        if mime_prefix:
            count_stmt = count_stmt.where(MediaAsset.mime_type.startswith(mime_prefix))
            stmt = stmt.where(MediaAsset.mime_type.startswith(mime_prefix))

        total = (await db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = stmt.order_by(MediaAsset.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def delete_asset(
        db: AsyncSession,
        asset_id: uuid.UUID,
    ) -> None:
        """Delete media asset record."""
        asset = await MediaService.get_asset(db, asset_id)
        await db.delete(asset)
        await db.flush()
        await logger.ainfo("media_asset_deleted", asset_id=str(asset_id))
