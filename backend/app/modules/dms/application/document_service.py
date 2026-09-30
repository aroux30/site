"""Document-management service: attachments and the fiscal archive index.

Two responsibilities with different rules, deliberately kept side by side so
the difference is visible:

* **Attachments are working documents.** Upload, rename, delete — normal
  record hygiene.
* **Archives are evidence.** Registered once, never updated, never deleted
  through the API. A supersede marks the old row and adds a new one; the
  history stays readable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.dms.domain.models import (
    ATTACHABLE_ENTITY_TYPES,
    ArchivedDocument,
    ArchivedDocumentKind,
    Attachment,
    AttachmentKind,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Upload cap, mirrored from the media store's own limit so a rejected upload
#: fails here with a clear message rather than deep in the storage layer.
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def validate_entity_type(entity_type: str) -> str:
    """Normalise and validate an attachable entity type. Pure."""
    normalised = (entity_type or "").strip().lower()
    if normalised not in ATTACHABLE_ENTITY_TYPES:
        raise ValidationError(
            f"نوع موجودیت «{entity_type}» برای پیوست پشتیبانی نمی‌شود",
            error_code="UNSUPPORTED_ENTITY_TYPE",
        )
    return normalised


def validate_attachment_meta(
    *, file_name: str, file_url: str, file_size: int
) -> None:
    """Reject an attachment row that could not be served or is oversized. Pure.

    The URL check is deliberately narrow: only store-relative paths are
    accepted. An absolute URL or a traversal sequence in a stored value is
    how an attachment table becomes an SSRF or path-traversal gadget later.
    """
    if not (file_name or "").strip():
        raise ValidationError("نام فایل الزامی است", error_code="FILE_NAME_REQUIRED")
    if not (file_url or "").strip():
        raise ValidationError("آدرس فایل الزامی است", error_code="FILE_URL_REQUIRED")
    url = file_url.strip()
    if "://" in url or url.startswith("//"):
        raise ValidationError(
            "آدرس فایل باید مسیر نسبی فروشگاه باشد، نه آدرس کامل",
            error_code="ABSOLUTE_URL_NOT_ALLOWED",
        )
    if ".." in url.replace("\\", "/").split("/"):
        raise ValidationError(
            "مسیر فایل نامعتبر است", error_code="INVALID_FILE_PATH"
        )
    if file_size < 0:
        raise ValidationError(
            "حجم فایل نامعتبر است", error_code="INVALID_FILE_SIZE"
        )
    if file_size > MAX_ATTACHMENT_BYTES:
        raise ValidationError(
            f"حجم فایل بیش از حد مجاز ({MAX_ATTACHMENT_BYTES // (1024 * 1024)} مگابایت) است",
            error_code="FILE_TOO_LARGE",
        )


# ── Attachments ─────────────────────────────────────────────────────────────


async def create_attachment(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    file_name: str,
    file_url: str,
    file_size: int,
    content_type: str | None = None,
    kind: AttachmentKind = AttachmentKind.GENERAL,
    title: str | None = None,
    notes: str | None = None,
    uploaded_by_id: uuid.UUID | None = None,
) -> Attachment:
    """Attach a stored file to a business record."""
    clean_type = validate_entity_type(entity_type)
    validate_attachment_meta(
        file_name=file_name, file_url=file_url, file_size=file_size
    )

    attachment = Attachment(
        entity_type=clean_type,
        entity_id=entity_id,
        kind=kind,
        file_name=file_name.strip(),
        file_url=file_url.strip(),
        file_size=file_size,
        content_type=content_type,
        title=title,
        notes=notes,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(attachment)
    await db.flush()
    await logger.ainfo(
        "attachment_created",
        attachment_id=str(attachment.id),
        entity_type=clean_type,
        entity_id=str(entity_id),
        kind=kind.value,
    )
    return attachment


async def list_attachments(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    kind: AttachmentKind | None = None,
) -> list[Attachment]:
    """Attachments on one record, newest first."""
    clean_type = validate_entity_type(entity_type)
    stmt = (
        select(Attachment)
        .where(
            Attachment.entity_type == clean_type,
            Attachment.entity_id == entity_id,
        )
        .order_by(Attachment.created_at.desc())
    )
    if kind is not None:
        stmt = stmt.where(Attachment.kind == kind)
    return list((await db.execute(stmt)).scalars().all())


async def get_attachment(db: AsyncSession, *, attachment_id: uuid.UUID) -> Attachment:
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise NotFoundError("Attachment")
    return attachment


async def delete_attachment(
    db: AsyncSession, *, attachment_id: uuid.UUID
) -> Attachment:
    """Remove an attachment row.

    Only the row: deleting the underlying file is the media module's call,
    because the same file may be referenced by another record and an
    attachment delete must not silently break a second reference.
    """
    attachment = await get_attachment(db, attachment_id=attachment_id)
    await db.delete(attachment)
    await db.flush()
    await logger.ainfo("attachment_deleted", attachment_id=str(attachment_id))
    return attachment


async def count_attachments_by_kind(
    db: AsyncSession, *, entity_type: str, entity_id: uuid.UUID
) -> dict[str, int]:
    """Per-kind counts for one record — drives the "3 files" badges. Pure-ish."""
    clean_type = validate_entity_type(entity_type)
    rows = (
        await db.execute(
            select(Attachment.kind, func.count())
            .where(
                Attachment.entity_type == clean_type,
                Attachment.entity_id == entity_id,
            )
            .group_by(Attachment.kind)
        )
    ).all()
    return {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
        for row in rows
    }


# ── Fiscal archive ──────────────────────────────────────────────────────────


async def archive_document(
    db: AsyncSession,
    *,
    kind: ArchivedDocumentKind,
    document_key: str,
    entity_type: str,
    entity_id: uuid.UUID,
    archive_path: str,
    content_type: str = "text/html",
    file_size: int | None = None,
    content_hash: str | None = None,
    fiscal_period: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> ArchivedDocument:
    """Register a frozen document in the archive index.

    Idempotent on (kind, document_key): archiving the same invoice number
    twice returns the existing row rather than raising — a retried backfill
    must not fail, and a duplicate must not overwrite evidence.
    """
    key = (document_key or "").strip()
    if not key:
        raise ValidationError(
            "شناسه سند الزامی است", error_code="DOCUMENT_KEY_REQUIRED"
        )
    clean_type = validate_entity_type(entity_type)

    existing = await get_archived_by_key(db, kind=kind, document_key=key)
    if existing is not None:
        return existing

    document = ArchivedDocument(
        kind=kind,
        document_key=key,
        entity_type=clean_type,
        entity_id=entity_id,
        archive_path=archive_path.strip(),
        content_type=content_type,
        file_size=file_size,
        content_hash=content_hash,
        fiscal_period=fiscal_period,
        metadata_json=metadata_json,
        is_superseded=False,
    )
    db.add(document)
    await db.flush()
    await logger.ainfo(
        "document_archived",
        document_id=str(document.id),
        kind=kind.value,
        document_key=key,
        fiscal_period=fiscal_period,
    )
    return document


async def get_archived_by_key(
    db: AsyncSession,
    *,
    kind: ArchivedDocumentKind,
    document_key: str,
) -> ArchivedDocument | None:
    """Look one archived document up by its business key."""
    return (
        await db.execute(
            select(ArchivedDocument).where(
                ArchivedDocument.kind == kind,
                ArchivedDocument.document_key == document_key.strip(),
            )
        )
    ).scalar_one_or_none()


async def supersede_document(
    db: AsyncSession,
    *,
    old_document_id: uuid.UUID,
    kind: ArchivedDocumentKind,
    document_key: str,
    entity_type: str,
    entity_id: uuid.UUID,
    archive_path: str,
    content_type: str = "text/html",
    file_size: int | None = None,
    content_hash: str | None = None,
    fiscal_period: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> tuple[ArchivedDocument, ArchivedDocument]:
    """Replace an archived document, keeping the superseded row.

    Returns ``(old, new)``. The old row is marked, never deleted: an auditor
    asking "what did this invoice say before it was corrected" gets an answer.
    """
    old = await db.get(ArchivedDocument, old_document_id)
    if old is None:
        raise NotFoundError("ArchivedDocument")
    if old.is_superseded:
        raise ConflictError(
            "این سند قبلاً جایگزین شده است", error_code="ALREADY_SUPERSEDED"
        )

    old.is_superseded = True
    new_document = await archive_document(
        db,
        kind=kind,
        document_key=document_key,
        entity_type=entity_type,
        entity_id=entity_id,
        archive_path=archive_path,
        content_type=content_type,
        file_size=file_size,
        content_hash=content_hash,
        fiscal_period=fiscal_period,
        metadata_json=metadata_json,
    )
    await db.flush()
    await logger.ainfo(
        "document_superseded",
        old_id=str(old_document_id),
        new_id=str(new_document.id),
        document_key=document_key,
    )
    return old, new_document


async def list_archived_documents(
    db: AsyncSession,
    *,
    kind: ArchivedDocumentKind | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    fiscal_period: str | None = None,
    document_key: str | None = None,
    include_superseded: bool = False,
    limit: int = 100,
) -> list[ArchivedDocument]:
    """Search the archive index, newest first."""
    stmt = (
        select(ArchivedDocument)
        .order_by(ArchivedDocument.created_at.desc())
        .limit(limit)
    )
    if kind is not None:
        stmt = stmt.where(ArchivedDocument.kind == kind)
    if entity_type:
        stmt = stmt.where(
            ArchivedDocument.entity_type == validate_entity_type(entity_type)
        )
    if entity_id:
        stmt = stmt.where(ArchivedDocument.entity_id == entity_id)
    if fiscal_period:
        stmt = stmt.where(ArchivedDocument.fiscal_period == fiscal_period.strip())
    if document_key:
        stmt = stmt.where(ArchivedDocument.document_key == document_key.strip())
    if not include_superseded:
        stmt = stmt.where(ArchivedDocument.is_superseded.is_(False))
    return list((await db.execute(stmt)).scalars().all())


def archive_summary(documents: list[ArchivedDocument]) -> dict[str, int]:
    """Counts by kind for the archive landing page. Pure."""
    summary: dict[str, int] = {}
    for doc in documents:
        key = doc.kind.value if hasattr(doc.kind, "value") else str(doc.kind)
        summary[key] = summary.get(key, 0) + 1
    return summary


def utcnow() -> datetime:
    """Timestamp helper, kept here so tests can freeze it in one place."""
    return datetime.now(UTC)
