"""Faceted product search service.

Builds an Elasticsearch query with aggregations for category, brand, price,
rating, availability, and dynamic attribute facets.  Filters are applied via
``post_filter`` so that facet bucket counts always reflect the *unfiltered*
query — the standard UX for e-commerce faceted navigation.
"""

from __future__ import annotations

import math
from typing import Any

import structlog

from app.modules.catalog.schemas.catalog import rial_to_toman, toman_to_rial
from app.modules.search.application.product_search_profile import product_multi_match
from app.modules.search.infrastructure.elasticsearch_client import (
    ElasticsearchService,
    get_elasticsearch_service,
)
from app.modules.search.schemas.faceted import (
    Facet,
    FacetedSearchRequest,
    FacetedSearchResult,
    FacetedSortOption,
)
from app.modules.search.schemas.search import FacetBucket, SearchProductResult

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Persian display names for built-in facets
_FACET_DISPLAY_NAMES: dict[str, str] = {
    "category_id": "دسته‌بندی",
    "brand": "برند",
    "price": "محدوده قیمت",
    "rating": "امتیاز",
    "availability": "موجودی",
}


class FacetedSearchService:
    """Elasticsearch faceted product search with post_filter semantics."""

    def __init__(self, es: ElasticsearchService | None = None) -> None:
        self._es = es or get_elasticsearch_service()

    # ── Public entry-point ─────────────────────────────────────────────

    async def faceted_product_search(
        self,
        request: FacetedSearchRequest,
    ) -> FacetedSearchResult:
        """Execute a faceted product search and return hits + facet counts."""
        from_offset = (request.page - 1) * request.size

        # 1. Core query (drives relevance scoring + facet counts)
        es_query = self._build_query(request.query)

        # 2. Aggregations (computed on the *query* result, before post_filter)
        aggs = self._build_aggregations(request.price_histogram_interval)

        # 3. Post-filter (narrows hits without affecting agg counts)
        post_filter = self._build_post_filter(request.filters, request.price_range)

        # 4. Sort
        sort_clause = self._build_sort(request.sort_by)

        body: dict[str, Any] = {
            "query": es_query,
            "from": from_offset,
            "size": request.size,
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

        if post_filter:
            body["post_filter"] = post_filter

        try:
            raw = await self._es.search(body)
        except Exception as exc:
            await logger.awarning(
                "faceted_search_failed",
                error=str(exc),
                query=request.query,
            )
            return FacetedSearchResult(
                hits=[],
                facets=[],
                total=0,
                page=request.page,
                size=request.size,
                total_pages=0,
                degraded=True,
            )

        # Parse response
        hits_data = raw.get("hits", {})
        total = hits_data.get("total", {}).get("value", 0)
        hits = [self._parse_hit(h) for h in hits_data.get("hits", [])]
        facets = self._parse_aggregations(raw.get("aggregations", {}))
        total_pages = math.ceil(total / request.size) if request.size > 0 else 0

        return FacetedSearchResult(
            hits=hits,
            facets=facets,
            total=total,
            page=request.page,
            size=request.size,
            total_pages=total_pages,
        )

    # ── Query building ─────────────────────────────────────────────────

    @staticmethod
    def _build_query(query: str) -> dict[str, Any]:
        """Build the core bool query.

        An empty query string matches all active products; a non-empty one
        performs a boosted multi_match.
        """
        filter_clauses: list[dict[str, Any]] = [
            {"term": {"is_active": True}},
        ]

        if not query.strip():
            return {"bool": {"must": [{"match_all": {}}], "filter": filter_clauses}}

        return {
            "bool": {
                "must": [product_multi_match(query)],
                "filter": filter_clauses,
            },
        }

    # ── Aggregations ───────────────────────────────────────────────────

    @staticmethod
    def _build_aggregations(price_interval: int) -> dict[str, Any]:
        """Build facet aggregations.

        These run against the *query* result (before ``post_filter``), so every
        facet always shows the full count of available options.
        """
        return {
            "facet_categories": {
                "terms": {
                    "field": "category_id",
                    "size": 50,
                },
            },
            "facet_category_names": {
                "terms": {
                    "field": "category_name.keyword",
                    "size": 50,
                },
            },
            "facet_brands": {
                "terms": {
                    "field": "brand_name.keyword",
                    "size": 50,
                },
            },
            "facet_price_histogram": {
                "histogram": {
                    "field": "price",
                    "interval": price_interval,
                    "min_doc_count": 1,
                },
            },
            "facet_rating": {
                "terms": {
                    "field": "rating_average",
                    "size": 10,
                },
            },
            "facet_availability": {
                "filter": {"term": {"is_active": True}},
                "aggs": {
                    "in_stock_count": {
                        "value_count": {"field": "id"},
                    },
                },
            },
            "facet_attributes": {
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

    # ── Post-filter (does not affect aggregation counts) ───────────────

    @staticmethod
    def _build_post_filter(
        filters: dict[str, list[str]],
        price_range: Any | None,
    ) -> dict[str, Any] | None:
        """Build a post_filter from the selected facet values.

        Using ``post_filter`` ensures aggregation counts remain unaffected by
        the user's current filter selections.
        """
        clauses: list[dict[str, Any]] = []

        # Category filter
        if cat_values := filters.get("category_id"):
            clauses.append({"terms": {"category_id": cat_values}})

        # Brand filter (match on keyword sub-field)
        if brand_values := filters.get("brand"):
            clauses.append({"terms": {"brand_name.keyword": brand_values}})

        # Rating filter
        if rating_values := filters.get("rating"):
            min_rating = min(float(r) for r in rating_values)
            clauses.append({"range": {"rating_average": {"gte": min_rating}}})

        # Availability filter
        if stock_values := filters.get("in_stock"):
            if "true" in [v.lower() for v in stock_values]:
                clauses.append({"term": {"is_active": True}})

        # Price range filter
        if price_range is not None:
            range_clause: dict[str, Any] = {}
            # The public contract for money in this API is Toman (the catalog
            # schemas convert on the way out, and `utils.ts:formatPrice` appends
            # "تومان" to whatever it is given). The index holds Rial, because it
            # is fed straight from the DB column. So a Toman bound has to become
            # Rial here, or "minimum ۵۰۰٬۰۰۰ تومان" filters at ۵۰٬۰۰۰.
            if price_range.min is not None:
                range_clause["gte"] = toman_to_rial(price_range.min)
            if price_range.max is not None:
                range_clause["lte"] = toman_to_rial(price_range.max)
            if range_clause:
                clauses.append({"range": {"price": range_clause}})

        # Dynamic attribute filters (keys prefixed with "attr:")
        for key, values in filters.items():
            if key.startswith("attr:") and values:
                attr_name = key[5:]  # strip "attr:" prefix
                clauses.append(
                    {
                        "nested": {
                            "path": "attributes",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"attributes.name": attr_name}},
                                        {"terms": {"attributes.value": values}},
                                    ],
                                },
                            },
                        },
                    }
                )

        if not clauses:
            return None

        if len(clauses) == 1:
            return clauses[0]

        return {"bool": {"filter": clauses}}

    # ── Sort ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_sort(sort: FacetedSortOption) -> list[dict[str, Any] | str]:
        """Build the ES sort clause."""
        if sort == FacetedSortOption.PRICE_ASC:
            return [{"price": {"order": "asc"}}, "_score"]
        if sort == FacetedSortOption.PRICE_DESC:
            return [{"price": {"order": "desc"}}, "_score"]
        if sort == FacetedSortOption.RATING:
            return [{"rating_average": {"order": "desc"}}, "_score"]
        if sort == FacetedSortOption.NEWEST:
            return [{"created_at": {"order": "desc"}}, "_score"]
        # RELEVANCE (default)
        return ["_score", {"created_at": {"order": "desc"}}]

    # ── Response parsing ───────────────────────────────────────────────

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
            price=rial_to_toman(source.get("price")),
            compare_at_price=rial_to_toman(source.get("compare_at_price")),
            rating_average=source.get("rating_average"),
            rating_count=source.get("rating_count"),
            image_url=source.get("image_url"),
            tags=source.get("tags", []),
            is_active=source.get("is_active", True),
            is_featured=source.get("is_featured", False),
            score=hit.get("_score"),
        )

    @staticmethod
    def _parse_aggregations(aggs: dict[str, Any]) -> list[Facet]:
        """Parse ES aggregation buckets into a list of Facet objects."""
        facets: list[Facet] = []

        # Category facet (use readable names from the parallel agg)
        cat_name_buckets = aggs.get("facet_category_names", {}).get("buckets", [])
        cat_id_buckets = aggs.get("facet_categories", {}).get("buckets", [])
        # Prefer name-based facet for display, fall back to ID-based
        cat_buckets = cat_name_buckets or cat_id_buckets
        if cat_buckets:
            facets.append(
                Facet(
                    field="category_id",
                    display_name=_FACET_DISPLAY_NAMES["category_id"],
                    buckets=[
                        FacetBucket(
                            key=b["key"],
                            doc_count=b["doc_count"],
                            label=b["key"] if cat_name_buckets else None,
                        )
                        for b in cat_buckets
                    ],
                )
            )

        # Brand facet
        brand_buckets = aggs.get("facet_brands", {}).get("buckets", [])
        if brand_buckets:
            facets.append(
                Facet(
                    field="brand",
                    display_name=_FACET_DISPLAY_NAMES["brand"],
                    buckets=[
                        FacetBucket(key=b["key"], doc_count=b["doc_count"])
                        for b in brand_buckets
                    ],
                )
            )

        # Price histogram facet
        price_buckets = aggs.get("facet_price_histogram", {}).get("buckets", [])
        if price_buckets:
            facets.append(
                Facet(
                    field="price",
                    display_name=_FACET_DISPLAY_NAMES["price"],
                    buckets=[
                        FacetBucket(
                            # Bucket keys are Rial like the indexed field; the
                            # facet is rendered as a Toman bound, so it is
                            # converted here rather than showing a range ten
                            # times higher than the products it counts.
                            key=str(rial_to_toman(int(b["key"]))),
                            doc_count=b["doc_count"],
                        )
                        for b in price_buckets
                    ],
                )
            )

        # Rating facet
        rating_buckets = aggs.get("facet_rating", {}).get("buckets", [])
        if rating_buckets:
            facets.append(
                Facet(
                    field="rating",
                    display_name=_FACET_DISPLAY_NAMES["rating"],
                    buckets=[
                        FacetBucket(
                            key=str(b["key"]),
                            doc_count=b["doc_count"],
                            label=f"{'★' * int(float(b['key']))} و بالاتر",
                        )
                        for b in sorted(rating_buckets, key=lambda x: x["key"], reverse=True)
                    ],
                )
            )

        # Availability facet
        avail_agg = aggs.get("facet_availability", {})
        in_stock_count = avail_agg.get("in_stock_count", {}).get("value", 0)
        if in_stock_count > 0:
            facets.append(
                Facet(
                    field="availability",
                    display_name=_FACET_DISPLAY_NAMES["availability"],
                    buckets=[
                        FacetBucket(
                            key="true",
                            doc_count=in_stock_count,
                            label="فقط کالاهای موجود",
                        ),
                    ],
                )
            )

        # Dynamic attribute facets (nested)
        attr_agg = aggs.get("facet_attributes", {}).get("attribute_names", {})
        for name_bucket in attr_agg.get("buckets", []):
            attr_name = name_bucket["key"]
            value_buckets = name_bucket.get("attribute_values", {}).get("buckets", [])
            if value_buckets:
                facets.append(
                    Facet(
                        field=f"attr:{attr_name}",
                        display_name=attr_name,
                        buckets=[
                            FacetBucket(key=v["key"], doc_count=v["doc_count"])
                            for v in value_buckets
                        ],
                    )
                )

        return facets


# ── Module-level convenience ──────────────────────────────────────────────

_faceted_service: FacetedSearchService | None = None


def get_faceted_search_service() -> FacetedSearchService:
    """Return (and lazily create) the module-level FacetedSearchService."""
    global _faceted_service
    if _faceted_service is None:
        _faceted_service = FacetedSearchService()
    return _faceted_service
