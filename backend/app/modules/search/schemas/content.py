"""Pydantic schemas for content (blog post / CMS page) storefront search.

Gap item 8 — storefront search used to cover products only. These schemas
carry results from the published-content indices (``{prefix}blog_posts`` and
``{prefix}cms_pages``), with a ``type`` discriminator on every hit so a merged
result list can link posts and pages appropriately.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Content types ─────────────────────────────────────────────────────────

ContentType = Literal["post", "page"]


# ── Search schemas ────────────────────────────────────────────────────────


class ContentSearchResult(BaseModel):
    """Single blog post or CMS page in content search results."""

    id: str
    type: ContentType = "post"
    title: str
    slug: str
    excerpt: str | None = None
    locale: str | None = None
    category: str | None = None
    category_slug: str | None = None
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    is_featured: bool = False
    score: float | None = Field(None, description="Relevance score")


class ContentSearchResponse(BaseModel):
    """Paginated content search response (blog posts + CMS pages)."""

    results: list[ContentSearchResult] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    total_pages: int = 0
    query: str = ""
    # Closest correction for a typo'd query (ES phrase suggester). None when
    # the suggester has nothing better or is unavailable.
    did_you_mean: str | None = None
    # True when the search fell back to PostgreSQL ILIKE because
    # Elasticsearch was unreachable — ordering is coarser and relevance
    # scoring is absent.
    degraded: bool = False


# ── Suggest schemas ───────────────────────────────────────────────────────


class ContentSuggestion(BaseModel):
    """Autocomplete suggestion over published content titles."""

    text: str
    type: ContentType = "post"
    slug: str | None = None
    id: str | None = None
    score: float | None = None


class ContentSuggestResponse(BaseModel):
    """Autocomplete suggestion response for content."""

    suggestions: list[ContentSuggestion] = Field(default_factory=list)
    query: str = ""
