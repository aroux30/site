"""Generic key-value custom fields for CMS content (WordPress postmeta parity).

Pages had no meta table at all, so an editor could not attach a field to a page
without a schema change. This table is deliberately generic — ``resource_type``
plus ``resource_id`` — so pages, reusable blocks and any future content type
share one access path instead of each growing its own meta table.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ContentMeta(BaseModel):
    """One custom field on a content resource."""

    __tablename__ = "content_meta"
    __table_args__ = (
        UniqueConstraint(
            "resource_type", "resource_id", "meta_key",
            name="uq_content_meta_resource_key",
        ),
        Index("ix_content_meta_resource", "resource_type", "resource_id"),
        Index("ix_content_meta_meta_key", "meta_key"),
    )

    # Deliberately not a foreign key: a generic table is shared by several
    # resource types, and a FK would force one owner type per table.
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ContentMeta(type={self.resource_type}, id={self.resource_id}, "
            f"key={self.meta_key})>"
        )
