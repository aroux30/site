"""SEO metadata domain models."""

import uuid
from typing import Any

from sqlalchemy import Boolean, Index, Integer, String, UniqueConstraint
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


class RedirectRule(BaseModel):
    """Admin-managed 301/302 redirect, evaluated by storefront middleware."""

    __tablename__ = "seo_redirects"
    __table_args__ = (
        UniqueConstraint("from_path", name="uq_seo_redirects_from_path"),
        Index("ix_seo_redirects_is_active", "is_active"),
    )

    from_path: Mapped[str] = mapped_column(String(500), nullable=False)
    to_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=301)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<RedirectRule({self.from_path} → {self.to_path}, {self.status_code})>"
