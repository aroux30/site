"""Media asset API endpoints."""

from __future__ import annotations

import math
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.media.application.media_service import MediaService
from app.modules.media.schemas.media import (
    MediaAssetListResponse,
    MediaAssetResponse,
    MediaUploadResponse,
)

router = APIRouter()


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload media file",
)
async def upload_media(
    file: UploadFile = File(..., description="File to upload (max 10MB, images/pdf)"),
    alt_text: Optional[str] = Form(None, description="Accessible description"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    """Upload an image or document, validate MIME/content, and return file URL."""
    asset = await MediaService.upload_file(
        db,
        file=file,
        uploader_id=user_id,
        alt_text=alt_text,
    )
    await db.commit()
    return MediaUploadResponse(
        asset=MediaAssetResponse.model_validate(asset),
        message="File uploaded successfully",
    )


@router.get(
    "",
    response_model=MediaAssetListResponse,
    summary="List media assets",
)
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type prefix e.g. 'image/'"),
    db: AsyncSession = Depends(get_db),
) -> MediaAssetListResponse:
    """List uploaded media assets with pagination."""
    items, total = await MediaService.list_assets(
        db, page=page, page_size=page_size, mime_prefix=mime_type
    )
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    return MediaAssetListResponse(
        items=[MediaAssetResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Get media asset by ID",
)
async def get_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Get metadata for a single media asset."""
    asset = await MediaService.get_asset(db, asset_id)
    return MediaAssetResponse.model_validate(asset)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media asset",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def delete_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a media asset."""
    await MediaService.delete_asset(db, asset_id)
    await db.commit()
