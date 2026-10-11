"""Pydantic schemas for the Link Genius module (internal links + keyword maps)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LinkSuggestion(BaseModel):
    """One ranked internal-link suggestion for a post."""

    post_id: uuid.UUID
    title: str
    slug: str
    url: str
    score: float
    excerpt: str = ""


class LinkSuggestionResponse(BaseModel):
    source_post_id: uuid.UUID
    suggestions: list[LinkSuggestion]
    total: int


class RelatedPost(BaseModel):
    """A related post for the storefront strip."""

    post_id: uuid.UUID
    title: str
    slug: str
    url: str
    score: float


class RelatedPostsResponse(BaseModel):
    items: list[RelatedPost]


class IncomingLink(BaseModel):
    """A post that links to the target — the reverse-link edge."""

    post_id: uuid.UUID
    title: str
    slug: str
    url: str
    anchor_text: str


class IncomingLinksResponse(BaseModel):
    post_id: uuid.UUID
    incoming: list[IncomingLink]
    total: int


class LinkMapVariationIn(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    kind: str = Field("manual", pattern="^(manual|ai)$")


class LinkMapVariationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    keyword: str
    kind: str


class LinkMapCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    target_url: str = Field(..., min_length=1, max_length=500)
    max_links_per_post: int = Field(3, ge=0, le=50)
    auto_link_on_publish: bool = False
    case_sensitive: bool = False
    is_active: bool = True
    variations: list[LinkMapVariationIn] = Field(default_factory=list)


class LinkMapUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    target_url: str | None = Field(None, min_length=1, max_length=500)
    max_links_per_post: int | None = Field(None, ge=0, le=50)
    auto_link_on_publish: bool | None = None
    case_sensitive: bool | None = None
    is_active: bool | None = None
    variations: list[LinkMapVariationIn] | None = None


class LinkMapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    target_url: str
    target_post_id: uuid.UUID | None = None
    max_links_per_post: int
    auto_link_on_publish: bool
    case_sensitive: bool
    is_active: bool
    variations: list[LinkMapVariationOut] = Field(default_factory=list)


class LinkMapListResponse(BaseModel):
    items: list[LinkMapOut]
    total: int


class LinkMapPreviewRequest(BaseModel):
    """Preview a map against a post body without writing anything."""

    post_id: uuid.UUID
    target_url: str
    keywords: list[str] = Field(default_factory=list)
    max_links_per_post: int = Field(3, ge=0, le=50)
    case_sensitive: bool = False


class LinkMapPreviewResponse(BaseModel):
    inserted: int
    matches: list[str] = Field(default_factory=list)


class LinkMapApplyRequest(BaseModel):
    """Apply a saved map to one post (or every published post)."""

    map_id: uuid.UUID
    post_id: uuid.UUID | None = None
    all_posts: bool = False


class LinkMapApplyResponse(BaseModel):
    posts_updated: int
    links_inserted: int


class InternalLinkItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    target_post_id: uuid.UUID | None = None
    url: str
    anchor_text: str
    link_type: str
    is_nofollow: bool
    target_blank: bool


# ── Broken-link crawler ─────────────────────────────────────────────────────


class LinkAuditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    http_status: int | None = None
    category: str
    detail: str | None = None
    is_marked_safe: bool
    last_checked_at: datetime


class LinkAuditListResponse(BaseModel):
    items: list[LinkAuditItem]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class LinkAuditRunResponse(BaseModel):
    checked: int
    broken: int
    redirect: int
    total: int
    timeout: int = 0
    error: int = 0
    blocked: int = 0


class LinkAuditMarkSafeRequest(BaseModel):
    safe: bool = True

