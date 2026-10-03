"""Custom post types: user-defined content types beyond blog posts (WordPress parity).

Allows admins to register new content types (portfolio, testimonial, event, etc.)
with configurable fields. Each custom post type gets its own slug namespace,
field schema, and CRUD operations through a unified API.

The design uses a single flexible table with a JSONB `fields` column,
so new post types don't require schema migrations.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class CustomPostTypeStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CustomPostType(BaseModel):
    """A registered custom post type definition (e.g. portfolio, testimonial, event).

    Defines the content type's metadata and field schema. The field_schema is
    a JSON array describing the expected fields, used for admin UI rendering
    and validation:

        [
            {"key": "company", "label": "Company", "type": "text", "required": true},
            {"key": "rating", "label": "Rating", "type": "number", "min": 1, "max": 5},
            {"key": "logo", "label": "Logo", "type": "image"},
        ]
    """

    __tablename__ = "custom_post_types"
    __table_args__ = (
        Index("ix_custom_post_types_slug", "slug"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Icon name for admin sidebar (e.g. "briefcase", "star", "calendar")
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # JSON schema of custom fields
    field_schema: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    # Whether this post type supports categories, tags, comments, revisions
    supports_categories: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    supports_comments: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

    # Relationships
    entries: Mapped[list["CustomPostEntry"]] = relationship(
        "CustomPostEntry",
        back_populates="post_type",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CustomPostType(slug={self.slug})>"


class CustomPostEntry(BaseModel):
    """An instance of a custom post type (e.g. one portfolio item, one testimonial)."""

    __tablename__ = "custom_post_entries"
    __table_args__ = (
        UniqueConstraint("post_type_id", "slug", name="uq_custom_post_entries_type_slug"),
        Index("ix_custom_post_entries_post_type_id", "post_type_id"),
        Index("ix_custom_post_entries_slug", "slug"),
        Index("ix_custom_post_entries_status", "status"),
        Index("ix_custom_post_entries_published_at", "published_at"),
    )

    post_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_post_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(550), nullable=False)
    # Flexible content fields stored as JSON
    fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[CustomPostTypeStatus] = mapped_column(
        Enum(CustomPostTypeStatus, name="custom_post_type_status_enum", native_enum=False),
        default=CustomPostTypeStatus.DRAFT,
        nullable=False,
        server_default=text("'DRAFT'::character varying"),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When set and in `draft`, the beat task moves this row to `published` once
    # the time passes. Without it an entry could be dated forward but never
    # went live by itself.
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: How many revisions exist. Kept as a column rather than counted on
    #: every write, so deciding whether to snapshot is one cheap read instead of
    #: an aggregate, and so the UI can show "12 versions" without asking.
    revision_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )

    # Relationships
    post_type: Mapped["CustomPostType"] = relationship(
        "CustomPostType", back_populates="entries"
    )

    def __repr__(self) -> str:
        return f"<CustomPostEntry(slug={self.slug}, type_id={self.post_type_id})>"


class CustomPostEntryRevision(BaseModel):
    """One saved state of a custom post type entry.

    The same role `ContentEntryRevision` plays for the other content-entry
    system: an editor who overwrites a whole entry with the wrong field values
    needs a way back, and the fields are free-form JSON, so there is nothing to
    diff against — only the previous state to keep.

    Named `custom_post_entry_revisions` rather than anything longer: the
    `fk_` naming convention interpolates the table name, and at 63 characters
    the constraint name stops being something Postgres accepts.
    """

    __tablename__ = "custom_post_entry_revisions"
    __table_args__ = (
        Index("ix_custom_post_entry_revisions_entry", "entry_id"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_post_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: Whole-field snapshot. Deliberately not a diff: the fields are operator-
    #: defined JSON with no stable schema, so a delta cannot be applied back
    #: without one.
    fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: Monotonic per entry. Restoring by number rather than by id is what the
    #: UI offers the operator, and it is what "revision 3" means to them.
    revision_number: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default=text("1")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    entry: Mapped["CustomPostEntry"] = relationship("CustomPostEntry")

    def __repr__(self) -> str:
        return (
            f"<CustomPostEntryRevision(entry_id={self.entry_id}, "
            f"n={self.revision_number})>"
        )
