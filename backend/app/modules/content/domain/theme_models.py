"""SiteTheme and ThemeRevision domain models for Design Tokens & Theme Management (Phase P2.0).

Supports:
- Design Tokens Community Group (DTCG) compliant token storage in PostgreSQL JSONB
- Atomic single-active-theme enforcement via partial unique index
- Theme versioning and revision history
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class SiteTheme(BaseModel):
    """Stores full site theme with design tokens in DTCG JSONB format."""

    __tablename__ = "site_themes"
    __table_args__ = (
        Index("ix_site_themes_is_active", "is_active"),
        Index("ix_site_themes_slug", "slug"),
        Index(
            "uq_site_themes_is_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    # DTCG design tokens payload: { "color": { "primary": { "$value": "#...", "$type": "color" } } }
    tokens: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    revisions: Mapped[list[ThemeRevision]] = relationship(
        "ThemeRevision",
        back_populates="theme",
        cascade="all, delete-orphan",
        order_by="ThemeRevision.revision_number.desc()",
    )

    def __repr__(self) -> str:
        return f"<SiteTheme(slug={self.slug}, active={self.is_active})>"


class ThemeRevision(BaseModel):
    """Immutable snapshot of a site theme tokens at a specific revision number."""

    __tablename__ = "theme_revisions"
    __table_args__ = (
        UniqueConstraint("theme_id", "revision_number", name="uq_theme_revisions_theme_rev"),
        Index("ix_theme_revisions_theme_id", "theme_id"),
    )

    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_themes.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    tokens: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    theme: Mapped[SiteTheme] = relationship("SiteTheme", back_populates="revisions")

    def __repr__(self) -> str:
        return f"<ThemeRevision(theme_id={self.theme_id}, rev={self.revision_number})>"
