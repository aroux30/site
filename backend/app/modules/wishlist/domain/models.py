"""Wishlist domain models."""

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class Wishlist(BaseModel):
    """Named wishlist belonging to a user."""

    __tablename__ = "wishlists"
    __table_args__ = (Index("ix_wishlists_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), default="default", nullable=False)

    # Relationships
    items: Mapped[list["WishlistItem"]] = relationship(
        "WishlistItem",
        back_populates="wishlist",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Wishlist(id={self.id}, user_id={self.user_id}, name={self.name})>"


class WishlistItem(BaseModel):
    """Individual product saved to a wishlist."""

    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_items_wishlist_product"),
        Index("ix_wishlist_items_wishlist_id", "wishlist_id"),
        Index("ix_wishlist_items_product_id", "product_id"),
    )

    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    wishlist: Mapped["Wishlist"] = relationship("Wishlist", back_populates="items")

    def __repr__(self) -> str:
        return f"<WishlistItem(id={self.id}, wishlist_id={self.wishlist_id}, product_id={self.product_id})>"  # noqa: E501
