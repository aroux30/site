"""Post relationships: arbitrary links between posts (WordPress parity).

Allows defining typed relationships between any two blog posts:
- related (manual related posts override)
- translation (multi-language link)
- series (part 1, part 2, etc.)
- revision_of (for editorial forks)

Stored in a lightweight join table with a relationship type label.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class BlogPostRelationship(BaseModel):
    """Arbitrary typed relationship between two blog posts."""

    __tablename__ = "blog_post_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_post_id", "target_post_id", "relationship_type",
            name="uq_blog_post_rel_src_tgt_type",
        ),
        Index("ix_blog_post_rel_source", "source_post_id"),
        Index("ix_blog_post_rel_target", "target_post_id"),
        Index("ix_blog_post_rel_type", "relationship_type"),
    )

    source_post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="related"
    )

    def __repr__(self) -> str:
        return (
            f"<BlogPostRelationship("
            f"src={self.source_post_id}, tgt={self.target_post_id}, "
            f"type={self.relationship_type})>"
        )
