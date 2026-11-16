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
    Text,
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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    tokens: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    density_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int | None] = mapped_column(Integer, default=1, server_default=text("1"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    revisions: Mapped[list[ThemeRevision]] = relationship(
        "ThemeRevision",
        back_populates="theme",
        cascade="all, delete-orphan",
        order_by="ThemeRevision.created_at.desc()",
    )

    @property
    def author_id(self) -> uuid.UUID | None:
        return self.created_by

    @author_id.setter
    def author_id(self, val: uuid.UUID | None) -> None:
        self.created_by = val

    def __repr__(self) -> str:
        return f"<SiteTheme(slug={self.slug}, active={self.is_active})>"


class ThemeRevision(BaseModel):
    """Immutable snapshot of site theme tokens at a specific revision number."""

    __tablename__ = "theme_revisions"
    __table_args__ = (
        Index("ix_theme_revisions_theme_id", "theme_id"),
    )

    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_themes.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tokens: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    density_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    theme: Mapped[SiteTheme] = relationship("SiteTheme", back_populates="revisions")

    @property
    def revision_number(self) -> int:
        return self.version

    @revision_number.setter
    def revision_number(self, val: int) -> None:
        self.version = val

    def __repr__(self) -> str:
        return f"<ThemeRevision(theme_id={self.theme_id}, rev={self.version})>"
