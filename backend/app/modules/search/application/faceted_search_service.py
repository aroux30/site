"""Faceted product search service.

Builds an Elasticsearch query with aggregations for category, brand, price,
rating, availability, and dynamic attribute facets.  Filters are applied via
``post_filter`` so that facet bucket counts always reflect the *unfiltered*
query — the standard UX for e-commerce faceted navigation.

**Postgres fallback**: when Elasticsearch is unreachable, the storefront
product grid must not render "۰ کالا" while 5,146 products sit in Postgres —
that is what happened (memory: storefront-lists-zero-products) and it blocks
every downstream flow (cart, checkout) that starts from the grid. The
fallback answers the same request from Postgres with the same response shape
(``degraded=True`` still flags the loss of relevance ranking); it covers the
storefront's actual usage — query, category/brand/price/availability
filters, sort, pagination — and returns an empty facet list rather than
fabricating counts it cannot compute cheaply.
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
        db: Any = None,
    ) -> FacetedSearchResult:
        """Execute a faceted product search and return hits + facet counts.

        ``db`` enables the Postgres fallback when Elasticsearch is down; a
        caller that cannot supply a session gets the old degraded-empty
        answer rather than an error.
        """
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
            if db is not None:
                return await self._postgres_fallback(request, db)
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
                    # Slug-keyed so the bucket key round-trips through the
                    # category_slug filter and the storefront URL; the
                    # Persian name rides as the bucket label via the sub-agg.
                    "field": "category_slug",
                    "size": 50,
                },
                "aggs": {
                    "cat_display_name": {
                        "terms": {"field": "category_name.keyword", "size": 1},
                    },
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
                    # The indexed field is Rial; the interval arrives in
                    # Toman like the rest of the API contract, so convert —
                    # or every bucket is ten times narrower than asked.
                    "field": "price",
                    "interval": toman_to_rial(price_interval),
                    "min_doc_count": 1,
                },
            },
            "facet_price_min": {"min": {"field": "price"}},
            "facet_price_max": {"max": {"field": "price"}},
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

        # Category filter (support category_id, category_slug, or category)
        cat_values = (
            filters.get("category_id")
            or filters.get("category_slug")
            or filters.get("category")
        )
        if cat_values:
            import uuid as _uuid

            ids = []
            slugs = []
            for v in cat_values:
                try:
                    _uuid.UUID(str(v))
                    ids.append(str(v))
                except (ValueError, TypeError):
                    slugs.append(str(v))
            sub_clauses = []
            if ids:
                sub_clauses.append({"terms": {"category_id": ids}})
                sub_clauses.append({"terms": {"category_ancestors": ids}})
            if slugs:
                sub_clauses.append({"terms": {"category_slug": slugs}})
                sub_clauses.append({"terms": {"category_ancestors": slugs}})
            if len(sub_clauses) == 1:
                clauses.append(sub_clauses[0])
            elif len(sub_clauses) > 1:
                clauses.append({"bool": {"should": sub_clauses, "minimum_should_match": 1}})

        # Brand filter — bucket keys are slugs in the SQL fallback; older
        # index builds keyed by name. Match either so both key styles work.
        if brand_values := filters.get("brand"):
            clauses.append(
                {
                    "bool": {
                        "should": [
                            {"terms": {"brand_name.keyword": brand_values}},
                            {"terms": {"brand_slug": brand_values}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

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
    async def _postgres_fallback(
        request: FacetedSearchRequest,
        db: Any,
    ) -> FacetedSearchResult:
        """Answer the same request from Postgres when Elasticsearch is down.

        WooCommerce-style behaviour — the storefront catalog filters straight
        from SQL with no search engine involved. Facet buckets (category,
        brand, price, availability, rating) are aggregated from the
        *text-filtered* population, mirroring the ES ``post_filter``
        convention the UI already renders: counts ignore the shopper's facet
        selections but honour the search box. Every storefront filter is
        honoured here: free-text query (name/description ILIKE), category with
        descendants, brand (slug or name), price range, in-stock, minimum
        rating, all sort options (incl. rating), and pagination.

        Facets the data cannot support are omitted, never fabricated:
        ``attr:*`` filters stay ignored while ``product_attributes`` is empty,
        and the rating facet only appears once approved reviews exist.
        ``degraded=True`` still flags the loss of relevance ranking.

        Prices: the DB stores Rial; the API contract is Toman (memory:
        money-unit-two-conventions), so the same conversion the ES path uses
        applies here.
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy import or_, select
        from sqlalchemy.orm import joinedload

        from app.modules.catalog.domain.models import (
            Brand,
            Category,
            Product,
            ProductImage,
            ProductStatus,
            ProductVariant,
        )
        from app.modules.inventory.domain.models import InventoryItem
        from app.modules.reviews.domain.models import Review, ReviewStatus

        query = (request.query or "").strip()

        # Shared population conditions: active products narrowed only by the
        # free-text query. Facet aggregations and the hit query both start
        # from this; facet selections are applied to hits only (post_filter).
        base_conds = [
            Product.status == ProductStatus.ACTIVE,
            Product.is_active.is_(True),
        ]
        if query:
            # SQLAlchemy binds the pattern as a parameter and autoescape
            # neutralizes user-supplied %/_ wildcards, so a crafted query
            # cannot broaden the ILIKE into a full-table scan.
            base_conds.append(
                or_(
                    Product.name.icontains(query, autoescape=True),
                    Product.description.icontains(query, autoescape=True),
                )
            )

        # "In stock" = at least one active variant the inventory ledger says
        # is buyable: units available, or stock not tracked at all (unlimited).
        in_stock_exists = (
            select(1)
            .select_from(ProductVariant)
            .join(InventoryItem, InventoryItem.variant_id == ProductVariant.id)
            .where(
                ProductVariant.product_id == Product.id,
                ProductVariant.is_active.is_(True),
                or_(
                    InventoryItem.available > 0,
                    InventoryItem.track_inventory.is_(False),
                ),
            )
            .exists()
        )

        # Approved-review aggregates per product power the rating facet, the
        # rating filter, rating sorting, and hit enrichment.
        rating_agg = (
            select(
                Review.product_id.label("pid"),
                sa_func.avg(Review.rating).label("avg_rating"),
                sa_func.count(Review.id).label("rating_count"),
            )
            .where(Review.status == ReviewStatus.APPROVED)
            .group_by(Review.product_id)
            .subquery()
        )

        # ── Facets: aggregated over the text-filtered population ──────────
        facets = await FacetedSearchService._pg_build_facets(
            db, request, base_conds, in_stock_exists, rating_agg
        )

        # ── Hit query ──────────────────────────────────────────────────────
        base = (
            select(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.brand),
                joinedload(Product.variants),
            )
            .where(*base_conds)
        )
        if request.sort_by == FacetedSortOption.RATING:
            # Join the review aggregate only when sorting by rating: the
            # selected coalesce column keeps ORDER BY … with DISTINCT valid
            # in Postgres. Page hits get their ratings from the per-page
            # lookup below, so no other sort pays for this join.
            base = base.add_columns(
                sa_func.coalesce(rating_agg.c.avg_rating, -1).label("sort_rating")
            ).outerjoin(rating_agg, rating_agg.c.pid == Product.id)

        # Filters arrive as {field: [values]}. Only the ones the SQL path can
        # honour are applied; anything else (dynamic attr:*) is ignored rather
        # than failing the request — the response is flagged degraded anyway.
        filters = request.filters or {}
        for field, values in filters.items():
            if not values:
                continue
            if field in ("category_id", "category", "category_slug"):
                import uuid as _uuid

                ids = []
                slugs = []
                for v in values:
                    try:
                        ids.append(_uuid.UUID(v))
                    except (ValueError, TypeError):
                        slugs.append(str(v))

                cat_match_conditions = []
                if ids:
                    cat_match_conditions.append(Category.id.in_(ids))
                    for cid in ids:
                        # Descendants: every category whose tree path extends
                        # this one's path.
                        path_subq = (
                            select(Category.path).where(Category.id == cid).scalar_subquery()
                        )
                        cat_match_conditions.append(
                            Category.path.startswith(sa_func.concat(path_subq, "/"))
                        )
                if slugs:
                    cat_match_conditions.append(Category.slug.in_(slugs))
                    for cslug in slugs:
                        path_subq = (
                            select(Category.path).where(Category.slug == cslug).scalar_subquery()
                        )
                        cat_match_conditions.append(
                            Category.path.startswith(sa_func.concat(path_subq, "/"))
                        )

                if cat_match_conditions:
                    descendant_subq = select(Category.id).where(or_(*cat_match_conditions))
                    base = base.where(Product.category_id.in_(descendant_subq))
            elif field == "brand":
                # Bucket keys are slugs (see _pg_build_facets); legacy links
                # and older index builds carry names — match either.
                from app.modules.catalog.domain.models import Brand

                base = base.where(
                    Product.brand_id.in_(
                        select(Brand.id).where(
                            or_(Brand.slug.in_(values), Brand.name.in_(values))
                        )
                    )
                )
            elif field == "rating":
                min_rating = min(float(r) for r in values)
                rating_filter = (
                    select(Review.product_id)
                    .where(Review.status == ReviewStatus.APPROVED)
                    .group_by(Review.product_id)
                    .having(sa_func.avg(Review.rating) >= min_rating)
                )
                base = base.where(Product.id.in_(rating_filter))
            elif field == "in_stock":
                if "true" in [v.lower() for v in values]:
                    base = base.where(in_stock_exists)

        # Join variants BEFORE any ProductVariant column is referenced: a
        # where() on a not-yet-joined table makes SQLAlchemy add it to the
        # FROM list as a cartesian product, and the price filter silently
        # stops narrowing (observed live: a 50k-200k Toman range still
        # returned all 5,146 products).
        needs_variants = request.price_range is not None or request.sort_by in (
            FacetedSortOption.PRICE_ASC,
            FacetedSortOption.PRICE_DESC,
        )
        if needs_variants:
            base = base.join(ProductVariant, ProductVariant.product_id == Product.id)

        if request.price_range is not None:
            # Price filter is Toman at the boundary; the DB column is Rial.
            if request.price_range.min is not None:
                base = base.where(
                    ProductVariant.price >= toman_to_rial(request.price_range.min)
                )
            if request.price_range.max is not None:
                base = base.where(
                    ProductVariant.price <= toman_to_rial(request.price_range.max)
                )

        # Count the SUBQUERY's id column, not Product.id: selecting
        # Product.id in the outer query re-adds the whole products table to
        # the outer FROM (a cartesian join that ignores the inner WHERE), so
        # the count silently ignored every filter (observed live: a price
        # cap still returned all 5,146).
        sub = base.subquery()
        total = (
            await db.execute(
                select(sa_func.count(sa_func.distinct(sub.c.id))).select_from(sub)
            )
        ).scalar_one()

        if request.sort_by == FacetedSortOption.PRICE_ASC:
            base = base.order_by(ProductVariant.price.asc())
        elif request.sort_by == FacetedSortOption.PRICE_DESC:
            base = base.order_by(ProductVariant.price.desc())
        elif request.sort_by == FacetedSortOption.NEWEST:
            base = base.order_by(Product.created_at.desc())
        elif request.sort_by == FacetedSortOption.RATING:
            # coalesce below zero keeps reviewed products on top while
            # review-less products still get a deterministic newest-first
            # order.
            base = base.order_by(
                sa_func.coalesce(rating_agg.c.avg_rating, -1).desc(),
                Product.created_at.desc(),
            )
        else:
            # Relevance: no text rank in SQL — featured first, then newest is
            # the closest honest ordering.
            base = base.order_by(
                Product.is_featured.desc(), Product.created_at.desc()
            )

        from_offset = (request.page - 1) * request.size
        base = base.distinct().offset(from_offset).limit(request.size)
        products = (await db.execute(base)).unique().scalars().all()

        # Page ratings in one query (not per product) — ES hits carry these
        # too, so star displays keep working in the fallback.
        page_ratings: dict[Any, tuple[Any, Any]] = {}
        if products:
            rating_page_rows = (
                await db.execute(
                    select(
                        rating_agg.c.pid,
                        rating_agg.c.avg_rating,
                        rating_agg.c.rating_count,
                    ).where(rating_agg.c.pid.in_([p.id for p in products]))
                )
            ).all()
            for pid, avg_r, cnt in rating_page_rows:
                page_ratings[pid] = (avg_r, cnt)

        # Primary images in one query (not per product).
        images: dict[Any, str] = {}
        if products:
            img_rows = (
                await db.execute(
                    select(ProductImage.product_id, ProductImage.url)
                    .where(
                        ProductImage.product_id.in_([p.id for p in products]),
                        ProductImage.is_primary.is_(True),
                    )
                    .order_by(ProductImage.position)
                )
            ).all()
            for pid, url in img_rows:
                images.setdefault(pid, url)

        hits: list[SearchProductResult] = []
        for p in products:
            variant = next(
                (v for v in p.variants if v.is_active), None
            ) or (p.variants[0] if p.variants else None)
            hits.append(
                SearchProductResult(
                    id=str(p.id),
                    name=p.name,
                    slug=p.slug,
                    description=p.description,
                    short_description=p.short_description,
                    category_name=p.category.name if p.category else None,
                    category_slug=p.category.slug if p.category else None,
                    brand_name=p.brand.name if p.brand else None,
                    brand_slug=p.brand.slug if p.brand else None,
                    price=rial_to_toman(variant.price) if variant else None,
                    compare_at_price=(
                        rial_to_toman(variant.compare_at_price)
                        if variant and variant.compare_at_price
                        else None
                    ),
                    rating_average=(
                        round(float(page_ratings[p.id][0]), 2)
                        if p.id in page_ratings
                        else None
                    ),
                    rating_count=(
                        int(page_ratings[p.id][1])
                        if p.id in page_ratings
                        else None
                    ),
                    image_url=images.get(p.id),
                    is_active=p.is_active,
                    is_featured=p.is_featured,
                    score=None,
                )
            )

        await logger.ainfo(
            "faceted_search_postgres_fallback",
            query=query,
            total=total,
            returned=len(hits),
        )
        return FacetedSearchResult(
            hits=hits,
            facets=facets,
            total=total,
            page=request.page,
            size=request.size,
            total_pages=math.ceil(total / request.size) if request.size > 0 else 0,
            degraded=True,
        )

    @staticmethod
    async def _pg_build_facets(
        db: Any,
        request: FacetedSearchRequest,
        base_conds: list[Any],
        in_stock_exists: Any,
        rating_agg: Any,
    ) -> list[Facet]:
        """Aggregate real facet buckets over the text-filtered population.

        Buckets are keyed the way the storefront round-trips them: categories
        and brands by slug (the Persian name rides as ``label``), price by
        Toman histogram start, availability by "true". WooCommerce parity: a
        term with zero matching products simply does not appear, and counts
        are computed before facet selections (post_filter semantics).
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from app.modules.catalog.domain.models import (
            Brand,
            Category,
            Product,
            ProductVariant,
        )

        facets: list[Facet] = []

        # ── Category buckets (slug key, Persian name label) ────────────────
        cat_rows = (
            await db.execute(
                select(
                    Category.slug,
                    Category.name,
                    sa_func.count(sa_func.distinct(Product.id)).label("cnt"),
                )
                .join(Product, Product.category_id == Category.id)
                .where(*base_conds)
                .group_by(Category.slug, Category.name)
                .order_by(
                    sa_func.count(sa_func.distinct(Product.id)).desc(),
                    Category.name,
                )
                .limit(50)
            )
        ).all()
        if cat_rows:
            facets.append(
                Facet(
                    field="category_id",
                    display_name=_FACET_DISPLAY_NAMES["category_id"],
                    buckets=[
                        FacetBucket(key=slug, doc_count=cnt, label=name)
                        for slug, name, cnt in cat_rows
                    ],
                )
            )

        # ── Brand buckets (slug key, Persian name label) ───────────────────
        brand_rows = (
            await db.execute(
                select(
                    Brand.slug,
                    Brand.name,
                    sa_func.count(sa_func.distinct(Product.id)).label("cnt"),
                )
                .join(Product, Product.brand_id == Brand.id)
                .where(*base_conds)
                .group_by(Brand.slug, Brand.name)
                .order_by(
                    sa_func.count(sa_func.distinct(Product.id)).desc(),
                    Brand.name,
                )
                .limit(50)
            )
        ).all()
        if brand_rows:
            facets.append(
                Facet(
                    field="brand",
                    display_name=_FACET_DISPLAY_NAMES["brand"],
                    buckets=[
                        FacetBucket(key=slug, doc_count=cnt, label=name)
                        for slug, name, cnt in brand_rows
                    ],
                )
            )

        # ── Price facet: true bounds + histogram over each product's cheapest
        #    active variant (Toman), so the slider sizes to the catalogue.
        price_rows = (
            await db.execute(
                select(
                    Product.id,
                    sa_func.min(ProductVariant.price).label("p"),
                )
                .join(ProductVariant, ProductVariant.product_id == Product.id)
                .where(
                    *base_conds,
                    ProductVariant.is_active.is_(True),
                )
                .group_by(Product.id)
            )
        ).all()
        toman_prices = [
            rial_to_toman(int(r.p)) for r in price_rows if r.p is not None
        ]
        if toman_prices:
            interval = max(request.price_histogram_interval, 1)
            buckets: dict[int, int] = {}
            for tp in toman_prices:
                start = (tp // interval) * interval
                buckets[start] = buckets.get(start, 0) + 1
            facets.append(
                Facet(
                    field="price",
                    display_name=_FACET_DISPLAY_NAMES["price"],
                    buckets=[
                        FacetBucket(key=str(start), doc_count=cnt)
                        for start, cnt in sorted(buckets.items())
                    ],
                    min=float(min(toman_prices)),
                    max=float(max(toman_prices)),
                )
            )

        # ── Availability facet (real inventory counts) ─────────────────────
        in_stock_count = (
            await db.execute(
                select(sa_func.count(sa_func.distinct(Product.id))).where(
                    *base_conds,
                    in_stock_exists,
                )
            )
        ).scalar_one()
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

        # ── Rating facet (approved reviews; hidden while none exist) ───────
        rating_rows = (
            await db.execute(
                select(rating_agg.c.pid, rating_agg.c.avg_rating)
                .join(Product, Product.id == rating_agg.c.pid)
                .where(*base_conds)
            )
        ).all()
        if rating_rows:
            rating_buckets = [
                FacetBucket(
                    key=str(threshold),
                    doc_count=sum(
                        1 for r in rating_rows if float(r.avg_rating) >= threshold
                    ),
                    label="★" * threshold + " و بالاتر",
                )
                for threshold in (4, 3, 2, 1)
                if any(float(r.avg_rating) >= threshold for r in rating_rows)
            ]
            if rating_buckets:
                facets.append(
                    Facet(
                        field="rating",
                        display_name=_FACET_DISPLAY_NAMES["rating"],
                        buckets=rating_buckets,
                    )
                )

        return facets

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

        # Category facet (slug-keyed buckets, Persian display name as label)
        cat_buckets = aggs.get("facet_categories", {}).get("buckets", [])
        if cat_buckets:
            facets.append(
                Facet(
                    field="category_id",
                    display_name=_FACET_DISPLAY_NAMES["category_id"],
                    buckets=[
                        FacetBucket(
                            key=b["key"],
                            doc_count=b["doc_count"],
                            label=(
                                (
                                    b.get("cat_display_name", {}).get("buckets")
                                    or [{}]
                                )[0].get("key")
                            ),
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
                    min=rial_to_toman(
                        int(aggs.get("facet_price_min", {}).get("value") or 0)
                    ),
                    max=rial_to_toman(
                        int(aggs.get("facet_price_max", {}).get("value") or 0)
                    ),
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
