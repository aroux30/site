"""Dynamic content-type builder (Strapi Content-Type Builder parity).

``ContentType`` stores a user-defined schema (list of typed fields, including
repeatable components and relations to other content types); ``ContentEntry``
stores rows of that type as JSONB. Validation runs against the field
definitions on every write, so an entry can never drift from its type.
"""

from __future__ import annotations

import enum
import re
import uuid
from typing import Any

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel
from app.modules.content.domain.models import PageStatus

FIELD_TYPES: frozenset[str] = frozenset(
    {
        "string", "text", "richtext", "integer", "decimal", "boolean",
        "date", "datetime", "email", "url", "slug", "enum",
        "media",       # media asset UUID
        "relation",    # → entry of another content type
        "component",   # embedded object per its own field list
    }
)

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,100}$")


class ContentTypeKind(str, enum.Enum):
    COLLECTION = "collection"   # many entries (Strapi collection type)
    SINGLE = "single"           # exactly one entry (Strapi single type)


class ContentType(BaseModel):
    """A user-defined content schema."""

    __tablename__ = "cms_content_types"

    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kind: Mapped[ContentTypeKind] = mapped_column(
        Enum(ContentTypeKind, name="cms_content_type_kind_enum", native_enum=False),
        default=ContentTypeKind.COLLECTION,
        nullable=False,
        server_default=text("'COLLECTION'::character varying"),
    )
    # [{name, type, required?, fields? (component), target? (relation),
    #   multiple?, options? (enum), default?}]
    fields: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

    entries: Mapped[list[ContentEntry]] = relationship(
        "ContentEntry", back_populates="content_type", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ContentType(slug={self.slug}, kind={self.kind})>"


class ContentEntry(BaseModel):
    """One row of a dynamic content type; ``data`` validates against the type."""

    __tablename__ = "cms_content_entries"
    __table_args__ = (
        Index("ix_cms_content_entries_type_status", "content_type_id", "status"),
        Index("ix_cms_content_entries_locale", "locale"),
    )

    content_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_content_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[PageStatus] = mapped_column(
        Enum(PageStatus, name="cms_page_status_enum", native_enum=False),
        default=PageStatus.DRAFT,
        nullable=False,
        server_default=text("'DRAFT'::character varying"),
    )
    locale: Mapped[str] = mapped_column(
        String(10), default="fa", nullable=False, server_default=text("'fa'::character varying")
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    revision_number: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default=text("1")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_unpublish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    content_type: Mapped[ContentType] = relationship("ContentType", back_populates="entries")

    def __repr__(self) -> str:
        return f"<ContentEntry(type={self.content_type_id}, status={self.status})>"
