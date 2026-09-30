"""Pydantic v2 schemas for the media asset management module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


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
    caption: str | None = None
    description: str | None = None
    folder: str | None = None
    focal_x: float | None = None
    focal_y: float | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_alt_text(self) -> bool:
        """Whether this image is missing the alt text it should carry.

        WordPress shows a per-row "no alt text" warning for exactly this
        reason: the image still renders and still saves, it is just invisible
        to screen readers and to image search. Computed rather than stored so
        there is no second source of truth to keep in step with ``alt_text``.

        Only images are flagged — alt text is meaningless for a PDF, and
        warning about one would train the operator to ignore the warning.
        """
        return self.mime_type.startswith("image/") and not (self.alt_text or "").strip()


class MediaAssetUpdateRequest(BaseModel):
    """Schema for updating media asset metadata."""

    alt_text: str | None = None
    caption: str | None = None
    description: str | None = None
    folder: str | None = None


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


class MediaBatchUploadError(BaseModel):
    """One file that failed inside a batch upload, with the reason."""

    filename: str
    error: str


class MediaBatchUploadResponse(BaseModel):
    """Result of a batch upload: per-file successes and failures.

    Files are processed independently — a rejected file never rolls back the
    ones already accepted.
    """

    uploaded: list[MediaAssetResponse] = []
    errors: list[MediaBatchUploadError] = []
