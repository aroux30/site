"""Search module API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.core.security.rate_limiter import limiter
from app.modules.search.application.content_search_service import (
    ContentSearchService,
    get_content_search_service,
)
from app.modules.search.application.faceted_search_service import (
    FacetedSearchService,
    get_faceted_search_service,
)
from app.modules.search.application.search_service import SearchService, get_search_service
from app.modules.search.schemas.content import (
    ContentSearchResponse,
    ContentSuggestResponse,
)
from app.modules.search.schemas.faceted import (
    FacetedSearchRequest,
    FacetedSearchResult,
)
from app.modules.search.schemas.search import (
    PopularSearchesResponse,
    ReindexResponse,
    SearchFilters,
    SearchResponse,
    SearchSortOption,
    SearchSuggestion,
    SuggestResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

settings = get_settings()

router = APIRouter()


def _get_service() -> SearchService:
    return get_search_service()


def _get_content_service() -> ContentSearchService:
    return get_content_search_service()


@router.get("", response_model=SearchResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH)
async def search_products(
    request: Request,
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
@limiter.limit(settings.RATE_LIMIT_SEARCH_SUGGEST)
async def suggest(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Partial query"),
    size: int = Query(5, ge=1, le=20, description="Number of suggestions"),
    service: SearchService = Depends(_get_service),
) -> SuggestResponse:
    """Return autocomplete suggestions for a partial query.

    Merges product suggestions with published blog-post / CMS-page titles
    (typed via ``SearchSuggestion.type``: ``product`` | ``post`` | ``page``).
    """
    response = await service.get_suggestions(query=q, size=size)
    # Content titles are additive: a content-index problem must never cost
    # the product suggestions, so failures are swallowed here.
    try:
        content = await get_content_search_service().suggest_content(q, size=size)
        response.suggestions.extend(
            SearchSuggestion(text=s.text, score=s.score, type=s.type, slug=s.slug)
            for s in content.suggestions
        )
    except Exception:
        await logger.awarning("content_suggest_merge_failed", query=q, exc_info=True)
    return response


@router.get("/suggest/content", response_model=ContentSuggestResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH_SUGGEST)
async def suggest_content(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Partial query"),
    size: int = Query(5, ge=1, le=20, description="Number of suggestions"),
    db: AsyncSession = Depends(get_db),
    service: ContentSearchService = Depends(_get_content_service),
) -> ContentSuggestResponse:
    """Autocomplete over published blog-post and CMS-page titles.

    Falls back to PostgreSQL ILIKE when Elasticsearch is unreachable.
    """
    return await service.suggest_content(q, size=size, db=db)


# ── Content search (blog posts + CMS pages) ──────────────────────────────


@router.get("/content", response_model=ContentSearchResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH)
async def search_content(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    content_type: str | None = Query(
        None,
        alias="type",
        pattern="^(post|page)$",
        description="Restrict to blog posts (post) or CMS pages (page)",
    ),
    locale: str | None = Query(None, max_length=10, description="Content locale (fa, en, ...)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
    service: ContentSearchService = Depends(_get_content_service),
) -> ContentSearchResponse:
    """Full-text search across published blog posts and CMS pages.

    Only publicly visible content is returned (published, not trashed, and
    for posts not private/password-protected). When Elasticsearch is
    unreachable the response falls back to a PostgreSQL ILIKE scan and is
    flagged ``degraded``; ``did_you_mean`` carries a spelling suggestion when
    the phrase suggester has one.
    """
    return await service.search_content(
        db,
        q,
        content_type=content_type,
        locale=locale,
        page=page,
        size=size,
    )


@router.get("/popular", response_model=PopularSearchesResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH_SUGGEST)
async def popular_searches(
    request: Request,
    size: int = Query(10, ge=1, le=50, description="Number of popular searches"),
    service: SearchService = Depends(_get_service),
) -> PopularSearchesResponse:
    """Return the most popular recent search terms."""
    return await service.get_popular_searches(size=size)


# ── Faceted search ────────────────────────────────────────────────────────


def _get_faceted_service() -> FacetedSearchService:
    return get_faceted_search_service()


@router.post("/products/faceted", response_model=FacetedSearchResult)
@limiter.limit(settings.RATE_LIMIT_SEARCH)
async def faceted_search(
    request: Request,
    body: FacetedSearchRequest,
    service: FacetedSearchService = Depends(_get_faceted_service),
) -> FacetedSearchResult:
    """Faceted product search with aggregation-driven filter counts.

    Accepts a JSON body with query, filters, price range, pagination, and
    sort options.  Returns hits together with facet buckets (category, brand,
    price histogram, rating, availability, and dynamic attributes).

    Public endpoint — no authentication required.
    """
    return await service.faceted_product_search(body)


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

# ── Admin global search (ERP feature #12) ─────────────────────────────────
#
# Mounted under ``/admin/search`` so it can never shadow the storefront
# ``/search`` endpoint, and guarded by ``admin:access`` — this box reaches
# customer PII (phone, email) that the storefront search never returns.


@admin_router.get(
    "/global",
    summary="Global admin search across orders, customers, tickets, products, vendors",
)
async def admin_global_search(
    q: str = Query(..., min_length=2, description="جست‌وجو: شماره سفارش، تلفن، ایمیل، نام، SKU"),
    entities: list[str] | None = Query(
        None,
        description="محدود کردن به انواع مشخص (order, customer, ticket, product, vendor)",
    ),
    per_type_limit: int = Query(5, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """One search box over the records support staff actually look up.

    Queries PostgreSQL (the source of truth per ADR-009) rather than the
    Elasticsearch projection: an operator helping a customer on the phone
    must find the order created thirty seconds ago, and a lagging index
    returning "not found" for a visible record reads as a bug.

    Requires ``search:reindex`` (the router-level gate) — the response
    includes customer phone numbers, so it is an admin-only surface.
    """
    from app.modules.search.application import admin_search_service

    return await admin_search_service.global_search(
        db, q, entities=entities, per_type_limit=per_type_limit
    )


@admin_router.get(
    "/entities",
    summary="Entity types the admin search box covers",
)
async def admin_search_entities() -> dict[str, str]:
    """The entity allow-list with Persian labels, for the UI."""
    from app.modules.search.application.admin_search_service import SEARCHABLE_ENTITIES

    return SEARCHABLE_ENTITIES
