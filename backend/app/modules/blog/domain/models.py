"""Blog/CMS domain models."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class BlogPostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ---- Models ----


class BlogCategory(BaseModel):
    """Blog post categories."""

    __tablename__ = "blog_categories"
    __table_args__ = (Index("ix_blog_categories_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)

    # Relationships
    posts: Mapped[list["BlogPost"]] = relationship(
        "BlogPost", back_populates="category", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<BlogCategory(id={self.id}, slug={self.slug})>"


class BlogPost(BaseModel):
    """Blog articles for content marketing and SEO."""

    __tablename__ = "blog_posts"
    __table_args__ = (
        Index("ix_blog_posts_slug", "slug"),
        Index("ix_blog_posts_author_id", "author_id"),
        Index("ix_blog_posts_status", "status"),
        Index("ix_blog_posts_published_at", "published_at"),
        Index("ix_blog_posts_category_id", "category_id"),
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(550), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BlogPostStatus] = mapped_column(
        Enum(BlogPostStatus, name="blog_post_status_enum", native_enum=False),
        default=BlogPostStatus.DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    category: Mapped[Optional["BlogCategory"]] = relationship(
        "BlogCategory", back_populates="posts"
    )

    def __repr__(self) -> str:
        return f"<BlogPost(id={self.id}, slug={self.slug}, status={self.status})>"
