"""Media management application service.

Handles file validation (MIME, size, path traversal), image dimensions
extraction, and metadata persistence. Writes go to the local ``UPLOAD_DIR``
volume; the S3/MinIO settings in core.config exist but no code path reads
them, so do not assume object storage here.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from PIL import Image, ImageOps
from sqlalchemy import func, or_, select

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.media.application.image_processor import (
    IMAGE_SIZES,
    ImageProcessor,
    derived_size_name,
)
from app.modules.media.application.storage_paths import (
    MEDIA_SUBDIR,
    candidate_sources,
)
from app.modules.media.application.watermark_service import maybe_watermark_uploaded_file
from app.modules.media.domain.models import MediaAsset
from app.modules.media.schemas.media import (
    MediaAssetResponse,
    MediaBatchUploadError,
    MediaBatchUploadResponse,
)

if TYPE_CHECKING:
    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
settings = get_settings()

#: Upper bound on files per batch upload request.
MAX_BATCH_FILES = 20

# Allowed upload MIME types.
#
# image/svg+xml is deliberately NOT allowed: SVG can carry embedded scripts
# and is served same-origin from /uploads/media/, which makes a stored-XSS
# account-takeover vector. Sanitizing SVG safely requires a dedicated
# parser/sanitizer dependency; until one is adopted and the serving path
# sets Content-Disposition/ CSP nonce handling, SVG uploads are rejected.
ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",          # animated banners; first frame only is processed
    "image/avif": ".avif",
    "application/pdf": ".pdf",
    # Audio: the blog's `audio` post format had nothing it could attach.
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".weba",
    # Video: likewise for the `video` post format.
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
}

#: Media categories, used to pick a size limit and to decide whether the image
#: pipeline (thumbnails, EXIF, focal point) applies at all.
IMAGE_MIME_TYPES = frozenset(
    m for m in ALLOWED_MIME_TYPES if m.startswith("image/")
)
AUDIO_MIME_TYPES = frozenset(
    m for m in ALLOWED_MIME_TYPES if m.startswith("audio/")
)
VIDEO_MIME_TYPES = frozenset(
    m for m in ALLOWED_MIME_TYPES if m.startswith("video/")
)

#: Non-image uploads get a larger ceiling than images: a short video is
#: routinely larger than a 10 MB photo, and a 10 MB cap would make the
#: `video`/`audio` post formats unusable. The image cap is unchanged so a
#: page cannot be filled with huge photographs.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB for still images and PDFs
MAX_MEDIA_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB for audio/video

MEDIA_CATEGORIES: dict[str, str] = {
    **{m: "image" for m in IMAGE_MIME_TYPES},
    **{m: "audio" for m in AUDIO_MIME_TYPES},
    **{m: "video" for m in VIDEO_MIME_TYPES},
    "application/pdf": "document",
}


def max_size_for(mime_type: str) -> int:
    """The size ceiling that applies to a given MIME type."""
    return (
        MAX_MEDIA_FILE_SIZE_BYTES
        if MEDIA_CATEGORIES.get(mime_type) in ("audio", "video")
        else MAX_FILE_SIZE_BYTES
    )


def category_for(mime_type: str) -> str:
    """``image`` | ``audio`` | ``video`` | ``document``, or ``"unknown"``."""
    return MEDIA_CATEGORIES.get(mime_type, "unknown")


#: Magic-byte signatures. Checked in order, so the more specific container
#: prefixes come before the generic ones they share.
_MAGIC_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
    (b"ID3", "audio/mpeg"),
    (b"\x1aE\xdf\xa3", "video/mp4"),        # Matroska/WebM family
)


def _sniff_mime(content: bytes, declared: str) -> str:
    """Return the MIME type the bytes actually are, else the declared one.

    A client-supplied Content-Type is a hint, not evidence. When the bytes
    identify as something the allowlist knows, they win — otherwise a caller
    could declare ``image/jpeg`` and store arbitrary bytes under an image
    extension.
    """
    head = content[:16]
    detected: str | None = None
    for signature, mime in _MAGIC_SIGNATURES:
        if head.startswith(signature):
            detected = mime
            break
    if detected is None and len(content) >= 12 and content[4:8] == b"ftyp":
        # ISO-BMFF: MP4, M4A, HEIF/AVIF and QuickTime all open with a box
        # size then 'ftyp'. The major brand at offset 8 tells them apart.
        # The AVIF and HEIC brands are the ones that matter most here: without
        # them an AVIF fell through to the video/mp4 default, took the 100 MB
        # video ceiling instead of the 10 MB image one, and — because the image
        # pipeline is gated on ``content_type.startswith("image/")`` — was
        # stored with no dimensions and no derivatives at all.
        brand = content[8:12]
        if brand in (b"avif", b"avis"):
            detected = "image/avif"
        elif brand in (b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx"):
            detected = "image/heic"
        elif brand in (b"qt  ", b"M4V "):
            detected = "video/quicktime"
        elif brand in (b"M4A ", b"M4B "):
            detected = "audio/mp4"
        else:
            detected = "video/mp4"
    if detected is None and head[:4] == b"RIFF":
        # RIFF is a container: WEBP, WAV and AVI all start with it.
        detected = {
            b"WEBP": "image/webp",
            b"WAVE": "audio/wav",
            b"AVI ": "video/x-msvideo",
        }.get(content[8:12], declared)
    if detected is None and head[:4] == b"OggS":
        detected = "audio/ogg"
    if detected is None:
        # No signature matched (e.g. a bare m4a with a weak container). Fall
        # back to the declared type, which the allowlist check then vets.
        return declared
    return detected


def _sanitize_filename(filename: str) -> str:
    """Strip unsafe path traversal characters and normalize filename."""
    base = os.path.basename(filename)
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    return clean or "upload"


def _sanitize_folder(folder: str | None) -> str | None:
    """Normalize a folder path; reject traversal. ``None`` stays ``None`` (root)."""
    if not folder:
        return None
    parts = [p for p in re.split(r"[/\\]+", folder.strip()) if p and p not in {".", ".."}]
    if not parts:
        return None
    clean = "/".join(re.sub(r"[^a-zA-Z0-9_\-؀-ۿ ]", "_", p).strip() for p in parts)
    return clean[:300] or None


def _error_message(exc: Exception) -> str:
    """Human-facing message for the batch error report (detail over str)."""
    detail = getattr(exc, "detail", None)
    return str(detail) if detail else str(exc)


#: Read granularity for the streaming upload guard. Small enough that a client
#: streaming far past the ceiling is cut off quickly, large enough that a normal
#: upload is not dominated by per-chunk await overhead.
_UPLOAD_CHUNK_BYTES = 1024 * 1024

#: Hardest ceiling any category can impose. Used as the read cap when the
#: declared type is unknown or absent, so an unlabelled body cannot stream
#: unbounded even before the MIME is sniffed. The per-category cap is applied
#: again after sniffing, where the real type is known.
_UPLOAD_ABSOLUTE_MAX_BYTES = 100 * 1024 * 1024


async def _read_capped(file: UploadFile, max_bytes: int | None) -> bytes:
    """Read an upload, refusing to buffer more than it is allowed to.

    ``await file.read()`` with no argument loads the entire body into memory
    before any size check runs, so the 100 MB ceiling was enforced only *after*
    the allocation it was meant to prevent — and a batch of 20 could buffer
    2 GB in one request. This reads in chunks and stops as soon as the running
    total passes the cap, so the peak allocation tracks the ceiling instead of
    the payload.

    ``max_bytes`` is a caller-supplied cap (the return-proof route sets 10 MB).
    It can only tighten the read, never widen it: the read cap is the minimum of
    the global ceiling and whatever the caller asked for, and the per-category
    limit is still applied after sniffing.

    Raises ``ValidationError`` with ``FILE_TOO_LARGE`` once the cap is passed.
    """
    cap = min(_UPLOAD_ABSOLUTE_MAX_BYTES, max_bytes or _UPLOAD_ABSOLUTE_MAX_BYTES)

    # A declared Content-Length lets an honest oversize upload be refused
    # before a single byte is read. It is a hint, not a guarantee — a lying or
    # absent header falls through to the streaming check below, which is the
    # one that actually holds.
    declared = file.headers.get("content-length") if file.headers else None
    if declared and declared.isdigit() and int(declared) > cap:
        raise ValidationError(
            detail=f"File size exceeds maximum allowed limit of {cap // (1024 * 1024)}MB",
            error_code="FILE_TOO_LARGE",
        )

    chunks: list[bytes] = []
    running = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        running += len(chunk)
        if running > cap:
            raise ValidationError(
                detail=f"File size exceeds maximum allowed limit of {cap // (1024 * 1024)}MB",
                error_code="FILE_TOO_LARGE",
            )
        chunks.append(chunk)
    return b"".join(chunks)


class MediaService:
    """Manages file upload, security validation, and asset storage."""

    @staticmethod
    async def upload_file(
        db: AsyncSession,
        file: UploadFile,
        uploader_id: uuid.UUID | None = None,
        alt_text: str | None = None,
        folder: str | None = None,
        max_bytes: int | None = None,
    ) -> MediaAsset:
        """Validate, process, and persist an uploaded file.

        ``max_bytes`` lets a narrow caller cap the read below the global
        100 MB ceiling — the return-proof route does, so a shopper upload
        cannot allocate the same buffer a staff video upload would.
        """
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                detail=f"Unsupported file type '{content_type}'. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}",  # noqa: E501
                error_code="UNSUPPORTED_MEDIA_TYPE",
            )

        content = await _read_capped(file, max_bytes)
        file_size = len(content)

        # The client-declared Content-Type is a hint, not evidence: a request
        # can claim image/jpeg and carry anything. Confirm the bytes actually
        # match before trusting the category, the size ceiling, or the image
        # pipeline. Non-images (audio/video/pdf) are checked by magic prefix.
        detected = _sniff_mime(content, content_type)
        if detected != content_type:
            content_type = detected

        # The ceiling depends on the category: a short video is routinely
        # larger than 10 MB, and the image cap is deliberately left alone.
        # A caller-supplied ceiling can only tighten this, never widen it —
        # otherwise a narrow route could raise its own limit by passing one.
        size_limit = max_size_for(content_type)
        if max_bytes is not None:
            size_limit = min(size_limit, max_bytes)
        if file_size > size_limit:
            raise ValidationError(
                detail=f"File size exceeds maximum allowed limit of {size_limit // (1024 * 1024)}MB",  # noqa: E501
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
        # Defense-in-depth: the extension reaching a filesystem path must be a
        # short lowercase token (allowlist values are constants, this guards
        # against configuration drift and validates the chain explicitly).
        if not re.fullmatch(r"\.[a-z0-9]{2,5}", ext):
            raise ValidationError(
                detail="Configured file extension is invalid",
                error_code="INVALID_EXTENSION_CONFIG",
            )
        if not safe_name.lower().endswith(ext):
            safe_name = f"{safe_name}{ext}"

        file_id = uuid.uuid4()
        # On-disk/URL name is fully server-generated (uuid + allowlisted
        # extension); the user-supplied name is kept only as DB metadata so no
        # untrusted text ever reaches a filesystem path.
        disk_name = file_id.hex + ext
        # Flat, matching the served URL exactly. This used to claim a sharded
        # layout (media/<hex[:2]>/<name>) that the upload never wrote, so the
        # column described a file that does not exist at that path.
        storage_key = f"media/{disk_name}"

        # Extract image dimensions & verify image if applicable
        width: int | None = None
        height: int | None = None
        if content_type.startswith("image/"):
            try:
                verify_img = Image.open(io.BytesIO(content))
                verify_img.verify()

                # A phone photo is usually stored with pixels in landscape and
                # an EXIF orientation tag saying "rotate me 90°". Nothing in the
                # pipeline honoured that tag, so the original was written
                # sideways and so was every derived size, the variant endpoint
                # and the storefront image. WordPress physically rotates the
                # stored file for the same reason
                # (wp-admin/includes/image.php:361-382).
                #
                # Applied to the bytes *before* they are written and before the
                # dimensions are read, so the stored original, the recorded
                # width/height and every derivative agree. ``exif_transpose``
                # is a no-op on an untagged image, so this costs nothing on the
                # files that were never rotated.
                #
                # Done before the EXIF-stripping save below, which is what
                # removes GPS and camera metadata from the stored original.
                try:
                    _opened = Image.open(io.BytesIO(content))
                    _transposed = ImageOps.exif_transpose(_opened)
                    if _transposed is not _opened:
                        buf = io.BytesIO()
                        # JPEG cannot carry alpha; PNG/WebP can, and forcing
                        # a lossy re-encode on a PNG would be a regression.
                        if content_type == "image/jpeg":
                            _transposed.convert("RGB").save(
                                buf, format="JPEG", quality=95
                            )
                        else:
                            _transposed.save(buf, format=_opened.format or "PNG")
                        content = buf.getvalue()
                        # The bytes changed, so the earlier len() is stale —
                        # the stored size and the size check must both see
                        # what is actually going to disk.
                        file_size = len(content)
                        logger.info("image_exif_orientation_applied")
                except Exception as e:  # noqa: BLE001 - never fail an upload on it
                    logger.warning("image_exif_transpose_failed", error=str(e))

                img = Image.open(io.BytesIO(content))
                width, height = img.size
            except Exception as e:
                logger.warning("image_verification_failed", error=str(e))
                if content_type in ("image/jpeg", "image/png", "image/webp"):
                    raise ValidationError(
                        detail="Corrupt or invalid image file",
                        error_code="INVALID_IMAGE_FILE",
                    ) from e

        # Storage directory resolution with fallback
        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        try:
            base_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240  # trivial local metadata operation
            probe = base_dir / f".probe_{uuid.uuid4().hex[:6]}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except (PermissionError, OSError):
            base_dir = Path(tempfile.gettempdir()) / "media"
            base_dir.mkdir(parents=True, exist_ok=True)

        local_upload_dir = Path(base_dir) / MEDIA_SUBDIR
        local_upload_dir.mkdir(parents=True, exist_ok=True)  # trivial local metadata operation
        # Same server-generated name as file_url: no untrusted text ever
        # reaches a filesystem path, and the served URL is a faithful
        # description of where the bytes actually live.
        local_file_path = local_upload_dir / disk_name

        local_file_path.write_bytes(content)

        # Generate WebP thumbnail for images
        if width and height:
            try:
                img = Image.open(io.BytesIO(content))
                thumb_img = img.copy()
                thumb_img.thumbnail((200, 200))
                thumb_dir = Path(base_dir) / "thumbnails"
                thumb_dir.mkdir(parents=True, exist_ok=True)
                thumb_path = thumb_dir / f"thumb_{file_id.hex}.webp"
                thumb_img.save(thumb_path, "WEBP", quality=85)
            except Exception as e:
                logger.warning("thumbnail_generation_failed", error=str(e))

            # The four registered sizes (thumbnail/medium/medium_large/large).
            # Nothing called this before, so a fresh upload only ever had the
            # 200px WebP above; the registered sizes were produced solely by the
            # regenerator, which could not resolve its own path. Runs on the
            # original, so the watermark step below marks the derived sizes too.
            try:
                await ImageProcessor.generate_thumbnails(str(local_file_path), db=db)
            except Exception as e:
                logger.warning("image_size_generation_failed", error=str(e))

        # Optional site-wide watermark (media_watermark_* site options),
        # applied after the original + thumbnail are written so both carry
        # the mark; variants rendered later from the original inherit it.
        # Best-effort by design: any failure logs and the upload continues
        # with the unwatermarked file.
        try:
            if await maybe_watermark_uploaded_file(
                db,
                file_path=local_file_path,
                mime_type=content_type,
                asset_hex=file_id.hex,
                base_dir=base_dir,
            ):
                file_size = local_file_path.stat().st_size
        except Exception as e:  # watermarking must never fail an upload
            logger.warning("media_watermark_step_failed", error=str(e))

        file_url = f"/uploads/media/{disk_name}"

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
            folder=_sanitize_folder(folder),
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
    async def upload_batch(
        db: AsyncSession,
        *,
        files: list[UploadFile],
        uploader_id: uuid.UUID | None = None,
        folder: str | None = None,
    ) -> MediaBatchUploadResponse:
        """Upload several files, each succeeding or failing independently.

        Every file runs through the same :meth:`upload_file` validation and
        processing (MIME whitelist, 10MB cap, optional watermark). A failed
        file is rolled back and reported in ``errors`` — it never poisons the
        files already accepted or the ones after it, so each file is committed
        as soon as it is processed.
        """
        if len(files) > MAX_BATCH_FILES:
            raise ValidationError(
                detail=f"Batch upload is limited to {MAX_BATCH_FILES} files per request",
                error_code="BATCH_TOO_LARGE",
            )

        uploaded: list[MediaAssetResponse] = []
        errors: list[MediaBatchUploadError] = []
        for file in files:
            filename = file.filename or "file"
            try:
                asset = await MediaService.upload_file(
                    db,
                    file=file,
                    uploader_id=uploader_id,
                    folder=folder,
                )
                await db.commit()
                uploaded.append(MediaAssetResponse.model_validate(asset))
            except Exception as exc:
                # Per-file isolation: discard this file's partial work, keep
                # the session usable for the remaining files.
                await db.rollback()
                errors.append(MediaBatchUploadError(filename=filename, error=_error_message(exc)))
                await logger.awarning(
                    "media_batch_upload_failed",
                    filename=filename,
                    error=str(exc),
                )
        await logger.ainfo(
            "media_batch_uploaded",
            requested=len(files),
            uploaded=len(uploaded),
            failed=len(errors),
        )
        return MediaBatchUploadResponse(uploaded=uploaded, errors=errors)

    @staticmethod
    async def register_derived_asset(
        db: AsyncSession,
        source_asset_id: uuid.UUID,
        edited_file_path: str,
        *,
        suffix: str,
        uploader_id: uuid.UUID | None = None,
    ) -> MediaAsset:
        """Register an edited image (crop/resize/rotate output) as a new asset.

        The editor wrote the bytes to a temp/derived path; this moves them into
        the media store under a server-generated name so the served URL matches
        where the bytes live, then records the new asset row.
        """
        source = await MediaService.get_asset(db, source_asset_id)
        edited = Path(edited_file_path)
        if not edited.is_file():
            raise ValidationError(
                detail="Edited image not found on disk",
                error_code="DERIVED_FILE_MISSING",
            )

        ext = edited.suffix.lower() or ".jpg"
        if not re.fullmatch(r"\.[a-z0-9]{2,5}", ext):
            ext = ".jpg"

        file_id = uuid.uuid4()
        disk_name = file_id.hex + ext
        content = edited.read_bytes()

        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        local_upload_dir = Path(base_dir) / MEDIA_SUBDIR
        local_upload_dir.mkdir(parents=True, exist_ok=True)
        local_file_path = local_upload_dir / disk_name
        local_file_path.write_bytes(content)

        width: int | None = None
        height: int | None = None
        try:
            with Image.open(io.BytesIO(content)) as img:
                width, height = img.size
        except Exception as exc:  # noqa: BLE001 — dimensions are metadata, not required
            logger.warning("derived_image_dimension_read_failed", error=str(exc))

        stem = Path(source.file_name).stem
        asset = MediaAsset(
            id=file_id,
            uploader_id=uploader_id or source.uploader_id,
            file_name=f"{stem}_{suffix}{ext}",
            file_path=f"media/{disk_name}",
            file_url=f"/uploads/media/{disk_name}",
            file_size=len(content),
            mime_type=source.mime_type,
            width=width,
            height=height,
            alt_text=source.alt_text,
            folder=source.folder,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)

        # The derived file is now owned by the media store; drop the temp copy.
        try:
            edited.unlink(missing_ok=True)
        except OSError:
            pass

        await logger.ainfo(
            "media_derived_asset_created",
            asset_id=str(asset.id),
            source_id=str(source_asset_id),
            suffix=suffix,
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
            raise NotFoundError("MediaAsset", f"Media asset with ID '{asset_id}' not found.")
        return asset

    @staticmethod
    async def list_assets(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        mime_prefix: str | None = None,
        folder: str | None = None,
        search: str | None = None,
    ) -> tuple[list[MediaAsset], int]:
        """Fetch paginated list of media assets, optionally scoped to a folder.

        ``search`` matches the operator-visible columns — the stored file name
        and the alt text — because those are the two strings an operator
        actually knows an asset by. The on-disk name is a server-generated uuid,
        so searching it would never match anything a human typed.
        """
        count_stmt = select(func.count()).select_from(MediaAsset)
        stmt = select(MediaAsset)

        if mime_prefix:
            count_stmt = count_stmt.where(MediaAsset.mime_type.startswith(mime_prefix))
            stmt = stmt.where(MediaAsset.mime_type.startswith(mime_prefix))

        if search and (term := search.strip()):
            like_q = f"%{term}%"
            condition = or_(
                MediaAsset.file_name.ilike(like_q),
                MediaAsset.alt_text.ilike(like_q),
            )
            count_stmt = count_stmt.where(condition)
            stmt = stmt.where(condition)

        if folder is not None:
            clean = _sanitize_folder(folder)
            if clean is None:
                # Root folder: assets with no folder assigned
                count_stmt = count_stmt.where(MediaAsset.folder.is_(None))
                stmt = stmt.where(MediaAsset.folder.is_(None))
            else:
                # Exact folder or any depth below it (Strapi-style tree filter)
                count_stmt = count_stmt.where(
                    (MediaAsset.folder == clean) | (MediaAsset.folder.startswith(clean + "/"))
                )
                stmt = stmt.where(
                    (MediaAsset.folder == clean) | (MediaAsset.folder.startswith(clean + "/"))
                )

        total = (await db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = stmt.order_by(MediaAsset.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def list_folders(db: AsyncSession) -> list[dict[str, Any]]:
        """Distinct folder paths with asset counts, for the admin folder tree."""
        stmt = (
            select(MediaAsset.folder, func.count())
            .where(MediaAsset.folder.is_not(None))
            .group_by(MediaAsset.folder)
            .order_by(MediaAsset.folder)
        )
        rows = (await db.execute(stmt)).all()
        return [{"path": folder, "asset_count": count} for folder, count in rows]

    @staticmethod
    async def move_to_folder(
        db: AsyncSession, asset_ids: list[uuid.UUID], folder: str | None
    ) -> int:
        """Move assets into a folder (or root when ``folder`` is None)."""
        clean = _sanitize_folder(folder)
        moved = 0
        for asset_id in asset_ids:
            asset = await MediaService.get_asset(db, asset_id)
            asset.folder = clean
            moved += 1
        await db.flush()
        await logger.ainfo("media_assets_moved", count=moved, folder=clean)
        return moved

    @staticmethod
    async def set_focal_point(
        db: AsyncSession, asset_id: uuid.UUID, focal_x: float, focal_y: float
    ) -> MediaAsset:
        """Set the smart-crop focal point (relative 0..1 coordinates)."""
        if not (0.0 <= focal_x <= 1.0) or not (0.0 <= focal_y <= 1.0):
            raise ValidationError(
                detail="Focal point coordinates must be between 0 and 1",
                error_code="BAD_FOCAL_POINT",
            )
        asset = await MediaService.get_asset(db, asset_id)
        asset.focal_x = focal_x
        asset.focal_y = focal_y
        await db.flush()
        await logger.ainfo("media_focal_point_set", asset_id=str(asset_id))
        return asset

    @staticmethod
    async def get_image_variant(
        db: AsyncSession,
        asset_id: uuid.UUID,
        *,
        width: int | None = None,
        height: int | None = None,
        quality: int = 82,
        fmt: str = "webp",
    ) -> tuple[bytes, str]:
        """Render an on-the-fly resized image variant (Strapi/Payload-style).

        Variants are cached on disk under ``variants/`` keyed by asset id and
        parameter hash, so repeated requests are served without re-encoding.
        Returns ``(content_bytes, mime_type)``.
        """
        if fmt not in {"webp", "jpeg", "png"}:
            raise ValidationError(detail=f"Unsupported variant format '{fmt}'", error_code="BAD_FORMAT")
        for value in (width, height):
            if value is not None and not (1 <= value <= 4096):
                raise ValidationError(detail="Variant dimensions must be between 1 and 4096 px", error_code="BAD_SIZE")
        if width is None and height is None:
            raise ValidationError(detail="At least one of width/height is required", error_code="NO_SIZE")

        asset = await MediaService.get_asset(db, asset_id)
        if not (asset.mime_type or "").startswith("image/") or asset.mime_type == "image/svg+xml":
            raise ValidationError(detail="Only raster images can be resized", error_code="NOT_AN_IMAGE")

        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        # Shared layout helper: the served URL is authoritative and the stored
        # key is the fallback, so a row predating the alignment still resolves.
        candidates = candidate_sources(base_dir, asset.file_url or "", asset.file_path)
        source = next((p for p in candidates if p.exists()), candidates[0])
        if not source.exists():
            raise NotFoundError("MediaAsset", f"Source file for asset '{asset_id}' not found on disk.")

        focal_tag = ""
        if asset.focal_x is not None or asset.focal_y is not None:
            focal_tag = f"_f{asset.focal_x or 0.5:.2f}-{asset.focal_y or 0.5:.2f}"
        cache_key = f"{asset_id.hex}_{width or 0}x{height or 0}_q{quality}{focal_tag}.{fmt}"
        variant_dir = Path(base_dir) / "variants"
        variant_dir.mkdir(parents=True, exist_ok=True)
        variant_path = variant_dir / cache_key

        if variant_path.exists() and variant_path.stat().st_mtime >= source.stat().st_mtime:
            mime = {"webp": "image/webp", "jpeg": "image/jpeg", "png": "image/png"}[fmt]
            return variant_path.read_bytes(), mime

        with Image.open(source) as img:
            src_w, src_h = img.size
            target_w, target_h = width, height
            if target_w and not target_h:
                target_h = max(1, round(src_h * target_w / src_w))
            elif target_h and not target_w:
                target_w = max(1, round(src_w * target_h / src_h))
            # Both dimensions given → smart-crop to the aspect ratio around the
            # focal point (default: center), then resize (Strapi focal-point).
            if target_w and target_h and (target_w, target_h) != (src_w, src_h):
                target_ratio = target_w / target_h
                src_ratio = src_w / src_h
                if abs(target_ratio - src_ratio) > 1e-3:
                    fx = asset.focal_x if asset.focal_x is not None else 0.5
                    fy = asset.focal_y if asset.focal_y is not None else 0.5
                    if src_ratio > target_ratio:  # too wide → crop left/right
                        crop_w = int(src_h * target_ratio)
                        cx = min(max(int(fx * src_w), crop_w // 2), src_w - crop_w // 2)
                        img = img.crop((cx - crop_w // 2, 0, cx + crop_w // 2, src_h))  # type: ignore[assignment]
                    else:  # too tall → crop top/bottom
                        crop_h = int(src_w / target_ratio)
                        cy = min(max(int(fy * src_h), crop_h // 2), src_h - crop_h // 2)
                        img = img.crop((0, cy - crop_h // 2, src_w, cy + crop_h // 2))  # type: ignore[assignment]
                img = img.resize((target_w, target_h), Image.LANCZOS)  # type: ignore[assignment]
            save_kwargs: dict[str, Any] = {"quality": quality}
            if fmt in {"webp", "jpeg"}:
                if img.mode in ("RGBA", "P") and fmt == "jpeg":
                    img = img.convert("RGB")  # type: ignore[assignment]
            img.save(variant_path, fmt.upper() if fmt != "jpeg" else "JPEG", **save_kwargs)  # type: ignore[union-attr]

        mime = {"webp": "image/webp", "jpeg": "image/jpeg", "png": "image/png"}[fmt]
        await logger.ainfo(
            "media_variant_rendered", asset_id=str(asset_id), variant=cache_key
        )
        return variant_path.read_bytes(), mime

    @staticmethod
    def _remove_files(base_dir: Path, asset_hex: str, file_url: str | None) -> list[str]:
        """Delete the asset's stored file, its derived sizes and cached variants.

        Returns the paths that could not be removed. The DB row is the source
        of truth for the library listing, so a filesystem error here must not
        roll back the delete the operator asked for — but silently leaving
        bytes on disk is how the media store leaked in the first place, so the
        failures are returned and logged rather than swallowed.

        Names are derived exactly as the upload path wrote them:
        ``media/<disk_name>``, the sibling ``<disk_name stem>-<size><ext>`` files
        the image processor rendered, ``thumbnails/thumb_<hex>.webp`` and
        ``variants/<hex>_*`` (the variant cache is keyed by asset id, so every
        cached size for this asset shares the ``<hex>_`` prefix).

        The derived sizes are constructed from ``disk_name`` rather than
        globbed: they sit beside the original, so a ``*-medium*`` pattern would
        also match an unrelated asset that happened to share the prefix, and
        the stem here is a server-generated uuid. Only sizes larger than the
        original were ever rendered, so most of these candidates do not exist —
        hence ``missing_ok`` below, which keeps that silent.
        """
        failed: list[str] = []
        disk_name = Path(file_url or "").name
        candidates: list[Path] = [
            # The authoritative flat location, plus the sharded one a past
            # upload layout wrote to, so both eras are reclaimed.
            base_dir / MEDIA_SUBDIR / disk_name,
            base_dir / MEDIA_SUBDIR / asset_hex[:2] / disk_name,
            base_dir / "thumbnails" / f"thumb_{asset_hex}.webp",
        ]
        # Sibling files of the original, in the same flat media directory.
        # The names are pure functions of the server-generated disk name, so
        # no user text reaches the path and the orphan is reclaimed whatever
        # folder filter the operator happened to be looking at.
        if disk_name:
            stem = Path(disk_name).stem
            ext = Path(disk_name).suffix
            candidates.extend(
                base_dir / MEDIA_SUBDIR / derived_size_name(stem, size_name, ext)
                for size_name in IMAGE_SIZES
            )
        variant_dir = base_dir / "variants"
        if variant_dir.is_dir():
            # Globbing a server-generated hex id: no user-supplied text reaches
            # the pattern, so no path traversal is possible here.
            candidates.extend(variant_dir.glob(f"{asset_hex}_*"))
        for path in candidates:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover - depends on filesystem state
                failed.append(f"{path.name}: {exc}")
        return failed

    @staticmethod
    async def delete_asset(
        db: AsyncSession,
        asset_id: uuid.UUID,
    ) -> None:
        """Delete a media asset and every file it owns on disk.

        The record and the bytes are removed together: dropping the row alone
        left the original, its thumbnail and all cached variants on disk, so
        the store grew forever while the admin saw a successful delete.
        """
        asset = await MediaService.get_asset(db, asset_id)
        # Read what the filesystem cleanup needs before the row is gone — the
        # ORM instance is expired after the delete + flush below.
        asset_hex = asset.id.hex
        file_url = asset.file_url

        await db.delete(asset)
        await db.flush()

        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        failed = MediaService._remove_files(base_dir, asset_hex, file_url)
        if failed:
            await logger.awarning(
                "media_asset_files_not_removed", asset_id=str(asset_id), failures=failed
            )
        await logger.ainfo("media_asset_deleted", asset_id=asset_hex)
