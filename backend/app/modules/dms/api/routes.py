"""DMS API: polymorphic attachments + the fiscal archive index.

Attachment paths are guarded by ``documents:read``/``documents:write``; the
archive is read-only through the API (there is deliberately no delete route —
see the module docstring in ``document_service``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.dms.application import document_service as svc
from app.modules.dms.domain.models import (
    ATTACHABLE_ENTITY_TYPES,
    ArchivedDocumentKind,
    AttachmentKind,
)

router = APIRouter()
_ADMIN = "/admin"


# ── Schemas ─────────────────────────────────────────────────────────────────


class AttachmentCreateRequest(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: uuid.UUID
    file_name: str = Field(..., min_length=1, max_length=255)
    file_url: str = Field(
        ..., min_length=1, max_length=500, description="مسیر نسبی فروشگاه رسانه"
    )
    file_size: int = Field(..., ge=0)
    content_type: str | None = Field(None, max_length=150)
    kind: AttachmentKind = AttachmentKind.GENERAL
    title: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=5000)


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    kind: str
    file_name: str
    file_url: str
    file_size: int
    content_type: str | None = None
    title: str | None = None
    notes: str | None = None
    uploaded_by_id: uuid.UUID | None = None
    created_at: datetime


class ArchivedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    document_key: str
    entity_type: str
    entity_id: uuid.UUID
    archive_path: str
    content_type: str
    file_size: int | None = None
    content_hash: str | None = None
    metadata_json: dict[str, Any] | None = None
    fiscal_period: str | None = None
    is_superseded: bool
    created_at: datetime


class AttachableTypesResponse(BaseModel):
    """The registry of entity types an attachment may target."""

    entity_types: list[str]


# ── Attachments ─────────────────────────────────────────────────────────────


@router.get(
    f"{_ADMIN}/attachable-types",
    response_model=AttachableTypesResponse,
    dependencies=[Depends(RequirePermissions("documents:read"))],
    summary="Entity types that accept attachments",
)
async def list_attachable_types() -> AttachableTypesResponse:
    """What the UI may offer as an attachment target."""
    return AttachableTypesResponse(entity_types=sorted(ATTACHABLE_ENTITY_TYPES))


@router.post(
    f"{_ADMIN}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("documents:write"))],
    summary="Attach a stored file to a business record (admin)",
)
async def create_attachment(
    body: AttachmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> AttachmentResponse:
    """Register an uploaded file against a record.

    The file itself is uploaded through the media module first; this endpoint
    records the link. Requires ``documents:write``.
    """
    attachment = await svc.create_attachment(
        db,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        file_name=body.file_name,
        file_url=body.file_url,
        file_size=body.file_size,
        content_type=body.content_type,
        kind=body.kind,
        title=body.title,
        notes=body.notes,
        uploaded_by_id=actor_id,
    )
    await db.commit()
    return AttachmentResponse.model_validate(attachment)


@router.get(
    f"{_ADMIN}/attachments",
    response_model=list[AttachmentResponse],
    dependencies=[Depends(RequirePermissions("documents:read"))],
    summary="Attachments on one record (admin)",
)
async def list_attachments(
    db: AsyncSession = Depends(get_db),
    entity_type: str = Query(..., description="e.g. order, purchase_order, vendor"),
    entity_id: uuid.UUID = Query(...),
    kind: AttachmentKind | None = Query(None, description="Filter by document kind"),
) -> list[AttachmentResponse]:
    """Everything attached to one record, newest first."""
    rows = await svc.list_attachments(
        db, entity_type=entity_type, entity_id=entity_id, kind=kind
    )
    return [AttachmentResponse.model_validate(r) for r in rows]


@router.get(
    f"{_ADMIN}/attachments/counts",
    dependencies=[Depends(RequirePermissions("documents:read"))],
    summary="Per-kind attachment counts for one record (admin)",
)
async def count_attachments(
    db: AsyncSession = Depends(get_db),
    entity_type: str = Query(...),
    entity_id: uuid.UUID = Query(...),
) -> dict[str, int]:
    """Badge counts for a record's attachment button."""
    return await svc.count_attachments_by_kind(
        db, entity_type=entity_type, entity_id=entity_id
    )


@router.delete(
    f"{_ADMIN}/attachments/{{attachment_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("documents:write"))],
    summary="Remove an attachment link (admin)",
)
async def delete_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete the attachment row. The stored file is left to the media module,
    which knows whether another record still references it."""
    await svc.delete_attachment(db, attachment_id=attachment_id)
    await db.commit()


# ── Fiscal archive (read-only through the API) ──────────────────────────────


@router.get(
    f"{_ADMIN}/archive",
    response_model=list[ArchivedDocumentResponse],
    dependencies=[Depends(RequirePermissions("documents:read"))],
    summary="Search the fiscal archive (admin)",
)
async def list_archived(
    db: AsyncSession = Depends(get_db),
    kind: ArchivedDocumentKind | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: uuid.UUID | None = Query(None),
    fiscal_period: str | None = Query(None, description="دوره مالی شمسی، مثلاً 1404"),
    document_key: str | None = Query(None, description="شماره سند"),
    include_superseded: bool = Query(
        False, description="نمایش نسخه‌های جایگزین‌شده هم بیاید"
    ),
    limit: int = Query(100, ge=1, le=500),
) -> list[ArchivedDocumentResponse]:
    """The auditor's search: one index over frozen documents across modules."""
    rows = await svc.list_archived_documents(
        db,
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        fiscal_period=fiscal_period,
        document_key=document_key,
        include_superseded=include_superseded,
        limit=limit,
    )
    return [ArchivedDocumentResponse.model_validate(r) for r in rows]


@router.get(
    f"{_ADMIN}/archive/summary",
    dependencies=[Depends(RequirePermissions("documents:read"))],
    summary="Archive counts by document kind (admin)",
)
async def archived_summary(
    db: AsyncSession = Depends(get_db),
    fiscal_period: str | None = Query(None),
) -> dict[str, int]:
    """How much of each kind is archived (optionally within a fiscal period)."""
    rows = await svc.list_archived_documents(
        db, fiscal_period=fiscal_period, limit=500
    )
    return svc.archive_summary(rows)


@router.get(
    f"{_ADMIN}/archive/{{document_id}}",
    response_model=ArchivedDocumentResponse,
    dependencies=[Depends(RequirePermissions("documents:read"))],
    summary="One archived document (admin)",
)
async def get_archived(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ArchivedDocumentResponse:
    """Fetch one archive row by id."""
    from app.modules.dms.domain.models import ArchivedDocument

    document = await db.get(ArchivedDocument, document_id)
    if document is None:
        raise NotFoundError("ArchivedDocument")
    return ArchivedDocumentResponse.model_validate(document)


__all__ = ["router"]
