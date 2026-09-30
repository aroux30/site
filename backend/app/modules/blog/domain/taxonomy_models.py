"""Custom taxonomies: user-defined classification systems (WordPress parity).

Beyond the built-in blog categories and tags, admins can create arbitrary
taxonomies (e.g. "brand", "region", "skill-level") and attach terms to posts.
Each taxonomy has its own set of hierarchical or flat terms.

Tables:
- custom_taxonomies: taxonomy definitions (name, slug, hierarchical)
- custom_taxonomy_terms: individual terms within a taxonomy
- blog_post_terms: many-to-many between posts and terms
"""

from __future__ import annotations

import enum
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class CustomTaxonomy(BaseModel):
    """A user-defined taxonomy (e.g. brand, color, skill-level)."""

    __tablename__ = "custom_taxonomies"
    __table_args__ = (
        Index("ix_custom_taxonomies_slug", "slug"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Hierarchical = categories-like (parent/child). Flat = tags-like.
    hierarchical: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

    # Relationships
    terms: Mapped[list["CustomTaxonomyTerm"]] = relationship(
        "CustomTaxonomyTerm",
        back_populates="taxonomy",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CustomTaxonomy(slug={self.slug})>"


class CustomTaxonomyTerm(BaseModel):
    """A term within a custom taxonomy."""

    __tablename__ = "custom_taxonomy_terms"
    __table_args__ = (
        UniqueConstraint("taxonomy_id", "slug", name="uq_custom_taxonomy_terms_tax_slug"),
        Index("ix_custom_taxonomy_terms_taxonomy_id", "taxonomy_id"),
        Index("ix_custom_taxonomy_terms_parent_id", "parent_id"),
        Index("ix_custom_taxonomy_terms_slug", "slug"),
    )

    taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_taxonomies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Hierarchical parent (NULL for top-level terms)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_taxonomy_terms.id", ondelete="CASCADE"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )

    # Relationships
    taxonomy: Mapped["CustomTaxonomy"] = relationship(
        "CustomTaxonomy", back_populates="terms"
    )

    def __repr__(self) -> str:
        return f"<CustomTaxonomyTerm(slug={self.slug}, taxonomy_id={self.taxonomy_id})>"


class BlogPostTerm(BaseModel):
    """Many-to-many between blog posts and custom taxonomy terms."""

    __tablename__ = "blog_post_terms"
    __table_args__ = (
        UniqueConstraint("post_id", "term_id", name="uq_blog_post_terms_post_term"),
        Index("ix_blog_post_terms_post_id", "post_id"),
        Index("ix_blog_post_terms_term_id", "term_id"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_taxonomy_terms.id", ondelete="CASCADE"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<BlogPostTerm(post_id={self.post_id}, term_id={self.term_id})>"
