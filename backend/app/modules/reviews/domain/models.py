"""Product review and rating domain models."""

import enum
import uuid
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


# ---- Enums ----

class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---- Models ----

class Review(BaseModel):
    """Product reviews submitted by customers."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "user_id", name="uq_reviews_product_user"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        Index("ix_reviews_product_id", "product_id"),
        Index("ix_reviews_user_id", "user_id"),
        Index("ix_reviews_status", "status"),
        Index("ix_reviews_rating", "rating"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pros: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    cons: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    is_verified_purchase: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status_enum", native_enum=False),
        default=ReviewStatus.PENDING,
        nullable=False,
    )

    # Relationships
    votes: Mapped[list["ReviewVote"]] = relationship(
        "ReviewVote", back_populates="review", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, product_id={self.product_id}, rating={self.rating})>"


class ReviewVote(BaseModel):
    """Helpfulness votes on reviews."""

    __tablename__ = "review_votes"
    __table_args__ = (
        UniqueConstraint(
            "review_id", "user_id", name="uq_review_votes_review_user"
        ),
        Index("ix_review_votes_review_id", "review_id"),
        Index("ix_review_votes_user_id", "user_id"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="votes")

    def __repr__(self) -> str:
        return f"<ReviewVote(id={self.id}, review_id={self.review_id}, is_helpful={self.is_helpful})>"
