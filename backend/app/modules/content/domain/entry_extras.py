"""Revision snapshots for dynamic content entries (parity with CmsPageRevision)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ContentEntryRevision(BaseModel):
    """Immutable snapshot of a content entry at a given revision number."""

    __tablename__ = "cms_content_entry_revisions"
    __table_args__ = (
        UniqueConstraint("entry_id", "revision_number", name="uq_entry_revisions_entry_rev"),
        Index("ix_entry_revisions_entry_id", "entry_id"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_content_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
