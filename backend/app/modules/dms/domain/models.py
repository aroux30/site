"""Document management: polymorphic attachments and the fiscal archive.

ERP benchmark gap analysis (feature #25 Document management, P2). The media
module is an image-oriented asset manager and ``TicketAttachment`` is bound to
one message; neither answers "attach this PO/invoice/return document to any
business record" or "archive posted fiscal documents".

Design notes
------------
* **Polymorphic by (entity_type, entity_id), not by FK.** A generic
  attachment table cannot hold a real FK per target without a join table per
  entity. The pair is indexed and validated against a registry of attachable
  types, so a typo'd entity name is refused at the API rather than producing
  an orphan row nobody can see.
* **Two distinct tables on purpose.** ``Attachment`` is a *working* document
  a user uploads and can delete; ``ArchivedDocument`` is an *immutable*
  record (a posted invoice's frozen HTML) that must never be deleted or
  overwritten — merging them would put a delete button next to fiscal
  evidence.
* **Storage is by reference.** Files live in the media store; these rows hold
  the URL plus the metadata the UI needs. Nothing here writes bytes.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    pass


#: Entity types an attachment may hang off. Kept as data (not an FK) so the
#: API can reject an unknown target with a clear message, and so adding a
#: type is a one-line change rather than a migration.
ATTACHABLE_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "order",
        "return",
        "purchase_order",
        "vendor_settlement",
        "invoice",
        "receipt",
        "vendor",
        "supplier",
        "product",
        "customer",
    }
)


class AttachmentKind(str, enum.Enum):
    """What the document is — drives UI grouping and icon choice."""

    GENERAL = "general"
    CONTRACT = "contract"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    SHIPPING_LABEL = "shipping_label"
    INSPECTION = "inspection"
    RETURN_FORM = "return_form"
    OTHER = "other"


class Attachment(BaseModel):
    """A working document attached to any business record."""

    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_entity", "entity_type", "entity_id"),
        Index("ix_attachments_kind", "kind"),
        Index("ix_attachments_uploaded_by", "uploaded_by_id"),
        CheckConstraint(
            "entity_type <> ''",
            name="ck_attachments_entity_type_not_empty",
        ),
    )

    #: Target record. Deliberately not a FK: see the module docstring.
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    kind: Mapped[AttachmentKind] = mapped_column(
        Enum(AttachmentKind, name="attachment_kind_enum", native_enum=False),
        default=AttachmentKind.GENERAL,
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Where the media store serves it from (relative URL, not a filesystem
    #: path — the two are different namespaces and confusing them is how
    #: path-traversal bugs are born).
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Attachment(id={self.id}, {self.entity_type}/{self.entity_id}, "
            f"file={self.file_name!r})>"
        )


class ArchivedDocumentKind(str, enum.Enum):
    """Kinds of immutable archived documents."""

    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    RECEIPT = "receipt"
    SETTLEMENT = "settlement"
    OTHER = "other"


class ArchivedDocument(BaseModel):
    """An immutable archived document — fiscal evidence, never deleted.

    The invoicing module already freezes a posted invoice's rendered HTML and
    stores its path on the invoice row. This table is the *index* over such
    artifacts across modules: one place an auditor (or a support agent in a
    dispute) can search without knowing which module produced the file.

    There is no delete endpoint for this table by design. A retention policy
    may purge rows older than the legal window, but that is an operator
    action, not an API one.
    """

    __tablename__ = "archived_documents"
    __table_args__ = (
        Index("ix_archived_documents_entity", "entity_type", "entity_id"),
        Index("ix_archived_documents_kind", "kind"),
        Index("ix_archived_documents_document_key", "document_key"),
        UniqueConstraint(
            "kind",
            "document_key",
            name="uq_archived_documents_kind_key",
        ),
        CheckConstraint(
            "entity_type <> ''",
            name="ck_archived_documents_entity_type_not_empty",
        ),
    )

    kind: Mapped[ArchivedDocumentKind] = mapped_column(
        Enum(ArchivedDocumentKind, name="archived_document_kind_enum", native_enum=False),
        nullable=False,
    )
    #: Stable business key of the document — an invoice number, a credit-note
    #: number. Unique per kind: two archived invoices may not claim number
    #: INV-1404-000123, or the chain-verify story falls apart.
    document_key: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    #: Path/URL of the frozen artifact (HTML snapshot today, PDF when a
    #: renderer is configured).
    archive_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="text/html"
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: Tamper-evidence hook: the hash the producing module computed over the
    #: artifact at freeze time. Not recomputed here — this table records it,
    #: the producing module owns it.
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    #: Jalali fiscal period ("1404"), so an archive search can be scoped to a
    #: year the way an Iranian auditor actually thinks.
    fiscal_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: True when this artifact replaced an earlier one (a corrected invoice).
    #: The superseded row stays — evidence of the correction, not just its
    #: outcome.
    is_superseded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    def __repr__(self) -> str:
        return (
            f"<ArchivedDocument(id={self.id}, kind={self.kind.value}, "
            f"key={self.document_key!r})>"
        )
