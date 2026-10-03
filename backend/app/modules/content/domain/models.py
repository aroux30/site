"""Content management, homepage blocks, tree menus, and FAQ domain models (Karta Phase 7/9).

Implements:
- HomepageBlock: Dynamic layout blocks reorderable from admin without code deploy (Karta blocks)
- SiteMenu: Multi-location nested hierarchical navigation tree (Karta menus & menu_types)
- FAQItem: Question & Answer catalog with structured Schema.org JSON-LD generation (Karta faqs)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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
    # Category IDs, banners, product tags
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

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

    # A plain slug, not the enum. The five built-ins are seeded, but an
    # operator can add a location from the panel (a campaign bar, a
    # landing-page nav), and an Enum column raises LookupError the moment a
    # row holds a value outside the five — so a custom location could be
    # written and then never read back. The DB column is varchar(32) with no
    # CHECK constraint, so nothing in the schema forced the enum either.
    location: Mapped[str] = mapped_column(
        String(32),
        default=MenuLocation.HEADER_MAIN.value,
        nullable=False,
        server_default=text("'header_main'::character varying"),
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_menus.id", ondelete="CASCADE"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

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
    category: Mapped[str] = mapped_column(
        String(100),
        default="عمومی",
        nullable=False,
        server_default=text("'عمومی'::character varying"),
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

    def __repr__(self) -> str:
        return f"<FAQItem(question={self.question[:40]}, category={self.category})>"


class PageStatus(str, enum.Enum):
    DRAFT = "draft"
    # Ready but not live. The blog has had this for posts; a page went straight
    # from draft to published, so there was nothing between writing and being
    # public.
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PageVisibility(str, enum.Enum):
    """Who may read a published page.

    Separate from ``PageStatus`` on purpose, and matching the posts: a page can
    be *published* and still *private*, which a status enum cannot express
    without a second "status" meaning two different things at once.
    """

    PUBLIC = "public"
    #: Published, but not listed and not served on the storefront.
    PRIVATE = "private"
    #: Published, but the body is withheld until the right password is given.
    PASSWORD = "password"


class CmsPage(BaseModel):
    """Editable storefront page with draft/publish workflow and revisions.

    Replaces the hardcoded admin/pages list. Public storefront routes still
    exist as Next.js files; this table is the source of truth for title, body,
    SEO, and publication state so editors can change copy without a deploy.
    """

    __tablename__ = "cms_pages"
    __table_args__ = (
        Index("ix_cms_pages_slug", "slug"),
        Index("ix_cms_pages_status", "status"),
        Index("ix_cms_pages_published_at", "published_at"),
        Index("ix_cms_pages_translation_group", "translation_group"),
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Content locale (Strapi i18n parity with blog_posts.locale). Slugs stay
    # globally unique, so a translation is a separate page row with its own slug.
    locale: Mapped[str] = mapped_column(
        String(10), default="fa", nullable=False, server_default=text("'fa'::character varying")
    )
    # i18n: pages that are translations of one another share a group UUID.
    # None = not translated.
    translation_group: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    status: Mapped[PageStatus] = mapped_column(
        Enum(PageStatus, name="cms_page_status_enum", native_enum=False),
        default=PageStatus.DRAFT,
        nullable=False,
        server_default=text("'DRAFT'::character varying"),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Whether readers may comment on this page. Default false, not true: a page
    # is a static document until its editor opts comments in, and turning them
    # on page-by-page is the only sane policy for a storefront (a legal page
    # should not accumulate threads).
    # Hero image for a storefront page. Posts had one; a page did not, so an
    # "about us" page had nowhere to put it.
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visibility: Mapped[PageVisibility] = mapped_column(
        Enum(PageVisibility, name="page_visibility_enum", native_enum=False),
        default=PageVisibility.PUBLIC,
        # The column stores member NAMES ("PUBLIC"), not values ("public"), so a
        # row written outside the ORM — raw SQL, a bulk insert, a restore — can
        # still be read back. A lowercase default here would pass every ORM test
        # and then raise LookupError on the first query that met such a row.
        server_default=text("'PUBLIC'::character varying"),
        nullable=False,
    )
    # Hashed, never plaintext: this column sits in the same row as the title,
    # and a ``SELECT *`` would otherwise hand out every page's secret.
    visibility_password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    allow_comments: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revision_number: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default=text("1")
    )
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_unpublish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Soft delete: trashed pages stay restorable until hard-deleted.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Hierarchical pages: parent-child nesting (WordPress parity)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_pages.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Manual ordering within the page list / parent
    menu_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    # Page template selection (e.g. "full-width", "sidebar", "landing")
    page_template: Mapped[str | None] = mapped_column(String(100), nullable=True)

    revisions: Mapped[list[CmsPageRevision]] = relationship(
        "CmsPageRevision",
        back_populates="page",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="CmsPageRevision.revision_number.desc()",
    )

    def __repr__(self) -> str:
        return f"<CmsPage(slug={self.slug}, status={self.status})>"


class CmsPageRevision(BaseModel):
    """Immutable snapshot of a CMS page at a given revision number."""

    __tablename__ = "cms_page_revisions"
    __table_args__ = (
        UniqueConstraint("page_id", "revision_number", name="uq_cms_page_revisions_page_rev"),
        Index("ix_cms_page_revisions_page_id", "page_id"),
    )

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    page: Mapped[CmsPage] = relationship("CmsPage", back_populates="revisions")

    def __repr__(self) -> str:
        return f"<CmsPageRevision(page_id={self.page_id}, rev={self.revision_number})>"
