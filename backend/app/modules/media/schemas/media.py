"""Pydantic v2 schemas for the media asset management module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MediaAssetResponse(BaseModel):
    """Schema for returning media asset details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    uploader_id: Optional[uuid.UUID] = None
    file_name: str
    file_path: str
    file_url: str
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
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
