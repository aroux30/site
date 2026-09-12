"""Unit tests for media upload validation and thumbnail processing."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile
from PIL import Image

from app.core.exceptions.handlers import ValidationError
from app.modules.media.application.media_service import MediaService, _sanitize_filename


def test_sanitize_filename():
    """Verify filename sanitization prevents path traversal."""
    assert _sanitize_filename("../../../etc/passwd") == "passwd"
    assert _sanitize_filename("image..png") == "image..png"
    assert _sanitize_filename("weird/path/file.jpg") == "file.jpg"
    assert _sanitize_filename("!@#$%^&*()file.png") == "__________file.png"


@pytest.mark.asyncio
async def test_upload_unsupported_mime_type_rejected():
    """Verify unsupported MIME type raises ValidationError."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "script.exe"
    mock_file.content_type = "application/x-msdownload"
    mock_file.read = AsyncMock(return_value=b"MZ\x90\x00")

    mock_db = MagicMock()

    with pytest.raises(ValidationError) as exc_info:
        await MediaService.upload_file(mock_db, mock_file)
    assert "Unsupported file type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_empty_file_rejected():
    """Verify empty file raises ValidationError."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "empty.jpg"
    mock_file.content_type = "image/jpeg"
    mock_file.read = AsyncMock(return_value=b"")

    mock_db = MagicMock()

    with pytest.raises(ValidationError) as exc_info:
        await MediaService.upload_file(mock_db, mock_file)
    assert "Empty file upload is not permitted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_corrupt_image_rejected():
    """Verify corrupt image content is caught by Pillow validation."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "corrupt.png"
    mock_file.content_type = "image/png"
    mock_file.read = AsyncMock(return_value=b"\x89PNG\r\n\x1a\ncorruptpayloadhere")

    mock_db = MagicMock()

    with pytest.raises(ValidationError) as exc_info:
        await MediaService.upload_file(mock_db, mock_file)
    assert "Corrupt or invalid image file" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_valid_image_extracts_dimensions():
    """Verify valid image upload generates dimensions and adds asset."""
    # Create valid in-memory 100x80 red PNG
    img_byte_arr = io.BytesIO()
    img = Image.new("RGB", (100, 80), color="red")
    img.save(img_byte_arr, format="PNG")
    content = img_byte_arr.getvalue()

    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test_image.png"
    mock_file.content_type = "image/png"
    mock_file.read = AsyncMock(return_value=content)

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    uploader_id = uuid.uuid4()
    asset = await MediaService.upload_file(
        mock_db,
        mock_file,
        uploader_id=uploader_id,
        alt_text="تست تصویر",
    )

    assert asset.file_name.endswith(".png")
    assert asset.width == 100
    assert asset.height == 80
    assert asset.alt_text == "تست تصویر"
    assert asset.uploader_id == uploader_id
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
