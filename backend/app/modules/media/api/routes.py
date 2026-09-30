"""Media asset API endpoints."""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.media.application.media_service import MediaService
from app.modules.media.application.public_url import build_asset_url, resolve_cdn_base_url
from app.modules.media.domain.models import MediaAsset
from app.modules.media.schemas.media import (
    MediaAssetListResponse,
    MediaAssetResponse,
    MediaAssetUpdateRequest,
    MediaBatchUploadResponse,
    MediaUploadResponse,
)

router = APIRouter()


async def _asset_response(db: AsyncSession, asset: MediaAsset) -> MediaAssetResponse:
    """Serialize an asset, prefixing the CDN base onto its public URL.

    The DB stores the origin-relative ``/uploads/media/<name>``; the
    ``media_cdn_base_url`` site option is applied at serialisation time so
    switching the delivery domain never rewrites stored rows.
    """
    response = MediaAssetResponse.model_validate(asset)
    cdn_base = await resolve_cdn_base_url(db)
    response.file_url = build_asset_url(response.file_url, cdn_base)
    return response


@router.post(
    "/sideload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Fetch a remote image by URL into the library (WordPress media_sideload_image)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
@limiter.limit("5/minute")
async def sideload_media(
    request: Request,
    url: str = Form(..., description="Public http(s) image URL"),
    alt_text: str | None = Form(None, description="Accessible description"),
    folder: str | None = Form(None, description="Target folder path"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    """Download an image from a URL and store it as a library asset.

    The admin media modal has offered this since WordPress 2.x, and pasting a
    supplier's image URL is a normal thing to do.

    Every byte fetched goes through the SAME ``upload_file`` path as a browser
    upload, so the magic-byte check, the MIME allowlist and the size ceiling
    apply identically — a remote file that is really a script is rejected the
    same way. On top of that the URL is vetted by
    ``app.core.security.url_guard``, which resolves DNS and refuses any name
    that points at an internal address, and re-checks every redirect hop.

    Rate limited harder than a direct upload: each call makes the server fetch
    from the open internet.
    """
    from app.modules.media.application.sideload_service import sideload_image

    asset = await sideload_image(
        db,
        url,
        uploader_id=user_id,
        alt_text=alt_text,
        folder=folder,
    )
    await db.commit()
    return MediaUploadResponse(
        asset=await _asset_response(db, asset),
        message="تصویر از نشانی دریافت و به کتابخانه افزوده شد",
    )


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload media file",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
@limiter.limit("20/minute")
async def upload_media(
    request: Request,
    file: UploadFile = File(..., description="File to upload (max 10MB, images/pdf)"),
    alt_text: str | None = Form(None, description="Accessible description"),
    folder: str | None = Form(None, description="Target folder path, e.g. 'banners/2026'"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    """Upload an image or document, validate MIME/content, and return file URL."""
    asset = await MediaService.upload_file(
        db,
        file=file,
        uploader_id=user_id,
        alt_text=alt_text,
        folder=folder,
    )
    await db.commit()
    return MediaUploadResponse(
        asset=await _asset_response(db, asset),
        message="File uploaded successfully",
    )


#: Return-request proofs are a customer-facing upload, and the customer role
#: holds no ``media:write`` — granting it would let any shopper write into the
#: store's library. This narrower path serves exactly that need instead: an
#: authenticated user, images only, into a folder nobody else browses.
_RETURN_PROOF_FOLDER = "returns/proof"
_RETURN_PROOF_MAX_BYTES = 10 * 1024 * 1024
_RETURN_PROOF_MIMES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/avif", "image/gif"}
)


@router.post(
    "/upload/return-proof",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a return-request proof photo (any authenticated user)",
)
@limiter.limit("10/minute")
async def upload_return_proof(
    request: Request,
    file: UploadFile = File(..., description="Proof photo (images only, max 10MB)"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    """Accept a return proof without granting the library to shoppers.

    The content validation and on-disk write are the same ones
    ``/media/upload`` runs — this route only narrows *who* may call and
    *what* they may send. Magic bytes still decide the real type, so a renamed
    ``.jpg`` that is really a script is rejected the same way.
    """
    declared = (file.content_type or "").split(";")[0].strip().lower()
    if declared not in _RETURN_PROOF_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="مدرک بازگشت کالا باید تصویر باشد (JPG، PNG، WebP، AVIF یا GIF)",
        )

    asset = await MediaService.upload_file(
        db,
        file=file,
        uploader_id=user_id,
        alt_text="مدرک بازگشت کالا",
        folder=_RETURN_PROOF_FOLDER,
        max_bytes=_RETURN_PROOF_MAX_BYTES,
    )
    await db.commit()
    return MediaUploadResponse(
        asset=await _asset_response(db, asset),
        message="مدرک بازگشت کالا بارگذاری شد",
    )


@router.post(
    "/upload/batch",
    response_model=MediaBatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple media files in one batch (max 20 files, 10MB each)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
@limiter.limit("10/minute")
async def upload_media_batch(
    request: Request,
    files: list[UploadFile] = File(
        ..., description="Files to upload (max 20 per batch, max 10MB each)"
    ),
    folder: str | None = Form(None, description="Target folder path applied to every file"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MediaBatchUploadResponse:
    """Upload several files at once; each file succeeds or fails independently.

    Every file goes through the same validation and processing as the single
    upload (MIME whitelist, 10MB cap, optional site watermark). Failed files
    are reported per file and never roll back the accepted ones.
    """
    return await MediaService.upload_batch(
        db, files=files, uploader_id=user_id, folder=folder
    )


@router.get(
    "",
    response_model=MediaAssetListResponse,
    summary="List media assets",
    # The asset list discloses uploader IDs and filenames for every asset in
    # the system — staff-only, matching the delete endpoint's model.
    dependencies=[Depends(RequirePermissions("media:read"))],
)
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mime_type: str | None = Query(None, description="Filter by MIME type prefix e.g. 'image/'"),
    folder: str | None = Query(None, description="Folder path; '' = root, omitted = all"),
    search: str | None = Query(
        None, description="Match the file name or alt text, case-insensitively"
    ),
    db: AsyncSession = Depends(get_db),
) -> MediaAssetListResponse:
    """List uploaded media assets with pagination."""
    items, total = await MediaService.list_assets(
        db, page=page, page_size=page_size, mime_prefix=mime_type, folder=folder, search=search
    )
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    return MediaAssetListResponse(
        items=[await _asset_response(db, a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/folders",
    response_model=list[dict[str, Any]],
    summary="List media folders with asset counts (admin)",
    dependencies=[Depends(RequirePermissions("media:read"))],
)
async def list_media_folders(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await MediaService.list_folders(db)


class _MoveRequest(BaseModel):
    ids: list[uuid.UUID]
    folder: str | None = None


class _FocalPointRequest(BaseModel):
    focal_x: float
    focal_y: float


@router.patch(
    "/{asset_id}/focal-point",
    response_model=MediaAssetResponse,
    summary="Set smart-crop focal point (admin)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def set_focal_point(
    asset_id: uuid.UUID,
    body: _FocalPointRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.set_focal_point(db, asset_id, body.focal_x, body.focal_y)
    await db.commit()
    return await _asset_response(db, asset)


@router.post(
    "/move",
    response_model=dict[str, int],
    summary="Move media assets to a folder (admin)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def move_media(
    body: _MoveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    moved = await MediaService.move_to_folder(db, body.ids, body.folder)
    await db.commit()
    return {"moved": moved}


@router.get(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Get media asset by ID",
    dependencies=[Depends(RequirePermissions("media:read"))],
)
async def get_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Get metadata for a single media asset."""
    asset = await MediaService.get_asset(db, asset_id)
    return await _asset_response(db, asset)


@router.get(
    "/{asset_id}/variant",
    summary="On-the-fly resized image variant (public, disk-cached)",
    response_class=Response,
    responses={200: {"content": {"image/webp": {}, "image/jpeg": {}, "image/png": {}}}},
)
@limiter.limit("120/minute")
async def get_media_variant(
    request: Request,
    asset_id: uuid.UUID,
    width: int | None = Query(None, ge=1, le=4096),
    height: int | None = Query(None, ge=1, le=4096),
    quality: int = Query(82, ge=1, le=100),
    fmt: str = Query("webp", pattern="^(webp|jpeg|png)$"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Strapi/Payload-style delivery transform: ``/media/{id}/variant?width=300``."""
    content, mime = await MediaService.get_image_variant(
        db, asset_id, width=width, height=height, quality=quality, fmt=fmt
    )
    return Response(
        content=content,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


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


@router.patch(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Update media asset metadata (WordPress parity)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def update_media_asset(
    asset_id: uuid.UUID,
    body: MediaAssetUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Update alt_text, caption, description, folder of a media asset."""
    from app.modules.media.domain.models import MediaAsset

    asset = await db.get(MediaAsset, asset_id)
    if not asset:
        from app.core.exceptions.handlers import NotFoundError
        raise NotFoundError("MediaAsset", f"Asset {asset_id} not found")

    if body.alt_text is not None:
        asset.alt_text = body.alt_text.strip() or None
    if body.caption is not None:
        asset.caption = body.caption.strip() or None
    if body.description is not None:
        asset.description = body.description.strip() or None
    if body.folder is not None:
        asset.folder = body.folder.strip() or None

    await db.commit()
    await db.refresh(asset)
    return await _asset_response(db, asset)


# ── Image editing & processing (WordPress parity) ────────────────────────


@router.post(
    "/{asset_id}/edit/crop",
    response_model=MediaAssetResponse,
    summary="Crop an image (creates a new asset)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def crop_media_asset(
    asset_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Crop an image to the given rectangle, creating a new media asset."""
    from app.modules.media.application.image_editor import ImageEditor
    from app.modules.media.application.media_service import MediaService

    new_path = await ImageEditor.crop(
        (await _get_asset_path(db, asset_id)),
        x=int(body["x"]), y=int(body["y"]),
        width=int(body["width"]), height=int(body["height"]),
    )
    derived = await MediaService.register_derived_asset(db, asset_id, new_path, suffix="crop")
    return await _asset_response(db, derived)


@router.post(
    "/{asset_id}/edit/resize",
    response_model=MediaAssetResponse,
    summary="Resize an image (creates a new asset)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def resize_media_asset(
    asset_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Resize an image, creating a new media asset."""
    from app.modules.media.application.image_editor import ImageEditor
    from app.modules.media.application.media_service import MediaService

    new_path = await ImageEditor.resize(
        (await _get_asset_path(db, asset_id)),
        width=int(body["width"]),
        height=int(body["height"]) if body.get("height") else None,
    )
    derived = await MediaService.register_derived_asset(db, asset_id, new_path, suffix="resize")
    return await _asset_response(db, derived)


@router.post(
    "/{asset_id}/edit/rotate",
    response_model=MediaAssetResponse,
    summary="Rotate an image (creates a new asset)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def rotate_media_asset(
    asset_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Rotate an image by 90/180/270 degrees, creating a new media asset."""
    from app.modules.media.application.image_editor import ImageEditor
    from app.modules.media.application.media_service import MediaService

    new_path = await ImageEditor.rotate(
        (await _get_asset_path(db, asset_id)),
        degrees=int(body.get("degrees", 90)),
    )
    derived = await MediaService.register_derived_asset(db, asset_id, new_path, suffix="rotate")
    return await _asset_response(db, derived)


@router.post(
    "/{asset_id}/edit/flip",
    response_model=MediaAssetResponse,
    summary="Flip an image horizontally or vertically (creates a new asset)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def flip_media_asset(
    asset_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Mirror an image on one axis, creating a new media asset.

    ``horizontal`` mirrors left-right (the fix for a photo shot through glass
    or a scanned document); the default false mirrors top-bottom. Same shape
    as the rotate/crop/resize edits: the original is never overwritten, a
    derived row points at the new file.
    """
    from app.modules.media.application.image_editor import ImageEditor
    from app.modules.media.application.media_service import MediaService

    horizontal = bool(body.get("horizontal", True))
    new_path = await ImageEditor.flip(
        await _get_asset_path(db, asset_id),
        horizontal=horizontal,
    )
    suffix = "fliph" if horizontal else "flipv"
    derived = await MediaService.register_derived_asset(db, asset_id, new_path, suffix=suffix)
    return await _asset_response(db, derived)


@router.get(
    "/{asset_id}/exif",
    summary="Extract EXIF metadata from an image",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def get_media_exif(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return EXIF metadata (camera, lens, GPS) for an image asset."""
    from app.modules.media.application.image_processor import ImageProcessor

    return await ImageProcessor.extract_exif(await _get_asset_path(db, asset_id))


@router.post(
    "/{asset_id}/regenerate-thumbnails",
    summary="Regenerate thumbnails for one asset",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def regenerate_asset_thumbnails(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate all thumbnail sizes for a single media asset."""
    from app.modules.media.application.thumbnail_regenerator import regenerate_single

    sizes = await regenerate_single(db, asset_id)
    return {"asset_id": str(asset_id), "generated": list(sizes.keys()), "files": sizes}


@router.post(
    "/regenerate-all-thumbnails",
    summary="Regenerate thumbnails for the whole library",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def regenerate_all_thumbnails(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Batch-regenerate thumbnails for every image in the media library."""
    from app.modules.media.application.thumbnail_regenerator import regenerate_all

    return await regenerate_all(db)


@router.post(
    "/{asset_id}/optimize",
    summary="Optimize an image (compress, optional WebP)",
    dependencies=[Depends(RequirePermissions("media:write"))],
)
async def optimize_media_asset(
    asset_id: uuid.UUID,
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compress an image, optionally converting to WebP."""
    from app.modules.media.application.image_optimizer import ImageOptimizer

    body = body or {}
    return await ImageOptimizer.optimize(
        await _get_asset_path(db, asset_id),
        quality=int(body.get("quality", 82)),
        convert_to_webp=bool(body.get("convert_to_webp", False)),
    )


async def _get_asset_path(db: AsyncSession, asset_id: uuid.UUID) -> str:
    """Load a media asset's on-disk path, or 404.

    The stored column is a root-relative key (``media/<name>``), not a path the
    filesystem can open from the process's working directory — returning it
    verbatim sent every crop/resize/rotate/EXIF/optimize call to a file that
    does not exist. The shared layout helper resolves it the same way the
    serving route and the thumbnail regenerator do, preferring the served URL
    over the stored key because rows written before the layouts were aligned
    can point somewhere the upload never wrote.
    """
    from app.core.config.settings import get_settings
    from app.core.exceptions.handlers import NotFoundError
    from app.modules.media.application.storage_paths import candidate_sources
    from app.modules.media.domain.models import MediaAsset

    asset = await db.get(MediaAsset, asset_id)
    if not asset:
        raise NotFoundError("MediaAsset", f"Asset {asset_id} not found")

    base_dir = Path(getattr(get_settings(), "UPLOAD_DIR", "media"))
    candidates = candidate_sources(base_dir, asset.file_url or "", asset.file_path)
    resolved = next((p for p in candidates if p.exists()), candidates[0])
    return str(resolved)
