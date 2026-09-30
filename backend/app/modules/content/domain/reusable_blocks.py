"""Reusable blocks: named HTML fragments embedded by reference (WordPress parity).

A reusable block is content an editor writes once and embeds in many places —
WordPress's "synced pattern". Editing the block updates every page that
embeds it.

Embedding is by reference, not by copy: bodies carry a ``[block slug="…"]``
token and the render path expands it from this table at read time. That is
what makes an edit propagate — a copied fragment would freeze the old text
into every page that had already used it.

Only *published, active* blocks expand. A block that was deactivated or
trashed stays embedded as its raw token rather than vanishing silently, so a
missing block is visible in the output instead of leaving a hole.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ReusableBlockStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReusableBlock(BaseModel):
    """A named HTML fragment embeddable in pages and posts by slug."""

    __tablename__ = "reusable_blocks"
    __table_args__ = (
        Index("ix_reusable_blocks_slug", "slug"),
        Index("ix_reusable_blocks_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReusableBlockStatus] = mapped_column(
        Enum(
            ReusableBlockStatus,
            name="reusable_block_status_enum",
            native_enum=False,
        ),
        default=ReusableBlockStatus.DRAFT,
        nullable=False,
        server_default=text("'DRAFT'::character varying"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )
    # Soft delete, matching the trash semantics used across the CMS.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ReusableBlock(slug={self.slug}, status={self.status})>"
