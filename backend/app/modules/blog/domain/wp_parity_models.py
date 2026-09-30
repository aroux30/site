"""WordPress P2 parity models: site options, meta tables, slug history.

These models cover the WordPress wp_options, wp_usermeta, wp_termmeta,
wp_commentmeta equivalents plus a slug history table for automatic
old-slug-to-new-slug redirects.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class SiteOption(BaseModel):
    """Global key-value settings (WordPress wp_options parity)."""

    __tablename__ = "site_options"
    __table_args__ = (
        Index("ix_site_options_option_key", "option_key"),
        Index("ix_site_options_autoload", "autoload"),
    )

    option_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    option_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    autoload: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

    def __repr__(self) -> str:
        return f"<SiteOption(key={self.option_key})>"


class UserMeta(BaseModel):
    """Per-user key-value metadata (WordPress wp_usermeta parity)."""

    __tablename__ = "user_meta"
    __table_args__ = (
        UniqueConstraint("user_id", "meta_key", name="uq_user_meta_user_key"),
        Index("ix_user_meta_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<UserMeta(user_id={self.user_id}, key={self.meta_key})>"


class BlogCommentMeta(BaseModel):
    """Per-comment key-value metadata (WordPress wp_commentmeta parity)."""

    __tablename__ = "blog_comment_meta"
    __table_args__ = (
        UniqueConstraint("comment_id", "meta_key", name="uq_blog_comment_meta_comment_key"),
        Index("ix_blog_comment_meta_comment_id", "comment_id"),
    )

    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BlogCommentMeta(comment_id={self.comment_id}, key={self.meta_key})>"


class BlogTermMeta(BaseModel):
    """Per-term key-value metadata (WordPress wp_termmeta parity)."""

    __tablename__ = "blog_term_meta"
    __table_args__ = (
        UniqueConstraint("term_type", "term_id", "meta_key", name="uq_blog_term_meta_term_key"),
        Index("ix_blog_term_meta_term", "term_type", "term_id"),
    )

    term_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "category" or "tag"
    term_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BlogTermMeta(type={self.term_type}, term={self.term_id}, key={self.meta_key})>"


class SlugHistory(BaseModel):
    """Tracks slug changes for automatic old-URL redirects."""

    __tablename__ = "slug_history"
    __table_args__ = (
        Index("ix_slug_history_old_slug", "old_slug"),
        Index("ix_slug_history_resource", "resource_type", "resource_id"),
    )

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "blog_post", "cms_page"
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    old_slug: Mapped[str] = mapped_column(String(550), nullable=False)
    new_slug: Mapped[str] = mapped_column(String(550), nullable=False)

    def __repr__(self) -> str:
        return f"<SlugHistory({self.old_slug} -> {self.new_slug})>"
