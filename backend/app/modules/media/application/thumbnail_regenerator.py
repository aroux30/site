"""Regenerate thumbnails for all existing media assets (WordPress parity).

Batch job that re-creates thumbnail sizes for all image assets in the library.
Useful after changing thumbnail dimensions in site options, or after migration.

Usage:
    from app.modules.media.application.thumbnail_regenerator import regenerate_all
    stats = await regenerate_all(db)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.config.settings import get_settings
from app.modules.media.application.image_processor import ImageProcessor
from app.modules.media.application.storage_paths import candidate_sources
from app.modules.media.domain.models import MediaAsset

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

IMAGE_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def _resolve_source(asset: MediaAsset) -> Path | None:
    """The on-disk original for an asset, or None when it is gone.

    ``asset.file_path`` is a root-relative key (``media/<name>``), not a path
    the filesystem can open from the process's working directory — passing it
    straight to Pillow made every regeneration fail. The shared layout helper
    resolves it the same way the serving route does: the served URL first, the
    stored key as fallback.
    """
    base_dir = Path(getattr(get_settings(), "UPLOAD_DIR", "media"))
    candidates = candidate_sources(base_dir, asset.file_url or "", asset.file_path)
    return next((p for p in candidates if p.exists()), None)


async def regenerate_all(db: "AsyncSession") -> dict[str, int]:
    """Regenerate thumbnails for all image assets. Returns stats."""
    stmt = select(MediaAsset).where(
        MediaAsset.mime_type.in_(IMAGE_MIME_PREFIXES)
    ).order_by(MediaAsset.created_at.asc())

    assets = (await db.execute(stmt)).scalars().all()
    stats = {"total": len(assets), "success": 0, "failed": 0, "skipped": 0}

    for asset in assets:
        try:
            source = _resolve_source(asset)
            if source is None:
                stats["skipped"] += 1
                logger.warning("thumbnail_regen_no_source", asset_id=str(asset.id))
                continue
            sizes = await ImageProcessor.generate_thumbnails(str(source), db=db)
            if sizes:
                stats["success"] += 1
            else:
                stats["skipped"] += 1
        except Exception as exc:
            stats["failed"] += 1
            logger.warning("thumbnail_regen_failed", asset_id=str(asset.id), error=str(exc))

    logger.info("thumbnails_regenerated", **stats)
    return stats


async def regenerate_single(db: "AsyncSession", asset_id: uuid.UUID) -> dict[str, str]:
    """Regenerate thumbnails for a single asset."""
    asset = await db.get(MediaAsset, asset_id)
    if not asset:
        return {"error": "Asset not found"}
    source = _resolve_source(asset)
    if source is None:
        # Distinguish "nothing to do" from "worked": the stored row may point at
        # a file that no longer exists on disk, which is a real operator-facing
        # problem rather than a silent no-op.
        return {
            "error": "Source file not found on disk",
            "asset_id": str(asset_id),
            "file_path": asset.file_path,
        }
    sizes = await ImageProcessor.generate_thumbnails(str(source), db=db)
    return sizes
