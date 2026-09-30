"""Pydantic schemas for the faceted product search endpoint."""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field

from app.modules.search.schemas.search import FacetBucket, SearchProductResult


# ── Enums ─────────────────────────────────────────────────────────────────


class FacetedSortOption(str, enum.Enum):
    RELEVANCE = "relevance"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING = "rating"
    NEWEST = "newest"


# ── Facet structures ──────────────────────────────────────────────────────


class Facet(BaseModel):
    """A single facet dimension with its aggregated buckets."""

    field: str
    display_name: str
    buckets: list[FacetBucket] = Field(default_factory=list)


class PriceRangeFilter(BaseModel):
    """Min/max price filter, in **Toman**.

    The index holds Rial because it is fed straight from the DB column, but the
    public money contract for this API is Toman — the catalog schemas convert on
    the way out, and the storefront renders with ``formatPrice``, which appends
    "تومان". So callers send Toman and the service converts before querying.
    """

    min: int | None = Field(None, ge=0, description="Minimum price (Toman)")
    max: int | None = Field(None, ge=0, description="Maximum price (Toman)")


# ── Request schema ────────────────────────────────────────────────────────


class FacetedSearchRequest(BaseModel):
    """Request body for the faceted product search endpoint."""

    query: str = Field("", max_length=500, description="Free-text search query (empty = match all)")
    filters: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Active filters keyed by facet field. "
            "e.g. {'category_id': ['abc'], 'brand': ['samsung'], "
            "'rating': ['4', '5'], 'in_stock': ['true'], "
            "'attr:color': ['red', 'blue']}"
        ),
    )
    price_range: PriceRangeFilter | None = Field(
        None, description="Optional price range filter, in Toman"
    )
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Results per page")
    sort_by: FacetedSortOption = Field(
        FacetedSortOption.RELEVANCE, description="Sort order"
    )
    price_histogram_interval: int = Field(
        5_000_000,
        ge=100_000,
        le=100_000_000,
        description="Histogram bucket width for the price facet, in Toman",
    )


# ── Response schema ───────────────────────────────────────────────────────


class FacetedSearchResult(BaseModel):
    """Response from the faceted product search endpoint."""

    hits: list[SearchProductResult] = Field(default_factory=list)
    facets: list[Facet] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    total_pages: int = 0

    # True when the search backend (Elasticsearch) could not be reached and
    # these empty hits mean "search is unavailable", NOT "nothing matched".
    # Without this the caller cannot tell the two apart: the search engine is
    # a separate service, so an outage would otherwise render as a storefront
    # with zero products and no error.
    degraded: bool = False
