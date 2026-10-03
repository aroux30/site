"""Pydantic v2 schemas for Content Management, Blocks, Menus, and FAQs (Karta Phase 7/9)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.domain.models import (
    BlockType,
    MenuLocation,
    PageStatus,
    PageVisibility,
)

from app.modules.content.domain.reusable_blocks import ReusableBlockStatus

# ── Homepage Block Schemas ────────────────────────────────────────────────


class HomepageBlockCreateRequest(BaseModel):
    """Admin payload to configure a homepage section."""

    title: str = Field(..., min_length=1, max_length=150)
    block_type: BlockType
    config: dict[str, Any] | None = None
    position: int = 0


class HomepageBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    block_type: BlockType
    config: dict[str, Any] | None = None
    position: int
    is_active: bool
    created_at: datetime


class BlockReorderRequest(BaseModel):
    """Admin payload to update display ordering of multiple blocks."""

    positions: dict[uuid.UUID, int] = Field(
        ...,
        description="Mapping of block_id to new integer position",
    )


# ── Tree Menu Schemas ─────────────────────────────────────────────────────


#: A menu location identifier. The five built-ins are seeded; an operator can
#: add more (a campaign bar, a landing-page nav) without a deploy, so this is a
#: slug rather than the enum. The column is varchar(32) and carries no CHECK
#: constraint, so the only requirement is that the value fits and is a slug —
#: it becomes a CSS selector and a layout slot name.
MENU_LOCATION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


def validate_menu_location(value: str) -> str:
    """Normalise and check a menu location id, raising a 422 on a bad one."""
    clean = (value or "").strip().lower()
    if not MENU_LOCATION_RE.match(clean):
        raise ValueError(
            "مکان منو باید با حرف/عدد شروع شود و فقط a-z، 0-9، _ و - داشته "
            "باشد (حداکثر ۳۲ نویسه)."
        )
    return clean


class MenuItemCreateRequest(BaseModel):
    """Admin payload to add a navigation link."""

    # `str`, not the enum: an operator can add a location from the panel, and
    # pinning this to the five seeded values is what made "add a menu location"
    # impossible. Validated by the route, which knows the seeded set too.
    location: str = Field("header_main", min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=500)
    parent_id: uuid.UUID | None = None
    position: int = 0
    icon: str | None = Field(None, max_length=50)


class MenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location: str
    title: str
    url: str
    parent_id: uuid.UUID | None = None
    position: int
    icon: str | None = None
    is_active: bool


class TreeMenuItemNode(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    location: str
    position: int
    icon: str | None = None
    children: list[TreeMenuItemNode] = Field(default_factory=list)


# ── FAQ Schemas & Google Schema.org ───────────────────────────────────────


class FAQItemCreateRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)
    answer_html: str = Field(..., min_length=1)
    category: str = Field("عمومی", max_length=100)
    position: int = 0


class FAQItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer_html: str
    category: str
    position: int
    is_active: bool


class FAQListWithGoogleSchemaResponse(BaseModel):
    items: list[FAQItemResponse]
    total: int
    schema_json_ld: dict[str, Any] = Field(
        ...,
        description="Valid Schema.org FAQPage JSON-LD for Google Rich Snippets",
    )


# ── CMS Pages (draft / publish / revisions) ─────────────────────────────────


class CmsPageCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    slug: str | None = Field(None, min_length=1, max_length=220)
    body_html: str = ""
    excerpt: str | None = Field(None, max_length=1000)
    status: PageStatus = PageStatus.DRAFT
    cover_image_url: str | None = Field(None, max_length=500)
    visibility: PageVisibility = PageVisibility.PUBLIC
    # Plaintext in, hash stored. The service hashes it and never echoes it back,
    # so a form that re-opens cannot show the existing value — which is why the
    # API returns "" rather than the stored hash.
    visibility_password: str | None = Field(None, max_length=255)
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None
    locale: str = Field("fa", min_length=2, max_length=10)
    # Hierarchical pages. The column and the FK have existed since the
    # WordPress-parity migration, but no schema carried them, so the tree could
    # not be built at all — and the breadcrumb's ancestor walk was provably
    # dead code because `parent_id` was always NULL.
    parent_id: uuid.UUID | None = None
    # Manual ordering among siblings. The column existed with no schema field,
    # so `model_dump(exclude_unset=True)` never carried it and sibling order
    # was whatever insertion order produced. Lower sorts first; ties fall back
    # to the title.
    menu_order: int = Field(0, ge=-100_000, le=100_000)
    # Whether readers may comment on this page. Off by default: a page is a
    # static document until its editor opts in.
    allow_comments: bool = False


class CmsPageUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    slug: str | None = Field(None, min_length=1, max_length=220)
    body_html: str | None = None
    excerpt: str | None = Field(None, max_length=1000)
    status: PageStatus | None = None
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None
    # Editable after creation (WordPress/Strapi parity): the admin dialog sends
    # it on PATCH; without this field Pydantic silently dropped the change.
    locale: str | None = Field(None, min_length=2, max_length=10)
    parent_id: uuid.UUID | None = None
    # Sibling ordering, editable after creation like the parent.
    menu_order: int | None = Field(None, ge=-100_000, le=100_000)
    cover_image_url: str | None = Field(None, max_length=500)
    visibility: PageVisibility | None = None
    # Empty string means "unchanged", not "clear": the stored hash never comes
    # back to the client, so a pre-filled field would be blank, and treating
    # blank as clear would silently unlock the page on any unrelated save.
    # Clearing protection is switching visibility away from "password".
    visibility_password: str | None = Field(None, max_length=255)
    # Opt a page into (or out of) comments. Carried here because the column is
    # server-owned truth: without it in the update schema, the admin toggle
    # would send the field and Pydantic would drop it silently.
    allow_comments: bool | None = None


class CmsPageRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    revision_number: int
    title: str
    slug: str
    status: str
    created_at: datetime


class CmsPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    body_html: str
    excerpt: str | None = None
    status: PageStatus
    published_at: datetime | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    author_id: uuid.UUID | None = None
    revision_number: int
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None
    locale: str = "fa"
    # i18n: pages sharing a group are translations of one another (None = not
    # translated). The storefront language switcher groups on this.
    translation_group: uuid.UUID | None = None
    # Soft-delete marker: the admin table hides the restore/permanent-delete
    # controls without this — the rows were indistinguishable from live pages.
    deleted_at: datetime | None = None
    # Hierarchical pages: the parent link the admin editor sets and the
    # storefront breadcrumb walks. Null for a top-level page.
    parent_id: uuid.UUID | None = None
    # Whether readers may comment. The storefront reads this to decide whether
    # to render a thread at all, so it has to be on the public response.
    allow_comments: bool = False
    # Manual ordering among siblings.
    menu_order: int = 0
    cover_image_url: str | None = None
    visibility: PageVisibility = PageVisibility.PUBLIC
    # Never the hash. Present so the editor can tell "this page is password
    # protected" without a second request.
    visibility_password_set: bool = False
    created_at: datetime
    updated_at: datetime


class CmsPageListResponse(BaseModel):
    items: list[CmsPageResponse]
    total: int


class CmsPagePaginatedResponse(BaseModel):
    """Paginated CMS page list (Strapi-style: items + total/page/page_size)."""

    items: list[CmsPageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Shared-content bulk operations & duplication (Strapi/WordPress parity) ──


class BulkActionRequest(BaseModel):
    """Admin payload for a bulk operation over a set of ids."""

    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)


class BulkActionResult(BaseModel):
    succeeded: int
    failed: int
    errors: dict[str, str] = Field(default_factory=dict)


# ── Single Types (Strapi-style singleton configs) ───────────────────────────


class SingleTypeResponse(BaseModel):
    """A named singleton config document backed by the settings store."""

    key: str
    value: dict[str, Any] | None = None
    updated_at: datetime | None = None


class SingleTypeUpdateRequest(BaseModel):
    """Replace a singleton's value (validated per-key on write)."""

    value: dict[str, Any] = Field(default_factory=dict)


# ── Partial updates for blocks / menus / FAQs ───────────────────────────────


class HomepageBlockUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=150)
    config: dict[str, Any] | None = None
    position: int | None = None
    is_active: bool | None = None


class MenuItemUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    url: str | None = Field(None, min_length=1, max_length=500)
    position: int | None = None
    icon: str | None = Field(None, max_length=50)
    is_active: bool | None = None


class FAQItemUpdateRequest(BaseModel):
    question: str | None = Field(None, min_length=1, max_length=300)
    answer_html: str | None = None
    category: str | None = Field(None, max_length=100)
    position: int | None = None
    is_active: bool | None = None


# ── Reusable blocks (WordPress "synced patterns") ───────────────────────────


class ReusableBlockCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    body_html: str = ""
    slug: str | None = Field(None, max_length=220)
    description: str | None = Field(None, max_length=500)
    status: ReusableBlockStatus = ReusableBlockStatus.DRAFT


class ReusableBlockUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    body_html: str | None = None
    description: str | None = Field(None, max_length=500)
    status: ReusableBlockStatus | None = None
    is_active: bool | None = None


class ReusableBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    body_html: str
    description: str | None = None
    status: ReusableBlockStatus
    is_active: bool
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PublicPageSummary(BaseModel):
    """Minimal published-page row for public discovery surfaces (sitemap).

    Deliberately carries no ``body_html``, ``seo_*`` or author fields: this
    route is unauthenticated, so it must expose only what a crawler needs —
    the address and when it last changed.
    """

    model_config = ConfigDict(from_attributes=True)

    slug: str
    locale: str = "fa"
    updated_at: datetime
    published_at: datetime | None = None


class PublicPageSummaryList(BaseModel):
    items: list[PublicPageSummary]
    total: int


# ── Block Patterns (code-registered, WordPress parity) ───────────────────


class BlockPatternVariable(BaseModel):
    """One editable slot of a pattern with its editor label and fallback."""

    name: str
    label: str
    default: str = ""


class BlockPatternSummary(BaseModel):
    slug: str
    title: str
    description: str
    category: str
    keywords: list[str] = []
    variables: list[BlockPatternVariable] = []


class BlockPatternCategoryGroup(BaseModel):
    category: str
    patterns: list[BlockPatternSummary]


class BlockPatternRenderRequest(BaseModel):
    """Variable values to substitute into a pattern's ``{{slots}}``."""

    variables: dict[str, str] = Field(default_factory=dict)


class BlockPatternRenderResponse(BaseModel):
    slug: str
    html: str
    applied_variables: list[str] = []


# ── CMS page revision diff ─────────────────────────────────────────────────


class RevisionRef(BaseModel):
    """Which revision one side of a diff is."""

    revision_number: int
    created_at: datetime | None = None
    title: str = ""


class RevisionFieldDiff(BaseModel):
    """One compared field: raw values plus whether they differ."""

    field: str
    changed: bool
    before: str | None = None
    after: str | None = None


class RevisionWordToken(BaseModel):
    """One word-level inline diff token for ``body_html``."""

    op: str = Field(..., pattern="^(equal|insert|delete|replace)$")
    text: str


class RevisionDiffResponse(BaseModel):
    """Field-level changes between two revisions plus inline body tokens."""

    page_id: uuid.UUID
    rev_a: RevisionRef
    rev_b: RevisionRef
    changed_fields: list[str] = []
    fields: list[RevisionFieldDiff] = []
    body_word_diff: list[RevisionWordToken] = []
    identical: bool = False


# ── Sitemap entries (extended public payload) ──────────────────────────────


class SitemapSectionRow(BaseModel):
    """One crawlable address of a section beyond CMS pages.

    Exactly one of ``slug`` and ``loc`` identifies the address. Slug-shaped
    sections (a product, a category) carry ``slug`` and the consumer builds the
    path; archives carry a rooted ``loc`` because their path is not a slug — an
    author archive is "/blog/authors/<slug>" and a date archive is
    "/archive/<year>/<month>". Making ``slug`` required for the second shape
    means the row cannot be constructed at all, which is why both sections came
    back empty rather than malformed.
    """

    slug: str | None = None
    loc: str | None = None
    updated_at: datetime | None = None
    changefreq: str = "weekly"
    priority: float = 0.5
    # The image a crawler should associate with this URL. Relative or absolute;
    # the consumer resolves it. Optional because most sections have no image.
    image_url: str | None = None


class SitemapEntriesResponse(BaseModel):
    """Extended sitemap payload for the storefront ``sitemap.ts``.

    ``items``/``total`` keep the exact shape of the older public pages list
    (``GET /content/pages``) so existing consumers stay valid; the remaining
    keys were added for sitemap completeness (blog taxonomy + catalog).
    """

    items: list[PublicPageSummary] = []
    total: int = 0
    blog_categories: list[SitemapSectionRow] = []
    blog_tags: list[SitemapSectionRow] = []
    products: list[SitemapSectionRow] = []
    # Author and date archives were crawlable pages that nothing advertised, so
    # their content was reachable but unlinked as far as a search engine was
    # concerned. Additive keys, defaulted, so existing consumers keep working.
    blog_authors: list[SitemapSectionRow] = []
    blog_date_archives: list[SitemapSectionRow] = []
    xml_fragment: str = ""
