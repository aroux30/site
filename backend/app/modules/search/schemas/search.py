"""Pydantic schemas for the search module."""

from __future__ import annotations

import enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────


class SearchSortOption(str, enum.Enum):
    RELEVANCE = "relevance"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING = "rating"
    NEWEST = "newest"


# ── Request schemas ───────────────────────────────────────────────────────


class SearchFilters(BaseModel):
    """Filters that can be applied alongside a search query."""

    category: Optional[str] = Field(None, description="Category slug or ID")
    brand: Optional[str] = Field(None, description="Brand slug or ID")
    min_price: Optional[int] = Field(None, ge=0, description="Minimum price (Rial)")
    max_price: Optional[int] = Field(None, ge=0, description="Maximum price (Rial)")
    min_rating: Optional[float] = Field(None, ge=1, le=5, description="Minimum average rating")
    attributes: Optional[dict[str, list[str]]] = Field(
        None,
        description="Attribute filters, e.g. {'color': ['red', 'blue']}",
    )
    is_active: Optional[bool] = Field(True, description="Filter by active status")


class SearchRequest(BaseModel):
    """Full-text product search request."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query text")
    filters: SearchFilters = Field(default_factory=SearchFilters)
    sort: SearchSortOption = Field(SearchSortOption.RELEVANCE, description="Sort order")
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Results per page")


# ── Response schemas ──────────────────────────────────────────────────────


class SearchProductResult(BaseModel):
    """Single product in search results."""

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    category_name: Optional[str] = None
    category_slug: Optional[str] = None
    brand_name: Optional[str] = None
    brand_slug: Optional[str] = None
    price: Optional[int] = None
    compare_at_price: Optional[int] = None
    rating_average: Optional[float] = None
    rating_count: Optional[int] = None
    image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_featured: bool = False
    score: Optional[float] = Field(None, description="Relevance score")


class FacetBucket(BaseModel):
    """A single bucket in a facet aggregation."""

    key: str
    doc_count: int
    label: Optional[str] = None


class PriceRangeFacet(BaseModel):
    """Price range facet bucket."""

    min: int
    max: int
    doc_count: int


class SearchFacets(BaseModel):
    """Aggregation facets returned with search results."""

    categories: list[FacetBucket] = Field(default_factory=list)
    brands: list[FacetBucket] = Field(default_factory=list)
    price_ranges: list[PriceRangeFacet] = Field(default_factory=list)
    attributes: dict[str, list[FacetBucket]] = Field(default_factory=dict)


class SearchSuggestion(BaseModel):
    """Autocomplete suggestion item."""

    text: str
    score: Optional[float] = None
    product_id: Optional[str] = None
    image_url: Optional[str] = None


class SearchResponse(BaseModel):
    """Paginated search response with facets and suggestions."""

    results: list[SearchProductResult] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    total_pages: int = 0
    facets: SearchFacets = Field(default_factory=SearchFacets)
    suggestions: list[SearchSuggestion] = Field(default_factory=list)
    query: str = ""


class SuggestResponse(BaseModel):
    """Autocomplete suggestion response."""

    suggestions: list[SearchSuggestion] = Field(default_factory=list)
    query: str = ""


class PopularSearchItem(BaseModel):
    """A popular search term."""

    query: str
    count: int


class PopularSearchesResponse(BaseModel):
    """Response for popular search terms endpoint."""

    searches: list[PopularSearchItem] = Field(default_factory=list)


class ReindexResponse(BaseModel):
    """Response from admin reindex operation."""

    success: bool
    indexed: int = 0
    errors: int = 0
    message: str = ""
