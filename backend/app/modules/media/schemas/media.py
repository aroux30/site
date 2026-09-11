"""Pydantic v2 schemas for the media asset management module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaAssetResponse(BaseModel):
    """Schema for returning media asset details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    uploader_id: uuid.UUID | None = None
    file_name: str
    file_path: str
    file_url: str
    file_size: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    alt_text: str | None = None
    created_at: datetime
    updated_at: datetime


class MediaAssetListResponse(BaseModel):
    """Paginated list of media assets."""

    items: list[MediaAssetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MediaUploadResponse(BaseModel):
    """Response returned immediately after file upload."""

    asset: MediaAssetResponse
    message: str = "File uploaded successfully"
