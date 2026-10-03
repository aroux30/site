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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from PIL import Image, ImageOps
from sqlalchemy import func, or_, select

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
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
# The defaults, used when the site option is unset or unreadable. They stay as
# module constants so the ceiling is discoverable and testable without a
# database — but they are no longer the *only* source of the limit.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB for still images and PDFs
MAX_MEDIA_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB for audio/video

#: Site options that hold the configurable ceilings, and their fallbacks. The
#: keys match WordPress's own naming where it has one.
OPTION_MAX_FILE_SIZE = "media_max_file_size_mb"
OPTION_MAX_MEDIA_FILE_SIZE = "media_max_media_file_size_mb"
#: A ceiling nobody sets by accident: a 4 GB upload is an outage, not a policy.
ABSOLUTE_MAX_FILE_SIZE_MB = 2048

MEDIA_CATEGORIES: dict[str, str] = {
    **{m: "image" for m in IMAGE_MIME_TYPES},
    **{m: "audio" for m in AUDIO_MIME_TYPES},
    **{m: "video" for m in VIDEO_MIME_TYPES},
    "application/pdf": "document",
}


def _clamp_mb(value: int, fallback: int) -> int:
    """Keep a configured ceiling inside a sane range.

    Zero or negative would reject every upload; the hard cap stops a typo of
    "204800" from turning into a 200 GB allowance.
    """
    if value <= 0:
        return fallback
    return min(value, ABSOLUTE_MAX_FILE_SIZE_MB)


async def max_size_for_mb(db: "AsyncSession") -> tuple[int, int]:
    """The (image/document, audio/video) ceilings in MB, from site options."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    image_mb, media_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024), MAX_MEDIA_FILE_SIZE_BYTES // (
        1024 * 1024
    )
    return (
        _clamp_mb(
            await SiteOptionsService.get_int(db, OPTION_MAX_FILE_SIZE, image_mb, minimum=1,
                                              maximum=ABSOLUTE_MAX_FILE_SIZE_MB),
            image_mb,
        ),
        _clamp_mb(
            await SiteOptionsService.get_int(db, OPTION_MAX_MEDIA_FILE_SIZE, media_mb, minimum=1,
                                              maximum=ABSOLUTE_MAX_FILE_SIZE_MB),
            media_mb,
        ),
    )


def max_size_for(mime_type: str) -> int:
    """The default size ceiling for a MIME type, without consulting settings.

    Kept synchronous and pure on purpose: the constants are the fallback, and
    every caller that can reach a database should use
    :func:`resolve_size_limit` so an operator's setting is actually honoured.
    """
    return (
        MAX_MEDIA_FILE_SIZE_BYTES
        if MEDIA_CATEGORIES.get(mime_type) in ("audio", "video")
        else MAX_FILE_SIZE_BYTES
    )


async def resolve_size_limit(
    db: "AsyncSession", mime_type: str, caller_max_bytes: int | None = None
) -> int:
    """The ceiling for an upload: the configured one, then any caller cap.

    A caller-supplied ceiling can only tighten the result, never widen it —
    otherwise a narrow route (a thumbnail generator, say) could raise its own
    limit by passing one.
    """
    image_mb, media_mb = await max_size_for_mb(db)
    is_media = MEDIA_CATEGORIES.get(mime_type) in ("audio", "video")
    limit = (media_mb if is_media else image_mb) * 1024 * 1024
    if caller_max_bytes is not None:
        limit = min(limit, caller_max_bytes)
    return limit


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


#: WordPress's default. 2560 covers a 4K phone photo downsampled to something a
#: retina display actually shows, and is roughly a quarter of the pixels of the
#: 4000px originals this replaces.
DEFAULT_BIG_IMAGE_THRESHOLD = 2560


def _fit_within(size: tuple[int, int], limit: int) -> tuple[int, int]:
    """Largest box with the same aspect ratio that fits inside ``limit``.

    The aspect ratio is preserved and neither side is allowed to grow, so a
    portrait and a landscape both come out right. Both dimensions shrink
    together rather than one being capped independently, which is the mistake
    that turns a 4000x3000 into a 2560x3000 and distorts it.
    """
    width, height = size
    longest = max(width, height)
    if longest <= limit:
        return width, height
    scale = limit / longest
    return max(1, round(width * scale)), max(1, round(height * scale))


async def _big_image_threshold(db: AsyncSession) -> int:
    """The operator's big-image limit, in pixels; 0 disables downscaling.

    Read per upload rather than cached, because it is a setting an operator
    changes the moment the site starts serving on a phone, and a stale
    threshold keeps shipping 4000px files for the life of the process.
    """
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    return await SiteOptionsService.get_int(
        db, "big_image_size_threshold", DEFAULT_BIG_IMAGE_THRESHOLD,
        minimum=0, maximum=20000,
    )


async def _process_image_content(
    db: AsyncSession,
    content: bytes,
    content_type: str,
    file_size: int,
) -> tuple[bytes, int, int | None, int | None]:
    """Verify an image and normalise its bytes; return the new (content, size, w, h).

    The upload path and the replace path must agree on what "stored image"
    means — EXIF orientation applied, big-image threshold honoured, dimensions
    measured *after* both — or a replaced file ends up sideways or 4000px wide
    while a fresh upload of the same bytes would not. One function, both
    callers, so they cannot drift.

    Raises ``ValidationError`` for a corrupt image of a type that cannot be
    stored blind (jpeg/png/webp). Non-image types pass through untouched.
    """
    width: int | None = None
    height: int | None = None
    if not content_type.startswith("image/"):
        return content, file_size, width, height

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

        # WordPress's big_image_size_threshold. A modern phone camera
        # produces 4000px-wide files that no storefront ever displays at
        # full size, and shipping them whole is the difference between a
        # product page that loads and one that does not on a phone.
        #
        # Applied here rather than left to a "regenerate" button: the
        # big file is the one that was just uploaded, so the moment it
        # could have been avoided is the moment it arrives. Existing
        # assets are not touched — resizing them silently would change
        # bytes a page may already reference.
        #
        # Downscaling only, never upscaling: a 400px image left alone
        # stays 400px, because making it 2560 would cost bytes and add
        # nothing.
        try:
            _threshold = await _big_image_threshold(db)
            if _threshold:
                _probe = Image.open(io.BytesIO(content))
                _w, _h = _probe.size
                if max(_w, _h) > _threshold:
                    buf = io.BytesIO()
                    if content_type == "image/jpeg":
                        _probe.convert("RGB").resize(
                            _fit_within((_w, _h), _threshold),
                            Image.LANCZOS,
                        ).save(buf, format="JPEG", quality=90)
                    else:
                        _probe.resize(
                            _fit_within((_w, _h), _threshold), Image.LANCZOS
                        ).save(buf, format=_probe.format or "PNG")
                    content = buf.getvalue()
                    file_size = len(content)
                    logger.info(
                        "image_downscaled",
                        original=f"{_w}x{_h}",
                        threshold=_threshold,
                        new_size=file_size,
                    )
        except Exception as e:  # noqa: BLE001 - an upload is never failed by this
            logger.warning("image_downscale_failed", error=str(e))

        img = Image.open(io.BytesIO(content))
        width, height = img.size
    except Exception as e:
        logger.warning("image_verification_failed", error=str(e))
        if content_type in ("image/jpeg", "image/png", "image/webp"):
            raise ValidationError(
                detail="Corrupt or invalid image file",
                error_code="INVALID_IMAGE_FILE",
            ) from e

    return content, file_size, width, height


async def _write_derivatives(
    db: AsyncSession,
    *,
    base_dir: Path,
    local_file_path: Path,
    content: bytes,
    asset_hex: str,
    mime_type: str,
) -> int:
    """Write the 200px WebP thumb, the registered sizes and the watermark.

    Returns the (possibly watermark-adjusted) file size of the original. Both
    the upload path and the replace path call this after the original bytes
    are on disk, so a replaced file has exactly the derivatives a fresh upload
    would — the alternative, a second hand-written copy here, is how the two
    paths drift and one of them quietly stops producing sizes.

    Every step is best-effort: a derivative that fails to render must not fail
    the write that succeeded.
    """
    if mime_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(content))
            thumb_img = img.copy()
            thumb_img.thumbnail((200, 200))
            thumb_dir = base_dir / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = thumb_dir / f"thumb_{asset_hex}.webp"
            thumb_img.save(thumb_path, "WEBP", quality=85)
        except Exception as e:
            logger.warning("thumbnail_generation_failed", error=str(e))

        # The four registered sizes (thumbnail/medium/medium_large/large).
        try:
            await ImageProcessor.generate_thumbnails(str(local_file_path), db=db)
        except Exception as e:
            logger.warning("image_size_generation_failed", error=str(e))

    # Optional site-wide watermark (media_watermark_* site options), applied
    # after the original + thumbnail are written so both carry the mark;
    # variants rendered later from the original inherit it. Best-effort by
    # design: any failure logs and the write continues unwatermarked.
    file_size = len(content)
    try:
        if await maybe_watermark_uploaded_file(
            db,
            file_path=local_file_path,
            mime_type=mime_type,
            asset_hex=asset_hex,
            base_dir=base_dir,
        ):
            file_size = local_file_path.stat().st_size
    except Exception as e:  # watermarking must never fail a write
        logger.warning("media_watermark_step_failed", error=str(e))
    return file_size


def _error_message(exc: Exception) -> str:
    """Human-facing message for the batch error report (detail over str)."""
    detail = getattr(exc, "detail", None)
    return str(detail) if detail else str(exc)


#: Read granularity for the streaming upload guard. Small enough that a client
#: streaming far past the ceiling is cut off quickly, large enough that a normal
#: upload is not dominated by per-chunk await overhead.
_UPLOAD_CHUNK_BYTES = 1024 * 1024

#: A folder that exists with nothing in it is stored as a marker row rather
#: than in a folders table, so the tree keeps one source. Both constants are
#: needed together: the mime is what the grid and the delete guard filter on,
#: and the prefix is what makes the row recognisable in a raw listing.
_FOLDER_MARKER_MIME = "inode/directory"
_FOLDER_MARKER_PREFIX = ".folder-"

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
        # larger than 10 MB, and the image cap is deliberately left alone. It
        # also depends on the site option, so an operator raising the video
        # ceiling does not need a redeploy — which is the whole point of this
        # being configurable rather than a module constant.
        size_limit = await resolve_size_limit(db, content_type, max_bytes)
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
        content, file_size, width, height = await _process_image_content(
            db, content, content_type, file_size
        )

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

        # The 200px WebP thumb, the four registered sizes, and the optional
        # site-wide watermark. Shared with the replace path so a replaced file
        # gets exactly the derivatives a fresh upload would.
        file_size = await _write_derivatives(
            db,
            base_dir=base_dir,
            local_file_path=local_file_path,
            content=content,
            asset_hex=file_id.hex,
            mime_type=content_type,
        )

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
            # The chain link. Without it the edit history is untraceable, so
            # there was no undo and no way back to the original: the editor
            # produced files it could not relate to each other.
            source_asset_id=source.id,
            edit_operation=suffix,
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
    async def list_edit_history(
        db: AsyncSession, asset_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        """The asset's own chain: root first, then each edit down to this row.

        This is the list the undo/redo buttons step through and the history
        panel renders, so it has to be the actual ancestry of ``asset_id`` —
        every hop of ``source_asset_id`` from the root to the current row.

        The previous version fetched only the *direct children of the root*,
        which is neither end of the chain for a chain deeper than one edit:
        for ``a -> b -> c`` it returned ``[b]`` and dropped both the original
        and the current file. ``is_current`` then matched nothing, so the
        current-step badge never showed and undo/redo had no index to walk.
        """
        # Walk up to the root, collecting the ancestry in reverse.
        chain: list[MediaAsset] = []
        seen: set[uuid.UUID] = set()
        cursor: uuid.UUID | None = asset_id
        while cursor is not None:
            if cursor in seen:  # a cycle cannot be written, but do not hang
                break
            seen.add(cursor)
            row = await db.get(MediaAsset, cursor)
            if row is None:
                break
            chain.append(row)
            cursor = row.source_asset_id

        # Root first, current last.
        chain.reverse()

        history: list[dict[str, Any]] = []
        for index, step in enumerate(chain):
            history.append(
                {
                    "id": str(step.id),
                    "source_id": str(step.source_asset_id) if step.source_asset_id else None,
                    "operation": step.edit_operation,
                    "file_name": step.file_name,
                    "file_url": step.file_url,
                    "width": step.width,
                    "height": step.height,
                    "is_root": index == 0,
                    "is_current": step.id == asset_id,
                    "created_at": step.created_at.isoformat() if step.created_at else None,
                }
            )
        return history

    @staticmethod
    async def restore_original(
        db: AsyncSession, asset_id: uuid.UUID
    ) -> MediaAsset:
        """Return the root of an edit chain, creating a copy if it is gone.

        "Restore the original" in WordPress means the bytes that were uploaded,
        not an undo of the last step. The root is reached by walking the
        ``source_asset_id`` links, so an asset three crops deep resolves in three
        hops.

        The root row is returned as-is when it is still there. If it has been
        deleted in the meantime the chain dangles — the parent link is
        ``SET NULL``, so a deleted root leaves its children parentless — and
        there is nothing to restore, which raises rather than silently handing
        back the asset the caller was already holding.
        """
        current = await MediaService.get_asset(db, asset_id)
        if current.source_asset_id is None:
            return current

        root_id = current.source_asset_id
        seen: set[uuid.UUID] = {current.id}
        while True:
            row = await db.get(MediaAsset, root_id)
            if row is None:
                raise NotFoundError(
                    "MediaAsset",
                    f"the original of asset {asset_id} no longer exists",
                )
            if row.source_asset_id is None:
                return row
            if root_id in seen:
                raise ValidationError(
                    detail="Media edit history contains a cycle",
                    error_code="MEDIA_HISTORY_CYCLE",
                )
            seen.add(root_id)
            root_id = row.source_asset_id

    @staticmethod
    async def duplicate_asset(
        db: AsyncSession,
        asset_id: uuid.UUID,
    ) -> MediaAsset:
        """Copy an asset's bytes and metadata into a new, standalone asset.

        WordPress's "save as a copy" from the image editor: an operator has
        edited a photo for one use and wants the edited version as its own
        file without touching the chain the edits live on.

        The copy carries **no** ``source_asset_id``: it is not an edit of the
        original, it is a new asset that happens to start from the same bytes.
        Linking it would put a file in the history that no operation produced,
        and "restore the original" on the copy would walk back into somebody
        else's chain.
        """
        source = await MediaService.get_asset(db, asset_id)

        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        source_path = MediaService._resolve_source_path(base_dir, source)
        if source_path is None or not source_path.is_file():
            raise NotFoundError(
                "MediaAsset",
                f"فایل {source.file_name} روی دیسک نیست و قابل کپی نیست",
            )

        content = source_path.read_bytes()
        ext = source_path.suffix.lower() or ".jpg"
        file_id = uuid.uuid4()
        disk_name = file_id.hex + ext
        local_upload_dir = Path(base_dir) / MEDIA_SUBDIR
        local_upload_dir.mkdir(parents=True, exist_ok=True)
        local_file_path = local_upload_dir / disk_name
        local_file_path.write_bytes(content)

        stem = Path(source.file_name).stem
        copy = MediaAsset(
            id=file_id,
            uploader_id=source.uploader_id,
            file_name=f"{stem}_copy{ext}",
            file_path=f"media/{disk_name}",
            file_url=f"/uploads/media/{disk_name}",
            file_size=len(content),
            mime_type=source.mime_type,
            width=source.width,
            height=source.height,
            alt_text=source.alt_text,
            title=source.title,
            caption=source.caption,
            description=source.description,
            folder=source.folder,
            # Deliberately no source_asset_id / edit_operation: see docstring.
        )
        db.add(copy)
        await db.flush()

        # The copy has its own derivatives (sizes, thumb, watermark) — a
        # standalone asset that renders at one size and 404s at the rest is
        # not a copy of the file, it is a copy of one of its URLs.
        await _write_derivatives(
            db,
            base_dir=base_dir,
            local_file_path=local_file_path,
            content=content,
            asset_hex=file_id.hex,
            mime_type=source.mime_type,
        )

        await logger.ainfo(
            "media_asset_duplicated",
            asset_id=str(copy.id),
            source_id=str(asset_id),
        )
        return copy

    @staticmethod
    def _resolve_source_path(base_dir: Path, asset: MediaAsset) -> Path | None:
        """The on-disk path of an asset's own original, if it exists.

        Uses the same candidate list the restore check and the delete sweep
        use, so the three cannot disagree about where a file lives.
        """
        for candidate in candidate_sources(base_dir, asset.file_url, asset.file_path):
            if candidate.is_file():
                return candidate
        return None

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
        include_trashed: bool = False,
        post_id: uuid.UUID | None = None,
        unattached: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[MediaAsset], int]:
        """Fetch paginated list of media assets, optionally scoped to a folder.

        ``search`` matches the operator-visible columns — the stored file name
        and the alt text — because those are the two strings an operator
        actually knows an asset by. The on-disk name is a server-generated uuid,
        so searching it would never match anything a human typed.

        Trashed assets are hidden unless ``include_trashed`` is set, so the
        default library view never offers a file that is on its way out — and
        the trash view shows only those.

        ``post_id`` and ``unattached`` are the two halves of WordPress's
        "attached to" column, and they exist because the column has been dead:
        nothing ever wrote ``post_id``, so the filter had nothing to match and
        an unattached-media view could only ever be "everything". Both are
        mutually exclusive by construction — asking for one post's media and
        also for media attached to nothing is a contradiction, and silently
        resolving it would return a list the operator did not ask for.
        """
        if post_id is not None and unattached:
            raise ValueError("post_id and unattached cannot both be set")
        count_stmt = select(func.count()).select_from(MediaAsset)
        stmt = select(MediaAsset)

        if not include_trashed:
            # `is_(None)` rather than `== None`: SQLAlchemy needs both shapes
            # spelled out, and the wrong one is a silently-empty library.
            count_stmt = count_stmt.where(MediaAsset.deleted_at.is_(None))
            stmt = stmt.where(MediaAsset.deleted_at.is_(None))

        # Folder markers are bookkeeping, not files. Listing one would put a
        # zero-byte row in the operator's grid with no way to tell what it is,
        # and it would count against the library total.
        count_stmt = count_stmt.where(MediaAsset.mime_type != _FOLDER_MARKER_MIME)
        stmt = stmt.where(MediaAsset.mime_type != _FOLDER_MARKER_MIME)

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

        # WordPress's "uploaded between" date range. What an operator reaches
        # for when the disk filled up last week and they need to know what
        # arrived since, or when they are hunting a batch of uploads from one
        # supplier and want to see them together.
        #
        # Inclusive on both ends. A "from" that excluded its own boundary day
        # would silently drop the files uploaded at midnight, which is exactly
        # when a nightly import runs and the files being hunted are.
        if created_from is not None:
            count_stmt = count_stmt.where(MediaAsset.created_at >= created_from)
            stmt = stmt.where(MediaAsset.created_at >= created_from)
        if created_to is not None:
            count_stmt = count_stmt.where(MediaAsset.created_at <= created_to)
            stmt = stmt.where(MediaAsset.created_at <= created_to)

        if post_id is not None:
            # This is the same filter the post page uses to show which images a
            # post actually uses, so an operator deleting an image sees the
            # same answer the storefront would.
            count_stmt = count_stmt.where(MediaAsset.post_id == post_id)
            stmt = stmt.where(MediaAsset.post_id == post_id)
        elif unattached:
            # `is_(None)` not `== None`, for the same reason as `deleted_at`
            # above: the other spelling silently returns nothing, which for
            # this filter would look like every file is attached.
            count_stmt = count_stmt.where(MediaAsset.post_id.is_(None))
            stmt = stmt.where(MediaAsset.post_id.is_(None))

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
    @staticmethod
    async def create_folder(db: AsyncSession, path: str) -> dict[str, Any]:
        """Create an empty folder in the library tree.

        Folders here are not rows — they are the distinct ``folder`` values on
        media assets, which is why creating one meant "upload something into it"
        and nothing else. That works until an operator wants to lay out
        ``products/shoes`` before the first product photo exists, which is the
        normal way anybody builds a library.

        So an empty folder is stored as a marker asset: a zero-byte file row in
        the folder itself. It keeps the tree derived from one place, so
        `list_folders` needs no second source and a folder cannot exist in the
        UI and be missing from the API.

        The marker is hidden from the grid and refused by the delete guard, so
        it is never something an operator sees, uploads over, or counts.
        """
        clean = _sanitize_folder(path)
        if not clean:
            raise ValidationError("مسیر پوشه معتبر نیست")

        existing = (await db.execute(
            select(func.count()).select_from(MediaAsset).where(
                MediaAsset.folder == clean)
        )).scalar_one()
        if existing:
            # Not an error: creating a folder that is already there is what an
            # operator double-clicking does, and refusing it looks broken.
            return {"path": clean, "created": False}
        marker = MediaAsset(
            uploader_id=None,
            file_name=f"{_FOLDER_MARKER_PREFIX}{clean.replace('/', '-')}.folder",
            # `folder`, not `file_path`: that is the column the tree is derived
            # from. Putting the path in `file_path` left a row that nothing
            # read — the folder existed in the response but not in the list.
            folder=clean,
            file_path=f"{clean}/{_FOLDER_MARKER_PREFIX}{clean.replace('/', '-')}.folder",
            file_url=f"/media/folders/{clean}",
            file_size=0,
            mime_type=_FOLDER_MARKER_MIME,
        )
        db.add(marker)
        await db.commit()
        await logger.ainfo("media_folder_created", folder=clean)
        return {"path": clean, "created": True}

    @staticmethod
    async def delete_folder(
        db: AsyncSession, path: str, *, delete_assets: bool = False
    ) -> dict[str, Any]:
        """Delete a folder, and optionally everything inside it.

        Defaults to refusing while it holds anything. Deleting forty product
        photos because somebody removed a folder is not a recoverable mistake,
        and the operator who meant that can say so with the flag.
        """
        clean = _sanitize_folder(path)
        if not clean:
            raise ValidationError("مسیر پوشه معتبر نیست")

        prefix = clean + "/"
        held = (await db.execute(
            select(func.count()).select_from(MediaAsset).where(
                or_(
                    MediaAsset.folder == clean,
                    MediaAsset.folder.startswith(prefix),
                ))
        )).scalar_one()

        real = (await db.execute(
            select(func.count()).select_from(MediaAsset).where(
                or_(
                    MediaAsset.folder == clean,
                    MediaAsset.folder.startswith(prefix),
                ),
                MediaAsset.mime_type != _FOLDER_MARKER_MIME,
            )
        )).scalar_one()

        if real and not delete_assets:
            raise ConflictError(
                f"این پوشه {real} فایل دارد. برای حذف، تأیید حذف فایل‌ها را بزنید."
            )

        ids = (await db.execute(
            select(MediaAsset.id).where(
                or_(
                    MediaAsset.folder == clean,
                    MediaAsset.folder.startswith(prefix),
                ))
        )).scalars().all()
        for asset_id in ids:
            await db.delete(await db.get(MediaAsset, asset_id))
        await db.commit()
        await logger.ainfo("media_folder_deleted", folder=clean, removed=len(ids))
        return {"path": clean, "removed": len(ids), "refused_assets": real}

    @staticmethod
    async def list_folders(db: AsyncSession) -> list[dict[str, Any]]:
        """Distinct folder paths with asset counts, for the admin folder tree.

        An empty folder appears with a count of zero — it is a real folder the
        operator made on purpose, and hiding it until the first upload is what
        made "create folder" feel like it did nothing.

        The marker rows are excluded from the *count*, because a folder must
        never report a file it does not have. They are not excluded from the
        *list*, or an empty folder would not appear at all — which is the bug
        the whole feature is meant to fix. So the two reads differ on purpose:
        a folder that exists only because it was created shows up with zero.
        """
        stmt = (
            select(MediaAsset.folder, func.count())
            .where(
                MediaAsset.folder.is_not(None),
                MediaAsset.mime_type != _FOLDER_MARKER_MIME,
            )
            .group_by(MediaAsset.folder)
            .order_by(MediaAsset.folder)
        )
        rows = (await db.execute(stmt)).all()
        counts = {folder: count for folder, count in rows}

        # Folders that exist only as their own marker: no asset, so no row in
        # the grouped query above, so they have to be added back by hand.
        markers = (await db.execute(
            select(MediaAsset.folder).where(
                MediaAsset.mime_type == _FOLDER_MARKER_MIME,
                MediaAsset.folder.is_not(None),
            )
        )).scalars().all()
        for folder in markers:
            counts.setdefault(folder, 0)

        return [
            {"path": folder, "asset_count": count}
            for folder, count in sorted(counts.items())
        ]

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
        for path in MediaService._stored_file_candidates(asset_hex, file_url):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover - depends on filesystem state
                failed.append("%s: %s" % (path.name, exc))
        return failed

    @staticmethod
    def _stored_file_candidates(asset_hex: str, file_url: str | None) -> list[Path]:
        """Every place an asset's own bytes may sit on disk.

        Delegates the lookup to ``storage_paths.candidate_sources``, which
        already owns the answer — the upload, the serving route and the variant
        renderer all read it. This list used to be spelled out separately, and
        the two copies disagreed: the delete sweep looked in
        ``media/<name>`` and ``media/<shard>/<name>`` while the restore check
        looked in ``UPLOAD_DIR/<file_path>``, which for a real row resolves to
        ``media/media/<shard>/<name>``. Every restore therefore reported "the
        bytes are gone" for an asset whose file was sitting right there.

        What is added here is only the derived sizes and the caches, which are
        keyed by the asset id rather than by the file name and so cannot come
        from ``candidate_sources``.

        Derived sizes are found by globbing ``<stem>-*<ext>`` rather than by
        constructing one name per registered size. The stem is a full 32-hex
        uuid — the upload path never writes an original that shares another
        asset's stem — so the pattern can only match this asset's own
        derivatives, and it catches two cases a registered-name list misses:
        sizes registered after this asset was uploaded (custom image sizes)
        and sizes the operator has since removed from the registry, whose
        files are still on disk and must still be reclaimed by a delete.
        """
        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        candidates: list[Path] = list(
            candidate_sources(base_dir, file_url or "", None)
        )

        disk_name = Path(file_url or "").name
        if disk_name:
            stem = Path(disk_name).stem
            ext = Path(disk_name).suffix
            media_dir = base_dir / MEDIA_SUBDIR
            # Globbing a server-generated hex id: no user-supplied text
            # reaches the pattern, so no path traversal is possible here.
            candidates.extend(media_dir.glob(f"{stem}-*{ext}"))
        candidates.append(base_dir / "thumbnails" / f"thumb_{asset_hex}.webp")
        variant_dir = base_dir / "variants"
        if variant_dir.is_dir():
            candidates.extend(variant_dir.glob(f"{asset_hex}_*"))
        return candidates

    @staticmethod
    def _stored_file_exists(asset: MediaAsset) -> bool:
        """Whether the asset's own bytes are still on disk."""
        return any(
            p.exists()
            for p in MediaService._stored_file_candidates(asset.id.hex, asset.file_url)
        )

    @staticmethod
    async def replace_file(
        db: AsyncSession,
        asset_id: uuid.UUID,
        file: UploadFile,
    ) -> MediaAsset:
        """Swap the bytes behind an asset, keeping its URL and its row.

        WordPress's "Enable Media Replace": the moment an operator needs it is
        when a product photo changes but the URL is already in a dozen pages,
        a feed and an ad. Deleting and re-uploading breaks every one of those
        references; this keeps them all working and changes the picture.

        The new file must be the same type as the old one. The URL ends in the
        old extension and the serving route derives the Content-Type from it,
        so a png URL answering with jpeg bytes is a lie the browser has to
        sniff around. Replacing an image with a different format is a delete
        and a re-upload, not a replace.

        Derivatives are rebuilt, not kept: the thumbnail, the four registered
        sizes and the cached variants were rendered from the old bytes, and
        leaving them would show the old picture everywhere the new one is not
        full-size.
        """
        asset = await MediaService.get_asset(db, asset_id)
        if asset.deleted_at is not None:
            raise ValidationError("این فایل در سطل زباله است؛ اول بازگردانی کنید")

        declared = file.content_type or "application/octet-stream"
        content = await _read_capped(file, None)
        if not content:
            raise ValidationError(
                detail="Empty file upload is not permitted",
                error_code="EMPTY_FILE",
            )
        detected = _sniff_mime(content, declared)
        if detected != asset.mime_type:
            raise ValidationError(
                detail=(
                    "The replacement must be the same file type as the original "
                    f"({asset.mime_type}); got {detected}"
                ),
                error_code="REPLACEMENT_TYPE_MISMATCH",
            )
        size_limit = await resolve_size_limit(db, detected, None)
        if len(content) > size_limit:
            raise ValidationError(
                detail=f"File size exceeds maximum allowed limit of {size_limit // (1024 * 1024)}MB",
                error_code="FILE_TOO_LARGE",
            )

        content, file_size, width, height = await _process_image_content(
            db, content, detected, len(content)
        )

        # Resolve where the current bytes live and write the new ones in their
        # place. os.replace is atomic on one filesystem, so a crash mid-write
        # leaves the old file whole rather than a half-written one under a
        # live URL.
        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        local_upload_dir = Path(base_dir) / MEDIA_SUBDIR
        local_upload_dir.mkdir(parents=True, exist_ok=True)
        target = local_upload_dir / Path(asset.file_url).name

        # The derived files are keyed off the disk name; remove them before
        # the new original lands so nothing rendered from the old bytes can
        # be served after this returns.
        MediaService._remove_files(base_dir, asset.id.hex, asset.file_url)

        tmp = target.with_name(target.name + f".tmp{os.getpid()}")
        try:
            tmp.write_bytes(content)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

        file_size = await _write_derivatives(
            db,
            base_dir=base_dir,
            local_file_path=target,
            content=content,
            asset_hex=asset.id.hex,
            mime_type=asset.mime_type,
        )

        asset.file_size = file_size
        asset.width = width
        asset.height = height
        await db.flush()

        await logger.ainfo(
            "media_asset_replaced",
            asset_id=str(asset.id),
            size=file_size,
            mime=asset.mime_type,
        )
        return asset

    @staticmethod
    async def trash_asset(db: AsyncSession, asset_id: uuid.UUID) -> MediaAsset:
        """Move an asset to the trash, keeping its row and its bytes.

        The bytes stay put on purpose: a restore has to bring the file back
        exactly as it was, and re-deriving a thumbnail from a source that may
        since have been re-uploaded is not the same thing. Purging is a separate,
        explicit step (``purge_asset``) with its own retention job behind it.
        """
        asset = await MediaService.get_asset(db, asset_id)
        if asset.deleted_at is not None:
            return asset
        now = datetime.now(timezone.utc)
        asset.deleted_at = now
        asset.trashed_at = now
        await db.flush()
        return asset

    @staticmethod
    async def restore_asset(db: AsyncSession, asset_id: uuid.UUID) -> MediaAsset:
        """Bring a trashed asset back to the library.

        Refuses if the bytes are gone: a row without its file would show up in
        the library as a broken image, which is worse than a missing asset the
        admin was told about.
        """
        asset = await MediaService.get_asset(db, asset_id)
        if asset.deleted_at is None:
            return asset
        if not MediaService._stored_file_exists(asset):
            raise NotFoundError(
                "MediaAsset",
                f"فایل {asset.file_name} روی دیسک نیست و قابل بازگردانی نیست",
            )
        asset.deleted_at = None
        asset.trashed_at = None
        await db.flush()
        return asset

    @staticmethod
    async def list_trashed(
        db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[list[MediaAsset], int]:
        """The trash view: only soft-deleted assets, oldest trash first."""
        count_stmt = select(func.count()).select_from(MediaAsset).where(
            MediaAsset.deleted_at.is_not(None)
        )
        stmt = (
            select(MediaAsset)
            .where(MediaAsset.deleted_at.is_not(None))
            .order_by(MediaAsset.trashed_at.asc().nulls_last(), MediaAsset.created_at.asc())
        )
        total = int((await db.execute(count_stmt)).scalar() or 0)
        rows = (
            (
                await db.execute(
                    stmt.offset((page - 1) * page_size).limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    async def purge_asset(db: AsyncSession, asset_id: uuid.UUID) -> None:
        """Permanently remove a trashed asset: row and bytes.

        Refuses an asset that is still live, so this cannot be reached by
        accident from a UI that only intended "remove".
        """
        asset = await MediaService.get_asset(db, asset_id)
        if asset.deleted_at is None:
            raise ValidationError("این فایل در سطل زباله نیست")
        await MediaService._delete_row_and_files(db, asset)

    @staticmethod
    async def empty_trash(
        db: AsyncSession, *, older_than_days: int | None = None
    ) -> int:
        """Purge trashed assets, optionally only those older than N days.

        ``older_than_days`` is what keeps this safe to schedule: a daily job
        that purges everything would make "empty trash" a lie the moment an
        admin restored something they had not meant to remove yet.
        """
        stmt = select(MediaAsset).where(MediaAsset.deleted_at.is_not(None))
        if older_than_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            stmt = stmt.where(
                or_(
                    MediaAsset.trashed_at.is_(None),
                    MediaAsset.trashed_at <= cutoff,
                )
            )
        assets = (await db.execute(stmt)).scalars().all()
        for asset in assets:
            await MediaService._delete_row_and_files(db, asset)
        return len(assets)

    @staticmethod
    async def bulk_trash(
        db: AsyncSession,
        asset_ids: list[uuid.UUID],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Trash many assets, reporting each one's outcome.

        Per-item results rather than one boolean, because "20 selected, 17
        moved, 3 are still used" and "20 moved" are different facts and the
        operator has to be able to tell them apart. A single in-use file must
        not stop the other nineteen.

        Each item runs in its own savepoint: a refusal from the usage check
        aborts the transaction, and without the savepoint that one file would
        take the whole batch down with it — the failure mode this project's own
        notes record for a poisoned transaction.
        """
        ok = 0
        results: list[dict[str, Any]] = []
        for asset_id in asset_ids:
            try:
                async with db.begin_nested():
                    await MediaService.delete_asset(db, asset_id, force=force)
                ok += 1
                results.append({"id": str(asset_id), "ok": True})
            except ValidationError as exc:
                results.append({"id": str(asset_id), "ok": False, "error": str(exc)})
            except NotFoundError as exc:
                results.append({"id": str(asset_id), "ok": False, "error": str(exc)})
            except ConflictError as exc:
                # The refusal from the usage check. It arrives here rather than
                # being caught as a ValidationError because the check raises its
                # own type, and it matters that it is named: the previous
                # catch-all rolled the WHOLE transaction back, which discards
                # work this request had already done, not just the savepoint
                # for this one file.
                results.append({"id": str(asset_id), "ok": False, "error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the rest
                # Roll back only this item. `db.rollback()` would end the whole
                # transaction, and anything the caller did before this batch
                # would be lost with it.
                async with db.begin_nested():
                    pass
                results.append(
                    {"id": str(asset_id), "ok": False, "error": f"{type(exc).__name__}: {exc}"}
                )
        return {
            "ok": ok,
            "failed": len(asset_ids) - ok,
            "total": len(asset_ids),
            "results": results,
        }

    @staticmethod
    async def _delete_row_and_files(db: AsyncSession, asset: MediaAsset) -> None:
        """Remove the row and every file it owns, in that order.

        Read what the filesystem cleanup needs before the row is gone — the ORM
        instance is expired after the delete + flush.

        The hook point is here rather than on the three public entry points
        (``purge_asset``, ``empty_trash``, the force branch of ``delete_asset``)
        because this is the one path they all funnel through: a hook bound to a
        single entry point would miss a scheduled purge, and a scheduled purge
        is the one that runs unattended.
        """
        from app.shared.plugins.registry import (
            HOOK_MEDIA_AFTER_DELETE,
            HOOK_MEDIA_BEFORE_DELETE,
            registry,
        )

        asset_hex = asset.id.hex
        file_url = asset.file_url
        asset_id = asset.id

        # ``before_delete`` can veto: return False from the filter to abort.
        # A plugin holding back a file a retention rule would otherwise purge
        # is a real need — the alternative is that the only way to stop it is
        # to switch the scheduled job off.
        veto = await registry.apply_filters(
            HOOK_MEDIA_BEFORE_DELETE,
            True,
            asset_id=asset_hex,
            file_url=file_url,
            mime_type=asset.mime_type,
        )
        if veto is False:
            await logger.ainfo("media_delete_vetoed_by_plugin", asset_id=asset_hex)
            return

        await db.delete(asset)
        await db.flush()

        base_dir = Path(getattr(settings, "UPLOAD_DIR", "media"))
        failed = MediaService._remove_files(base_dir, asset_hex, file_url)
        if failed:
            await logger.awarning(
                "media_asset_files_not_removed", asset_id=str(asset_id), failures=failed
            )

        # After the bytes are gone, not after the row: a plugin that wants to
        # archive a copy needs the file, and the file is what this call removed.
        await registry.do_action(
            HOOK_MEDIA_AFTER_DELETE,
            asset_id=asset_hex,
            file_url=file_url,
            files_removed=not failed,
        )
        await logger.ainfo("media_asset_deleted", asset_id=asset_hex)

    @staticmethod
    async def attach_to_post(
        db: AsyncSession,
        asset_id: uuid.UUID,
        post_id: uuid.UUID | None,
    ) -> MediaAsset:
        """Point an asset at a post, or detach it with ``None``.

        WordPress's "Attached to" column. The column has existed on the model
        since the beginning with no writer, which made it worse than absent: an
        operator looking for an image's usage had a field to read and a blank.

        Detaching takes an explicit ``None`` rather than a second method, because
        "attach to nothing" and "I did not say" are the same value in the API
        and only one of them is a decision. The route documents the difference.

        The post is checked to exist. A media row pointing at a deleted post is
        what this whole column exists to prevent, and a 404 here is the moment
        it can be prevented — accepting the id would store exactly that.
        """
        asset = await db.get(MediaAsset, asset_id)
        if asset is None:
            raise NotFoundError("MediaAsset", f"Asset {asset_id} not found")

        if post_id is not None:
            from app.modules.blog.domain.models import BlogPost

            post = await db.get(BlogPost, post_id)
            if post is None:
                raise NotFoundError("BlogPost", f"Post {post_id} not found")

        asset.post_id = post_id
        await db.commit()
        await db.refresh(asset)
        await logger.ainfo(
            "media_asset_attached",
            asset_id=str(asset_id),
            post_id=str(post_id) if post_id else None,
        )
        return asset

    @staticmethod
    async def delete_asset(
        db: AsyncSession,
        asset_id: uuid.UUID,
        *,
        force: bool = False,
    ) -> None:
        """Delete a media asset and every file it owns on disk.

        The record and the bytes are removed together: dropping the row alone
        left the original, its thumbnail and all cached variants on disk, so
        the store grew forever while the admin saw a successful delete.

        This is the *library* delete an operator clicks, so it now trashes: the
        row and the bytes both survive and ``restore_asset`` can bring them
        back. Permanent deletion moved to ``purge_asset``, which only accepts an
        asset that is already in the trash.

        Refuses while the asset is still referenced unless ``force``. The force
        flag means "yes, break those references" — it still goes to the trash,
        so the mistake remains recoverable.
        """
        from app.core.exceptions.handlers import ConflictError

        asset = await MediaService.get_asset(db, asset_id)
        if asset.deleted_at is not None:
            return  # already in the trash; deleting again must not resurrect it
        if not force:
            from app.modules.media.application.usage_service import count_media_usage

            usage = await count_media_usage(db, Path(asset.file_url).name)
            if usage.total:
                raise ConflictError(
                    "این فایل هنوز استفاده می‌شود (%s)." % usage.summary()
                )
        await MediaService.trash_asset(db, asset_id)
