"""SEO metadata domain models."""

import uuid
from typing import Any

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class SEOMetadata(BaseModel):
    """Per-resource SEO metadata and Open Graph tags."""

    __tablename__ = "seo_metadata"
    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "resource_id",
            name="uq_seo_metadata_resource",
        ),
        Index("ix_seo_metadata_resource_type", "resource_type"),
        Index(
            "ix_seo_metadata_resource_type_id",
            "resource_type",
            "resource_id",
        ),
    )

    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    og_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schema_markup: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<SEOMetadata(id={self.id}, resource_type={self.resource_type}, resource_id={self.resource_id})>"  # noqa: E501
