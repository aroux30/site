"""Media asset API endpoints.

Rebuilt 2026-10-02 after an editing mistake truncated this file to seven lines.
Every route below was reconstructed from the service method it calls and the
schema it returns — the signatures here are the ones the service actually has,
so a mismatch surfaces as a TypeError at import time rather than as a route that
404s. Where a behaviour could not be read off the service, it is marked and the
fixture in `.p1-tests/media_route_contract_test.py` is what pins it.

The order matters in one place: `/folders` and `/move` are declared before
`/{asset_id}`, because a path parameter declared first would swallow the
literal ones. FastAPI matches in declaration order.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.database.session import AsyncSession, get_db
from app.core.exceptions.handlers import ConflictError
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_optional,
)
from app.modules.media.application.media_service import MediaService
from app.modules.media.domain.models import MediaAsset
from app.modules.media.schemas.media import (
    MediaAssetListResponse,
    MediaAssetResponse,
    MediaAssetUpdateRequest,
    MediaBatchUploadError,
    MediaBatchUploadResponse,
    MediaUploadResponse,
)

#: A customer's return photo, against the 100 MB staff ceiling. A shopper on a
#: phone is not uploading a product catalogue, and the route is unauthenticated
#: in the sense that matters: any signed-in customer reaches it.
CUSTOMER_UPLOAD_MAX_BYTES = 10 * 1024 * 1024

# No prefix here: `main.py` mounts this module's routers under `/media`
# already, so a prefix on the router would produce `/api/v1/media/media/...`.
router = APIRouter(tags=["media"])

#: Admin surfaces. The library is a staff tool; a customer must not be able to
#: enumerate it, and a signed-in customer is not staff.
admin_router = APIRouter(tags=["media-admin"])

_require_media_read = Depends(RequirePermissions("media:read"))
_require_media_write = Depends(RequirePermissions("media:write"))


async def _asset_response(db: AsyncSession, asset: MediaAsset) -> MediaAssetResponse:
    """Project a row onto the response schema.

    A single place, because the variants (thumbnail width, derived-from marker)
    are computed from the same row in every route and a per-route projection is
    how one of them ends up stale.
    """
    return MediaAssetResponse.model_validate(asset)


# ============================================================================
# Upload
# ============================================================================


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=201,
    summary="Upload a file (admin)",
    dependencies=[_require_media_write],
)
async def upload_media(
    file: UploadFile = File(...),
    alt_text: str | None = Query(None),
    folder: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    asset = await MediaService.upload_file(
        db, file, uploader_id=None, alt_text=alt_text, folder=folder
    )
    return MediaUploadResponse(asset=await _asset_response(db, asset))


@router.post(
    "/upload/batch",
    response_model=MediaBatchUploadResponse,
    status_code=201,
    summary="Upload several files (admin)",
    dependencies=[_require_media_write],
)
async def upload_media_batch(
    files: list[UploadFile] = File(...),
    folder: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> MediaBatchUploadResponse:
    """Upload many files, reporting each outcome separately.

    Per-file rather than all-or-nothing: a batch of forty product photos with
    one unsupported file in it should not mean re-picking the other thirty-nine.
    """
    assets: list[MediaAssetResponse] = []
    errors: list[MediaBatchUploadError] = []
    for uploaded in files:
        try:
            asset = await MediaService.upload_file(
                db, uploaded, uploader_id=None, folder=folder
            )
            assets.append(await _asset_response(db, asset))
        except Exception as exc:  # noqa: BLE001 — one bad file must not abort the batch
            errors.append(
                MediaBatchUploadError(
                    file_name=uploaded.filename or "",
                    error=str(getattr(exc, "detail", exc)),
                )
            )
    return MediaBatchUploadResponse(items=assets, errors=errors)


# ============================================================================
# Listing
# ============================================================================


@router.get(
    "",
    response_model=MediaAssetListResponse,
    summary="List uploaded media assets with pagination.",
    dependencies=[_require_media_read],
)
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mime_type: str | None = Query(None, description="Filter by MIME type prefix e.g. 'image/'"),
    folder: str | None = Query(None, description="Folder path; '' = root, omitted = all"),
    search: str | None = Query(
        None, description="Match the file name or alt text, case-insensitively"
    ),
    include_trashed: bool = Query(
        False, description="Include soft-deleted assets (the trash view)"
    ),
    post_id: uuid.UUID | None = Query(
        None, description="Only assets attached to this post"
    ),
    unattached: bool = Query(
        False,
        description="Only assets attached to nothing (cannot be combined with post_id)",
    ),
    created_from: datetime | None = Query(
        None, description="Only assets uploaded at or after this instant"
    ),
    created_to: datetime | None = Query(
        None, description="Only assets uploaded at or before this instant"
    ),
    db: AsyncSession = Depends(get_db),
) -> MediaAssetListResponse:
    """List uploaded media assets with pagination.

    Trashed assets are excluded by default, so the library never offers a file
    that is already on its way out.

    ``post_id`` and ``unattached`` are the two halves of the "Attached to"
    column, which had a model column and no writer — so this filter had nothing
    to match and the unattached view could only ever be "everything".
    """
    if post_id is not None and unattached:
        # A contradiction rather than a preference: the operator asked for one
        # post's media and also for media attached to nothing. Refusing here
        # beats returning a list that satisfies neither reading.
        raise HTTPException(
            status_code=400,
            detail="post_id و unattached نمی‌توانند با هم استفاده شوند",
        )
    items, total = await MediaService.list_assets(
        db,
        page=page,
        page_size=page_size,
        mime_prefix=mime_type,
        folder=folder,
        search=search,
        include_trashed=include_trashed,
        post_id=post_id,
        unattached=unattached,
        created_from=created_from,
        created_to=created_to,
    )
    total_pages = max(1, math.ceil(total / page_size)) if total else 0
    return MediaAssetListResponse(
        items=[await _asset_response(db, a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/folders",
    summary="List media folders with asset counts (admin)",
    dependencies=[_require_media_read],
)
async def list_media_folders(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await MediaService.list_folders(db)


class _FolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=300)


class _FolderDeleteRequest(_FolderRequest):
    delete_assets: bool = Field(
        False,
        description="Also delete the files inside. Without it a non-empty "
                    "folder is refused rather than emptied.",
    )


@router.post(
    "/folders",
    summary="Create a media folder (admin)",
    dependencies=[_require_media_write],
)
async def create_media_folder(
    body: _FolderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a folder, empty or not.

    Folders here are the distinct ``folder`` values on assets, so before this an
    empty folder could not exist — you could only make one by uploading into it.
    Laying out ``products/shoes`` before the first product photo is the normal
    way anyone builds a library, and it used to be impossible.
    """
    return await MediaService.create_folder(db, body.path)


@router.delete(
    "/folders",
    summary="Delete a media folder (admin)",
    dependencies=[_require_media_write],
)
async def delete_media_folder(
    body: _FolderDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a folder.

    Refuses a folder that still holds files unless ``delete_assets`` is set.
    Removing forty product photos because somebody deleted a folder is not
    recoverable, and the operator who meant it can say so.
    """
    return await MediaService.delete_folder(
        db, body.path, delete_assets=body.delete_assets
    )


# ============================================================================
# Trash
#
# Every route in this block has a literal first segment (`/trash`,
# `/bulk-trash`), and several share their shape with the single-asset routes
# below (`GET /{asset_id}`, `DELETE /{asset_id}`). FastAPI matches in
# declaration order, so those two must come first or they swallow `/trash`:
# every trash call used to answer 422 because `/trash` was parsed as an asset
# id, and `/trash/empty` was parsed as a UUID the same way. The whole block
# therefore lives above the single-asset section, not next to the handlers it
# belongs to by topic.
# ============================================================================


class _BulkTrashRequest(BaseModel):
    """Ids to trash. Capped so one request cannot fan out unbounded."""

    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)
    # Force means "yes, break the references". The files still land in the
    # trash, so a mistaken bulk delete stays recoverable.
    force: bool = False


class MediaTrashListResponse(BaseModel):
    """The trash view's page: trashed assets and how many exist in total."""

    items: list[MediaAssetResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class _EmptyTrashResponse(BaseModel):
    """How many assets a purge removed.

    An object, not a bare number: the route returned ``int`` while its
    annotation said ``dict``, so every call failed response validation with a
    500 after the purge had already happened. A purge that reports failure
    after deleting the files is worse than one that reports nothing.
    """

    purged: int


@router.post(
    "/bulk-trash",
    summary="Trash several assets at once (admin)",
    dependencies=[_require_media_write],
)
async def bulk_trash_media(
    body: _BulkTrashRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await MediaService.bulk_trash(
        db, body.ids, force=body.force
    )
    return result


@router.get(
    "/trash",
    response_model=MediaTrashListResponse,
    summary="List trashed assets (admin)",
    dependencies=[_require_media_read],
)
async def list_media_trash(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> MediaTrashListResponse:
    items, total = await MediaService.list_trashed(
        db, page=page, page_size=page_size
    )
    return MediaTrashListResponse(
        items=[await _asset_response(db, a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)) if total else 0,
    )


@router.post(
    "/trash/empty",
    response_model=_EmptyTrashResponse,
    summary="Empty the media trash (admin)",
    dependencies=[_require_media_write],
)
async def empty_media_trash(
    older_than_days: int | None = Query(
        None, ge=0, description="Only purge files trashed longer ago than this"
    ),
    db: AsyncSession = Depends(get_db),
) -> _EmptyTrashResponse:
    """Purge the trash, optionally only entries older than N days.

    ``POST`` rather than ``DELETE /trash``: the client sends a query-string
    filter, and the empty-trash action is a command with a parameter, not the
    deletion of the collection itself.
    """
    purged = await MediaService.empty_trash(db, older_than_days=older_than_days)
    return _EmptyTrashResponse(purged=purged)


@router.delete(
    "/trash",
    response_model=_EmptyTrashResponse,
    summary="Empty the media trash (admin)",
    dependencies=[_require_media_write],
)
async def empty_media_trash_legacy(
    older_than_days: int | None = Query(
        None, ge=0, description="Only purge files trashed longer ago than this"
    ),
    db: AsyncSession = Depends(get_db),
) -> _EmptyTrashResponse:
    """The collection-shaped spelling of the same purge, kept for callers
    written against the first rebuild. Same service call, same answer."""
    purged = await MediaService.empty_trash(db, older_than_days=older_than_days)
    return _EmptyTrashResponse(purged=purged)


@router.post(
    "/trash/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Trash one asset (admin)",
    dependencies=[_require_media_write],
)
async def trash_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.trash_asset(db, asset_id)
    return await _asset_response(db, asset)


@router.delete(
    "/trash/{asset_id}",
    summary="Permanently delete one trashed asset (admin)",
    dependencies=[_require_media_write],
)
async def purge_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete one trashed asset for good — the row and its bytes.

    Refused for an asset that is not in the trash, so "delete" from the
    library can never reach this: it goes through the trash first, and this is
    the explicit second step the trash panel's «حذف دائمی» button performs.
    """
    await MediaService.purge_asset(db, asset_id)
    return {"purged": str(asset_id)}


# ============================================================================
# Single asset
# ============================================================================


@router.get(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Get one media asset",
    dependencies=[_require_media_read],
)
async def get_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.get_asset(db, asset_id)
    return await _asset_response(db, asset)


@router.patch(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    summary="Update media metadata (admin)",
    dependencies=[_require_media_write],
)
async def update_media_asset(
    asset_id: uuid.UUID,
    body: MediaAssetUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.get_asset(db, asset_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)
    await db.commit()
    await db.refresh(asset)
    return await _asset_response(db, asset)


@router.get(
    "/{asset_id}/variant",
    summary="Server-rendered image variant URL",
    dependencies=[_require_media_read],
)
async def get_media_variant(
    asset_id: uuid.UUID,
    width: int | None = Query(None, ge=1, le=4000),
    height: int | None = Query(None, ge=1, le=4000),
    quality: int | None = Query(None, ge=1, le=100),
    fmt: str | None = Query(None, description="webp | jpeg | png"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await MediaService.get_image_variant(
        db, asset_id, width=width, height=height, quality=quality, fmt=fmt
    )


# ============================================================================
# Image editing and processing
# ============================================================================


class _FocalPointRequest(BaseModel):
    focal_x: float
    focal_y: float


class _AttachRequest(BaseModel):
    """The post an asset belongs to.

    Required rather than optional even though it may be null: "attach to
    nothing" and "I did not say" are the same wire value otherwise, and the
    second would silently detach. Making the caller state it is the whole
    difference between an intentional detach and a dropped field.
    """

    post_id: uuid.UUID | None


class _TransformRequest(BaseModel):
    """Shared body for crop/rotate/resize. Angles are degrees."""

    angle: float = Field(0.0, description="Rotation in degrees")
    width: int | None = Field(None, ge=1, le=20000)
    height: int | None = Field(None, ge=1, le=20000)
    left: int | None = Field(None, ge=0)
    top: int | None = Field(None, ge=0)
    right: int | None = Field(None, ge=0)
    bottom: int | None = Field(None, ge=0)


@router.patch(
    "/{asset_id}/focal-point",
    response_model=MediaAssetResponse,
    summary="Set smart-crop focal point (admin)",
    dependencies=[_require_media_write],
)
async def set_focal_point(
    asset_id: uuid.UUID,
    body: _FocalPointRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.set_focal_point(db, asset_id, body.focal_x, body.focal_y)
    await db.commit()
    return await _asset_response(db, asset)


@router.put(
    "/{asset_id}/attach",
    response_model=MediaAssetResponse,
    summary="Attach an asset to a post, or detach it (admin)",
    dependencies=[_require_media_write],
)
async def attach_media_to_post(
    asset_id: uuid.UUID,
    body: _AttachRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Point an asset at a post, or at nothing.

    WordPress's "Attached to" column. The model column existed from the start
    with no writer and no filter, so an operator asking "where is this image
    used" had a field to read and a blank in it.

    ``post_id: null`` detaches. That is the same value as "not supplied", which
    is why this is a PUT of a whole object rather than a bare link: the caller
    has to say what it means, and an omitted field would otherwise detach
    something by accident.
    """
    asset = await MediaService.attach_to_post(db, asset_id, body.post_id)
    return await _asset_response(db, asset)


# ============================================================================
# Move
# ============================================================================


class _MoveRequest(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)
    folder: str | None = Field(
        None, description="Target folder path; null moves to the root"
    )


@router.post(
    "/move",
    summary="Move media assets to a folder (admin)",
    dependencies=[_require_media_write],
)
async def move_media(
    body: _MoveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    moved = await MediaService.move_to_folder(db, body.ids, body.folder)
    return {"moved": moved}


# ============================================================================
# Side-load from a URL
# ============================================================================


class _SideloadRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000)
    alt_text: str | None = None
    folder: str | None = None


@router.post(
    "/sideload",
    response_model=MediaAssetResponse,
    status_code=201,
    summary="Fetch an image from a URL and store it (admin)",
    dependencies=[_require_media_write],
)
async def sideload_media(
    body: _SideloadRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Download an image and store it as an asset.

    The SSRF guard lives in `sideload_service`: private and loopback addresses
    are refused there, not here, so every caller of that function gets the same
    rule and a new one cannot be added without it.
    """
    from app.modules.media.application.sideload_service import sideload_image

    asset = await sideload_image(
        db, body.url, alt_text=body.alt_text, folder=body.folder
    )
    return await _asset_response(db, asset)


# ============================================================================
# Usage
# ============================================================================


@router.get(
    "/{asset_id}/usage",
    summary="Where a media asset is used (admin)",
    dependencies=[_require_media_read],
)
async def get_media_usage(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Every place this file is referenced.

    The warning an operator gets before deleting an image is only as good as
    this count, so it is a route rather than a field on the asset: the count
    is a join across several tables and putting it in the list response would
    make every page of the library pay for it.
    """
    from app.modules.media.application.usage_service import count_media_usage

    asset = await MediaService.get_asset(db, asset_id)
    return await count_media_usage(db, asset.file_name)


# ============================================================================
# Image editing, EXIF, thumbnails
# ============================================================================


class _CropRequest(BaseModel):
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)


class _ResizeRequest(BaseModel):
    width: int = Field(..., ge=1, le=20000)
    height: int | None = Field(None, ge=1, le=20000)
    maintain_aspect: bool = True


class _RotateRequest(BaseModel):
    degrees: int = Field(90, description="90, 180 or 270")


class _FlipRequest(BaseModel):
    horizontal: bool = True


class _OptimizeRequest(BaseModel):
    quality: int = Field(82, ge=1, le=100)
    convert_to_webp: bool = False


def _resolve_edit_source(asset: MediaAsset) -> str:
    """The absolute on-disk path of an asset's own bytes, for the editor.

    The edit routes used to pass ``asset.file_path`` — which is ``media/<name>``,
    a path *relative to* the uploads root — straight to ``ImageEditor``. The
    editor opens it relative to the process cwd, so it looked for
    ``<cwd>/media/<name>`` while the file lives at
    ``<cwd>/<UPLOAD_DIR>/media/<name>`` (``media/media/<name>`` in the standard
    layout): every crop, resize, rotate and flip raised FileNotFoundError.

    Resolves through the same candidate list the restore check and delete sweep
    use, so the four cannot disagree about where a file lives.
    """
    from pathlib import Path

    from app.core.config.settings import get_settings
    from app.modules.media.application.storage_paths import MEDIA_SUBDIR

    base_dir = Path(getattr(get_settings(), "UPLOAD_DIR", "media"))
    resolved = MediaService._resolve_source_path(base_dir, asset)
    if resolved is None:
        raise NotFoundError(
            "MediaAsset",
            f"فایل {asset.file_name} روی دیسک نیست و قابل ویرایش نیست",
        )
    return str(resolved)


async def _edited_asset(
    db: AsyncSession, asset_id: uuid.UUID, new_path: str, operation: str
) -> MediaAssetResponse:
    """Register a file the editor produced as a derived asset.

    Every edit goes through here so the chain is recorded: the edit-history
    panel walks `source_asset_id`, and a route that skipped it would leave an
    edited file with no way back to its original.

    ``operation`` ("crop"/"resize"/"rotate"/"flip") is stored as the edit
    operation, which is what the history list shows. It doubles as the
    filename suffix, so a bare "edit" would make every step read "ویرایش"
    with no way to tell a rotation from a crop.
    """
    asset = await MediaService.register_derived_asset(
        db, asset_id, new_path, suffix=operation
    )
    return await _asset_response(db, asset)


@router.post(
    "/{asset_id}/edit/crop",
    response_model=MediaAssetResponse,
    summary="Crop an image non-destructively (admin)",
    dependencies=[_require_media_write],
)
async def crop_media_asset(
    asset_id: uuid.UUID,
    body: _CropRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    from app.modules.media.application.image_editor import ImageEditor

    asset = await MediaService.get_asset(db, asset_id)
    new_path = await ImageEditor().crop(
        _resolve_edit_source(asset), x=body.x, y=body.y, width=body.width, height=body.height
    )
    return await _edited_asset(db, asset_id, new_path, "crop")


@router.post(
    "/{asset_id}/edit/resize",
    response_model=MediaAssetResponse,
    summary="Resize an image non-destructively (admin)",
    dependencies=[_require_media_write],
)
async def resize_media_asset(
    asset_id: uuid.UUID,
    body: _ResizeRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    from app.modules.media.application.image_editor import ImageEditor

    asset = await MediaService.get_asset(db, asset_id)
    new_path = await ImageEditor().resize(
        _resolve_edit_source(asset), width=body.width, height=body.height,
        maintain_aspect=body.maintain_aspect,
    )
    return await _edited_asset(db, asset_id, new_path, "resize")


@router.post(
    "/{asset_id}/edit/rotate",
    response_model=MediaAssetResponse,
    summary="Rotate an image non-destructively (admin)",
    dependencies=[_require_media_write],
)
async def rotate_media_asset(
    asset_id: uuid.UUID,
    body: _RotateRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    from app.modules.media.application.image_editor import ImageEditor

    asset = await MediaService.get_asset(db, asset_id)
    new_path = await ImageEditor().rotate(_resolve_edit_source(asset), degrees=body.degrees)
    return await _edited_asset(db, asset_id, new_path, "rotate")


@router.post(
    "/{asset_id}/edit/flip",
    response_model=MediaAssetResponse,
    summary="Flip an image non-destructively (admin)",
    dependencies=[_require_media_write],
)
async def flip_media_asset(
    asset_id: uuid.UUID,
    body: _FlipRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    from app.modules.media.application.image_editor import ImageEditor

    asset = await MediaService.get_asset(db, asset_id)
    new_path = await ImageEditor().flip(
        _resolve_edit_source(asset), horizontal=body.horizontal
    )
    return await _edited_asset(db, asset_id, new_path, "flip")


@router.get(
    "/{asset_id}/edit/history",
    summary="The chain of non-destructive edits (admin)",
    dependencies=[_require_media_read],
)
async def get_media_edit_history(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await MediaService.list_edit_history(db, asset_id)


@router.post(
    "/{asset_id}/edit/restore-original",
    response_model=MediaAssetResponse,
    summary="Undo every edit and go back to the original (admin)",
    dependencies=[_require_media_write],
)
async def restore_media_original(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.restore_original(db, asset_id)
    return await _asset_response(db, asset)


@router.post(
    "/{asset_id}/edit/duplicate",
    response_model=MediaAssetResponse,
    status_code=201,
    summary="Save a standalone copy of an asset (admin)",
    dependencies=[_require_media_write],
)
async def duplicate_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Copy the bytes and metadata into a new asset with no chain link.

    "Save as a copy": the operator wants this version as its own file without
    touching the edit chain it currently sits in. The copy gets its own
    derivatives, so it renders at every size like any other asset.
    """
    asset = await MediaService.duplicate_asset(db, asset_id)
    return await _asset_response(db, asset)


@router.post(
    "/{asset_id}/optimize",
    response_model=MediaAssetResponse,
    summary="Re-encode an image at lower quality (admin)",
    dependencies=[_require_media_write],
)
async def optimize_media_asset(
    asset_id: uuid.UUID,
    body: _OptimizeRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    from app.modules.media.application.image_optimizer import ImageOptimizer

    asset = await MediaService.get_asset(db, asset_id)
    new_path = await ImageOptimizer().optimize(
        _resolve_edit_source(asset), quality=body.quality,
        convert_to_webp=body.convert_to_webp,
    )
    return await _edited_asset(db, asset_id, new_path, "optimize")


@router.get(
    "/{asset_id}/exif",
    summary="EXIF metadata of an image (admin)",
    dependencies=[_require_media_read],
)
async def get_media_exif(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.media.application.image_processor import ImageProcessor

    asset = await MediaService.get_asset(db, asset_id)
    # Resolve the real on-disk path, like the edit routes: `asset.file_path` is
    # `media/<name>` relative to the uploads root, and `extract_exif` opens from
    # cwd — the same wrong-base bug that broke every image edit. EXIF read of
    # the wrong path returned an empty dict rather than raising, so an operator
    # saw "no camera data" for a photo that had plenty.
    return await ImageProcessor().extract_exif(_resolve_edit_source(asset))


@router.post(
    "/{asset_id}/regenerate-thumbnails",
    summary="Rebuild one asset's thumbnails (admin)",
    dependencies=[_require_media_write],
)
async def regenerate_asset_thumbnails(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    from app.modules.media.application.thumbnail_regenerator import regenerate_single

    return await regenerate_single(db, asset_id)


@router.post(
    "/regenerate-all-thumbnails",
    summary="Rebuild every thumbnail (admin)",
    dependencies=[_require_media_write],
)
async def regenerate_all_thumbnails(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    from app.modules.media.application.thumbnail_regenerator import regenerate_all

    return await regenerate_all(db)


# ============================================================================
# Upload: customer return proof
# ============================================================================


@router.post(
    "/upload/return-proof",
    response_model=MediaAssetResponse,
    status_code=201,
    summary="Upload a photo proving a return (customer)",
)
async def upload_return_proof(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] | None = Depends(get_current_user_optional),
) -> MediaAssetResponse:
    """A customer's own photo of a returned item.

    Not behind `media:write`: this is the one media route a customer reaches,
    and gating it on the staff permission would make the returns flow
    unusable. Capped well below the staff ceiling so a customer upload cannot
    allocate a staff video upload's buffer.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="ورود لازم است")
    uploader_id = None
    try:
        uploader_id = uuid.UUID(current_user["sub"])
    except Exception:  # noqa: BLE001 — a malformed sub is "no uploader"
        pass
    asset = await MediaService.upload_file(
        db, file, uploader_id=uploader_id, max_bytes=CUSTOMER_UPLOAD_MAX_BYTES
    )
    return await _asset_response(db, asset)


@router.post(
    "/{asset_id}/replace",
    response_model=MediaAssetResponse,
    summary="Replace an asset's file, keeping its URL (admin)",
    dependencies=[_require_media_write],
)
async def replace_media_file(
    asset_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    """Swap the bytes behind an asset without changing its URL.

    WordPress's "Enable Media Replace". The URL is the asset's public
    identity — pages, feeds and ads point at it — so replacing the file is
    the operation that keeps those references working while the picture
    changes. The new file must be the same type; anything else is a delete
    and a re-upload.
    """
    asset = await MediaService.replace_file(db, asset_id, file)
    return await _asset_response(db, asset)


@router.post(
    "/{asset_id}/restore",
    response_model=MediaAssetResponse,
    summary="Restore a trashed asset (admin)",
    dependencies=[_require_media_write],
)
async def restore_media_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MediaAssetResponse:
    asset = await MediaService.restore_asset(db, asset_id)
    return await _asset_response(db, asset)


@router.delete(
    "/{asset_id}",
    summary="Permanently delete one asset (admin)",
    dependencies=[_require_media_write],
)
async def delete_media_asset(
    asset_id: uuid.UUID,
    force: bool = Query(
        False, description="Delete even if something still references it"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await MediaService.delete_asset(db, asset_id, force=force)
    return {"deleted": str(asset_id)}
