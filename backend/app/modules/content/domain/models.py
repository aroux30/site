"""Content management, homepage blocks, tree menus, and FAQ domain models (Karta Phase 7/9).

Implements:
- HomepageBlock: Dynamic layout blocks reorderable from admin without code deploy (Karta blocks)
- SiteMenu: Multi-location nested hierarchical navigation tree (Karta menus & menu_types)
- FAQItem: Question & Answer catalog with structured Schema.org JSON-LD generation (Karta faqs)
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class BlockType(str, enum.Enum):
    SLIDER = "slider"
    CATEGORY_GRID = "category_grid"
    FEATURED_PRODUCTS = "featured_products"
    DISCOUNT_CAROUSEL = "discount_carousel"
    BANNER_GRID = "banner_grid"
    HTML_CUSTOM = "html_custom"


class MenuLocation(str, enum.Enum):
    HEADER_TOP = "header_top"
    HEADER_MAIN = "header_main"
    FOOTER_COL1 = "footer_col1"
    FOOTER_COL2 = "footer_col2"
    MOBILE_NAV = "mobile_nav"


class HomepageBlock(BaseModel):
    """Dynamic homepage section controllable from admin without code changes (Karta blocks)."""

    __tablename__ = "homepage_blocks"
    __table_args__ = (
        Index("ix_homepage_blocks_position", "position"),
        Index("ix_homepage_blocks_is_active", "is_active"),
    )

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    block_type: Mapped[BlockType] = mapped_column(
        Enum(BlockType, name="block_type_enum", native_enum=False),
        nullable=False,
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Category IDs, banners, product tags
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<HomepageBlock(title={self.title}, type={self.block_type}, pos={self.position})>"


class SiteMenu(BaseModel):
    """Multi-location tree navigation item with hierarchical parent-child nesting (Karta menus)."""

    __tablename__ = "site_menus"
    __table_args__ = (
        Index("ix_site_menus_location", "location"),
        Index("ix_site_menus_parent_id", "parent_id"),
        Index("ix_site_menus_position", "position"),
    )

    location: Mapped[MenuLocation] = mapped_column(
        Enum(MenuLocation, name="menu_location_enum", native_enum=False),
        default=MenuLocation.HEADER_MAIN,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_menus.id", ondelete="CASCADE"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<SiteMenu(title={self.title}, location={self.location}, pos={self.position})>"


class FAQItem(BaseModel):
    """Frequently Asked Questions with automated Google FAQPage JSON-LD generation (Karta faqs)."""

    __tablename__ = "faq_items"
    __table_args__ = (
        Index("ix_faq_items_category", "category"),
        Index("ix_faq_items_position", "position"),
        Index("ix_faq_items_is_active", "is_active"),
    )

    question: Mapped[str] = mapped_column(String(300), nullable=False)
    answer_html: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="عمومی", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<FAQItem(question={self.question[:40]}, category={self.category})>"
