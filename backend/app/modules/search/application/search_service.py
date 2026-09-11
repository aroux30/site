"""Search application service.

Orchestrates full-text product search, autocomplete suggestions, popular
searches tracking, and index management via Elasticsearch.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.cache.redis import get_redis
from app.core.config.settings import get_settings
from app.modules.catalog.domain.models import (
    Product,
    ProductTag,
)
from app.modules.search.infrastructure.elasticsearch_client import (
    ElasticsearchService,
    get_elasticsearch_service,
)
from app.modules.search.schemas.search import (
    FacetBucket,
    PopularSearchesResponse,
    PopularSearchItem,
    PriceRangeFacet,
    ReindexResponse,
    SearchFacets,
    SearchFilters,
    SearchProductResult,
    SearchResponse,
    SearchSortOption,
    SearchSuggestion,
    SuggestResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

_POPULAR_SEARCHES_KEY = "search:popular"
_POPULAR_SEARCHES_TTL = 3600  # 1 hour


class SearchService:
    """Application-level search operations."""

    def __init__(self, es: ElasticsearchService | None = None) -> None:
        self._es = es or get_elasticsearch_service()
        self._settings = get_settings()

    # ── Full-text search ──────────────────────────────────────────────

    async def search_products(
        self,
        query: str,
        filters: SearchFilters | None = None,
        sort: SearchSortOption = SearchSortOption.RELEVANCE,
        page: int = 1,
        size: int = 20,
    ) -> SearchResponse:
        """Execute a full-text product search with filters and facets."""
        filters = filters or SearchFilters()
        from_offset = (page - 1) * size

        # Build query
        es_query = self._build_search_query(query, filters)
        sort_clause = self._build_sort(sort)
        aggs = self._build_aggregations()

        body: dict[str, Any] = {
            "query": es_query,
            "from": from_offset,
            "size": size,
            "sort": sort_clause,
            "aggs": aggs,
            "highlight": {
                "fields": {
                    "name": {"number_of_fragments": 0},
                    "description": {"fragment_size": 150, "number_of_fragments": 2},
                },
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
            },
        }

        try:
            raw = await self._es.search(body)
        except Exception as exc:
            await logger.awarning("elasticsearch_search_failed", error=str(exc), query=query)
            return SearchResponse(
                results=[],
                total=0,
                page=page,
                size=size,
                total_pages=0,
                facets=SearchFacets(),
                query=query,
            )

        # Track query for popular searches (fire-and-forget)
        await self._track_search_query(query)

        # Parse results
        hits = raw.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        results = [self._parse_hit(hit) for hit in hits.get("hits", [])]
        facets = self._parse_aggregations(raw.get("aggregations", {}))
        total_pages = math.ceil(total / size) if size > 0 else 0

        return SearchResponse(
            results=results,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            facets=facets,
            query=query,
        )

    # ── Autocomplete suggestions ──────────────────────────────────────

    async def get_suggestions(self, query: str, size: int = 5) -> SuggestResponse:
        """Return autocomplete suggestions for a partial query."""
        body: dict[str, Any] = {
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "name.autocomplete^3",
                                    "brand_name.keyword^2",
                                    "category_name.keyword",
                                    "tags.keyword",
                                ],
                                "type": "best_fields",
                            },
                        },
                    ],
                    "filter": [{"term": {"is_active": True}}],
                },
            },
            "_source": ["id", "name", "slug", "image_url"],
        }

        try:
            raw = await self._es.search(body)
            hits = raw.get("hits", {}).get("hits", [])
        except Exception as exc:
            await logger.awarning("elasticsearch_suggest_failed", error=str(exc), query=query)
            hits = []

        suggestions = [
            SearchSuggestion(
                text=hit["_source"].get("name", ""),
                score=hit.get("_score"),
                product_id=hit["_source"].get("id"),
                image_url=hit["_source"].get("image_url"),
            )
            for hit in hits
        ]

        return SuggestResponse(suggestions=suggestions, query=query)

    # ── Popular searches ──────────────────────────────────────────────

    async def get_popular_searches(self, size: int = 10) -> PopularSearchesResponse:
        """Return the most popular recent search terms."""
        redis = await get_redis()
        top = await redis.zrevrange(
            f"{self._settings.REDIS_KEY_PREFIX}{_POPULAR_SEARCHES_KEY}",
            0,
            size - 1,
            withscores=True,
        )
        searches = [PopularSearchItem(query=term, count=int(score)) for term, score in top]
        return PopularSearchesResponse(searches=searches)

    # ── Index management ──────────────────────────────────────────────

    async def index_product(
        self, product_dict: dict[str, Any], index_name: str | None = None
    ) -> None:
        """Index a single product document."""
        doc_id = str(product_dict["id"])
        await self._es.index_document(doc_id, product_dict, index_name=index_name)

    async def bulk_index_products(
        self, products: list[dict[str, Any]], index_name: str | None = None
    ) -> dict[str, Any]:
        """Bulk-index a list of product documents."""
        target = index_name or self._es.index_name
        actions = [
            {
                "_index": target,
                "_id": str(p["id"]),
                "_source": p,
            }
            for p in products
        ]
        return await self._es.bulk_index(actions)

    async def delete_product_index(self, product_id: str, index_name: str | None = None) -> None:
        """Remove a product from the search index."""
        await self._es.delete_document(product_id, index_name=index_name)

    async def reindex_all(
        self, db: AsyncSession, index_name: str | None = None
    ) -> ReindexResponse:
        """Re-create the index and re-index all active products from the DB.

        This is an admin operation.
        """
        await logger.ainfo("reindex_started", index_name=index_name or self._es.index_name)

        # Re-create the index
        await self._es.create_product_index(force=True, index_name=index_name)

        # Load all active products with relationships
        stmt = (
            select(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.brand),
                joinedload(Product.variants),
                joinedload(Product.images),
                joinedload(Product.product_tags).joinedload(ProductTag.tag),
                joinedload(Product.product_attributes),
            )
            .where(Product.is_active.is_(True))
        )
        result = await db.execute(stmt)
        products = result.unique().scalars().all()

        # Build index documents
        docs: list[dict[str, Any]] = []
        for product in products:
            doc = self._product_to_doc(product)
            docs.append(doc)

        if not docs:
            return ReindexResponse(
                success=True,
                indexed=0,
                errors=0,
                message="No active products to index",
            )

        # Bulk index
        bulk_result = await self.bulk_index_products(docs, index_name=index_name)
        success_count = bulk_result.get("success", 0)
        error_list = bulk_result.get("errors", [])
        error_count = len(error_list) if isinstance(error_list, list) else 0

        await logger.ainfo(
            "reindex_completed",
            total=len(docs),
            success=success_count,
            errors=error_count,
        )

        return ReindexResponse(
            success=error_count == 0,
            indexed=success_count,
            errors=error_count,
            message=f"Indexed {success_count} products with {error_count} errors",
        )

    # ── Private helpers ───────────────────────────────────────────────

    def _build_search_query(self, query: str, filters: SearchFilters) -> dict[str, Any]:
        """Build the Elasticsearch bool query."""
        must: list[dict[str, Any]] = []
        filter_clauses: list[dict[str, Any]] = []

        # Full-text query with boosting
        must.append(
            {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^3",
                        "description",
                        "tags^2",
                        "brand_name^2",
                        "category_name",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                    "minimum_should_match": "75%",
                },
            }
        )

        # Filters
        if filters.category:
            filter_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"term": {"category_slug": filters.category}},
                            {"term": {"category_id": filters.category}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        if filters.brand:
            filter_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"term": {"brand_slug": filters.brand}},
                            {"term": {"brand_id": filters.brand}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        # Price range
        price_range: dict[str, Any] = {}
        if filters.min_price is not None:
            price_range["gte"] = filters.min_price
        if filters.max_price is not None:
            price_range["lte"] = filters.max_price
        if price_range:
            filter_clauses.append({"range": {"price": price_range}})

        # Rating
        if filters.min_rating is not None:
            filter_clauses.append({"range": {"rating_average": {"gte": filters.min_rating}}})

        # Active status
        if filters.is_active is not None:
            filter_clauses.append({"term": {"is_active": filters.is_active}})

        # Attribute filters (nested)
        if filters.attributes:
            for attr_name, attr_values in filters.attributes.items():
                filter_clauses.append(
                    {
                        "nested": {
                            "path": "attributes",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"attributes.name": attr_name}},
                                        {"terms": {"attributes.value": attr_values}},
                                    ],
                                },
                            },
                        },
                    }
                )

        return {
            "bool": {
                "must": must,
                "filter": filter_clauses,
            },
        }

    @staticmethod
    def _build_sort(sort: SearchSortOption) -> list[dict[str, Any] | str]:
        """Build ES sort clause."""
        if sort == SearchSortOption.PRICE_ASC:
            return [{"price": {"order": "asc"}}, "_score"]
        if sort == SearchSortOption.PRICE_DESC:
            return [{"price": {"order": "desc"}}, "_score"]
        if sort == SearchSortOption.RATING:
            return [{"rating_average": {"order": "desc"}}, "_score"]
        if sort == SearchSortOption.NEWEST:
            return [{"created_at": {"order": "desc"}}, "_score"]
        # RELEVANCE (default)
        return ["_score", {"created_at": {"order": "desc"}}]

    @staticmethod
    def _build_aggregations() -> dict[str, Any]:
        """Build aggregations for faceted search."""
        return {
            "categories": {
                "terms": {
                    "field": "category_name.keyword",
                    "size": 30,
                },
            },
            "brands": {
                "terms": {
                    "field": "brand_name.keyword",
                    "size": 30,
                },
            },
            "price_ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"to": 500_000, "key": "under_500k"},
                        {"from": 500_000, "to": 1_000_000, "key": "500k_1m"},
                        {"from": 1_000_000, "to": 5_000_000, "key": "1m_5m"},
                        {"from": 5_000_000, "to": 10_000_000, "key": "5m_10m"},
                        {"from": 10_000_000, "to": 50_000_000, "key": "10m_50m"},
                        {"from": 50_000_000, "key": "over_50m"},
                    ],
                },
            },
            "attributes": {
                "nested": {
                    "path": "attributes",
                },
                "aggs": {
                    "attribute_names": {
                        "terms": {
                            "field": "attributes.name",
                            "size": 20,
                        },
                        "aggs": {
                            "attribute_values": {
                                "terms": {
                                    "field": "attributes.value",
                                    "size": 30,
                                },
                            },
                        },
                    },
                },
            },
        }

    @staticmethod
    def _parse_hit(hit: dict[str, Any]) -> SearchProductResult:
        """Parse a single ES hit into a SearchProductResult."""
        source = hit.get("_source", {})
        return SearchProductResult(
            id=source.get("id", ""),
            name=source.get("name", ""),
            slug=source.get("slug", ""),
            description=source.get("description"),
            short_description=source.get("short_description"),
            category_name=source.get("category_name"),
            category_slug=source.get("category_slug"),
            brand_name=source.get("brand_name"),
            brand_slug=source.get("brand_slug"),
            price=source.get("price"),
            compare_at_price=source.get("compare_at_price"),
            rating_average=source.get("rating_average"),
            rating_count=source.get("rating_count"),
            image_url=source.get("image_url"),
            tags=source.get("tags", []),
            is_active=source.get("is_active", True),
            is_featured=source.get("is_featured", False),
            score=hit.get("_score"),
        )

    @staticmethod
    def _parse_aggregations(aggs: dict[str, Any]) -> SearchFacets:
        """Parse ES aggregation results into SearchFacets."""
        # Categories
        categories = [
            FacetBucket(key=b["key"], doc_count=b["doc_count"])
            for b in aggs.get("categories", {}).get("buckets", [])
        ]

        # Brands
        brands = [
            FacetBucket(key=b["key"], doc_count=b["doc_count"])
            for b in aggs.get("brands", {}).get("buckets", [])
        ]

        # Price ranges
        price_ranges = []
        for b in aggs.get("price_ranges", {}).get("buckets", []):
            price_ranges.append(
                PriceRangeFacet(
                    min=int(b.get("from", 0)),
                    max=int(b.get("to", 0)),
                    doc_count=b["doc_count"],
                )
            )

        # Nested attributes
        attributes: dict[str, list[FacetBucket]] = {}
        attr_agg = aggs.get("attributes", {}).get("attribute_names", {})
        for name_bucket in attr_agg.get("buckets", []):
            attr_name = name_bucket["key"]
            values = [
                FacetBucket(key=v["key"], doc_count=v["doc_count"])
                for v in name_bucket.get("attribute_values", {}).get("buckets", [])
            ]
            attributes[attr_name] = values

        return SearchFacets(
            categories=categories,
            brands=brands,
            price_ranges=price_ranges,
            attributes=attributes,
        )

    @staticmethod
    def _product_to_doc(product: Product) -> dict[str, Any]:
        """Convert a SQLAlchemy Product model to an indexable document."""
        # Find primary/lowest-price variant
        price = 0
        compare_at_price = None
        sku = ""
        if product.variants:
            cheapest = min(product.variants, key=lambda v: v.price)
            price = cheapest.price
            compare_at_price = cheapest.compare_at_price
            sku = cheapest.sku

        # Primary image
        image_url = None
        if product.images:
            primary = next((img for img in product.images if img.is_primary), None)
            image_url = (primary or product.images[0]).url if product.images else None

        # Tags
        tags = [pt.tag.name for pt in (product.product_tags or []) if pt.tag]

        # Attributes
        attributes = []
        for pa in product.product_attributes or []:
            if pa.attribute and pa.attribute_value:
                attributes.append(
                    {
                        "name": pa.attribute.slug,
                        "value": pa.attribute_value.slug,
                    }
                )

        return {
            "id": str(product.id),
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "short_description": product.short_description,
            "category_id": str(product.category_id) if product.category_id else None,
            "category_name": product.category.name if product.category else None,
            "category_slug": product.category.slug if product.category else None,
            "brand_id": str(product.brand_id) if product.brand_id else None,
            "brand_name": product.brand.name if product.brand else None,
            "brand_slug": product.brand.slug if product.brand else None,
            "price": price,
            "compare_at_price": compare_at_price,
            "rating_average": None,  # Populated by review service
            "rating_count": 0,
            "tags": tags,
            "attributes": attributes,
            "sku": sku,
            "image_url": image_url,
            "is_active": product.is_active,
            "is_featured": product.is_featured,
            "status": product.status.value if product.status else None,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        }

    async def _track_search_query(self, query: str) -> None:
        """Increment the popularity counter for a search query in Redis."""
        try:
            normalized = query.strip().lower()
            if len(normalized) < 2:
                return
            redis = await get_redis()
            key = f"{self._settings.REDIS_KEY_PREFIX}{_POPULAR_SEARCHES_KEY}"
            await redis.zincrby(key, 1, normalized)
        except Exception:
            # Non-critical – don't let tracking failures break search
            await logger.awarning("search_tracking_failed", query=query, exc_info=True)


# ── Module-level convenience ──────────────────────────────────────────────

_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    """Return (and lazily create) the module-level SearchService."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
