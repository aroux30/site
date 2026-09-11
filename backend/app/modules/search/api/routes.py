"""Search module API routes."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.search.application.search_service import SearchService, get_search_service
from app.modules.search.schemas.search import (
    PopularSearchesResponse,
    ReindexResponse,
    SearchFilters,
    SearchResponse,
    SearchSortOption,
    SuggestResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter()


def _get_service() -> SearchService:
    return get_search_service()


@router.get("", response_model=SearchResponse)
async def search_products(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: str | None = Query(None, description="Category slug or ID"),
    brand: str | None = Query(None, description="Brand slug or ID"),
    min_price: int | None = Query(None, ge=0, description="Minimum price (Rial)"),
    max_price: int | None = Query(None, ge=0, description="Maximum price (Rial)"),
    min_rating: float | None = Query(None, ge=1, le=5, description="Minimum average rating"),
    sort: SearchSortOption = Query(SearchSortOption.RELEVANCE, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    service: SearchService = Depends(_get_service),
) -> SearchResponse:
    """Full-text product search with filters, sorting, and facets."""
    filters = SearchFilters(
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
    )
    return await service.search_products(
        query=q,
        filters=filters,
        sort=sort,
        page=page,
        size=size,
    )


@router.get("/suggest", response_model=SuggestResponse)
async def suggest(
    q: str = Query(..., min_length=1, max_length=200, description="Partial query"),
    size: int = Query(5, ge=1, le=20, description="Number of suggestions"),
    service: SearchService = Depends(_get_service),
) -> SuggestResponse:
    """Return autocomplete suggestions for a partial query."""
    return await service.get_suggestions(query=q, size=size)


@router.get("/popular", response_model=PopularSearchesResponse)
async def popular_searches(
    size: int = Query(10, ge=1, le=50, description="Number of popular searches"),
    service: SearchService = Depends(_get_service),
) -> PopularSearchesResponse:
    """Return the most popular recent search terms."""
    return await service.get_popular_searches(size=size)


# ── Admin endpoints ───────────────────────────────────────────────────────

admin_router = APIRouter(
    prefix="/admin/search",
    tags=["admin-search"],
    dependencies=[Depends(RequirePermissions("search:reindex"))],
)


@admin_router.post("/reindex", response_model=ReindexResponse)
async def reindex_products(
    db: AsyncSession = Depends(get_db),
    service: SearchService = Depends(_get_service),
) -> ReindexResponse:
    """Re-create the search index and re-index all active products.

    Requires ``search:reindex`` permission.
    """
    return await service.reindex_all(db)
