"""Recommendation & AI service.

Provides algorithms for:
- Similar products (category, brand, tag overlap, price range proximity)
- Frequently bought together (market basket analysis on co-occurring order items)
- Personalized recommendations (user wishlist, recent orders, category preferences)
- Trending products (order volume and review velocity over the last 14 days)

Includes Redis caching and structured logging with structlog.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import desc, distinct, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.cache.redis import cache_get, cache_set
from app.core.exceptions.handlers import NotFoundError
from app.modules.catalog.domain.models import (
    Product,
    ProductStatus,
    ProductVariant,
)
from app.modules.catalog.schemas.catalog import ProductResponse, rial_to_toman
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.recommendations.schemas.recommendations import (
    FrequentlyBoughtTogetherResponse,
    PersonalizedFeedResponse,
    RecommendedProductItem,
    SimilarProductsResponse,
    TrendingProductsResponse,
)
from app.modules.reviews.domain.models import Review, ReviewStatus
from app.modules.wishlist.domain.models import Wishlist, WishlistItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# ── Cache TTL configurations (in seconds) ──────────────────────────────────
CACHE_TTL_SIMILAR = 7200  # 2 hours
CACHE_TTL_FBT = 7200  # 2 hours
CACHE_TTL_TRENDING = 3600  # 1 hour
CACHE_TTL_PERSONALIZED = 900  # 15 minutes


def _product_options() -> list[Any]:
    """Lightweight eager-load options required for computing similarity and generating responses."""  # noqa: E501
    return [
        selectinload(Product.variants),
        selectinload(Product.images),
        selectinload(Product.product_tags),
    ]


def _product_to_response(product: Product) -> ProductResponse:
    """Map a Product domain model to ProductResponse schema."""
    active_variants = [v for v in product.variants if v.is_active] if product.variants else []
    min_price: int | None = None
    max_price: int | None = None
    if active_variants:
        prices = [v.price for v in active_variants]
        min_price = rial_to_toman(min(prices))
        max_price = rial_to_toman(max(prices))

    primary_image_url: str | None = None
    if product.images:
        primary_images = [img for img in product.images if img.is_primary]
        if primary_images:
            primary_image_url = primary_images[0].url
        else:
            sorted_images = sorted(product.images, key=lambda i: getattr(i, "position", 0))
            primary_image_url = sorted_images[0].url

    return ProductResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        category_id=product.category_id,
        brand_id=product.brand_id,
        short_description=product.short_description,
        product_type=product.product_type,
        status=product.status,
        is_active=product.is_active,
        is_featured=product.is_featured,
        primary_image_url=primary_image_url,
        min_price=min_price,
        max_price=max_price,
        variant_count=len(product.variants) if product.variants else 0,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def _fetch_products_by_ids(
    db: AsyncSession,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Product]:
    """Batch fetch products by IDs with required relations."""
    if not product_ids:
        return {}
    stmt = (
        select(Product)
        .options(*_product_options())
        .where(
            Product.id.in_(product_ids),
            Product.is_active.is_(True),
            Product.status == ProductStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    products = result.unique().scalars().all()
    return {p.id: p for p in products}


class RecommendationService:
    """Enterprise recommendation engine service."""

    # ── 1. Similar Products ──────────────────────────────────────────────────

    async def get_similar_products(
        self,
        db: AsyncSession,
        product_id: uuid.UUID,
        limit: int = 6,
    ) -> SimilarProductsResponse:
        """Calculate similarity based on shared category, shared brand,
        tag overlap, and price range proximity.

        Scoring breakdown:
        - Shared category: 35% weight
        - Shared brand: 20% weight
        - Tag overlap (Jaccard similarity): 25% weight
        - Price range proximity: 20% weight
        """
        cache_key = f"recommendations:similar:{product_id}:{limit}"
        try:
            cached = await cache_get(cache_key)
            if cached:
                data = json.loads(cached)
                return SimilarProductsResponse.model_validate(data)
        except Exception as exc:
            await logger.awarning("cache_get_failed", key=cache_key, error=str(exc))

        # 1. Fetch target product
        target_stmt = select(Product).options(*_product_options()).where(Product.id == product_id)
        result = await db.execute(target_stmt)
        target_product = result.unique().scalar_one_or_none()

        if target_product is None:
            raise NotFoundError("Product", f"Product with ID '{product_id}' was not found")

        target_tags = (
            {pt.tag_id for pt in target_product.product_tags}
            if target_product.product_tags
            else set()
        )
        target_active_variants = (
            [v for v in target_product.variants if v.is_active] if target_product.variants else []
        )
        target_price = min((v.price for v in target_active_variants), default=0)

        # 2. Fetch candidate products (active, excluding self)
        # Prioritize candidates sharing category, brand, or any tag, plus recent active items
        candidate_stmt = (
            select(Product)
            .options(*_product_options())
            .where(
                Product.id != product_id,
                Product.is_active.is_(True),
                Product.status == ProductStatus.ACTIVE,
            )
            .limit(100)
        )
        cand_result = await db.execute(candidate_stmt)
        candidates = cand_result.unique().scalars().all()

        scored_candidates: list[tuple[float, str, Product]] = []

        for cand in candidates:
            # Category match (0.35)
            cat_score = 1.0 if cand.category_id == target_product.category_id else 0.0

            # Brand match (0.20)
            brand_score = (
                1.0
                if target_product.brand_id is not None and cand.brand_id == target_product.brand_id
                else 0.0
            )

            # Tag overlap (0.25)
            cand_tags = {pt.tag_id for pt in cand.product_tags} if cand.product_tags else set()
            if target_tags or cand_tags:
                tag_overlap = len(target_tags & cand_tags)
                tag_union = len(target_tags | cand_tags)
                tag_score = tag_overlap / tag_union if tag_union > 0 else 0.0
            else:
                tag_score = 0.0

            # Price proximity (0.20)
            cand_variants = [v for v in cand.variants if v.is_active] if cand.variants else []
            cand_price = min((v.price for v in cand_variants), default=0)
            if target_price > 0 and cand_price > 0:
                price_diff = abs(target_price - cand_price)
                max_p = max(target_price, cand_price)
                price_score = max(0.0, 1.0 - (price_diff / max_p))
            elif target_price == 0 and cand_price == 0:
                price_score = 0.5
            else:
                price_score = 0.0

            total_score = (
                0.35 * cat_score + 0.20 * brand_score + 0.25 * tag_score + 0.20 * price_score
            )

            # Determine primary descriptive reason
            reasons: list[str] = []
            if cat_score > 0 and brand_score > 0:
                reasons.append("Same category and brand")
            elif cat_score > 0:
                reasons.append("Same category")
            elif brand_score > 0:
                reasons.append("Same brand")

            if tag_score >= 0.3:
                reasons.append("Matching tags")
            if price_score >= 0.8:
                reasons.append("Similar price range")

            reason_str = " & ".join(reasons) if reasons else "Similar product attributes"

            scored_candidates.append((round(total_score, 4), reason_str, cand))

        # Sort by similarity score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored_candidates[:limit]

        items: list[RecommendedProductItem] = [
            RecommendedProductItem(
                product_id=cand.id,
                product=_product_to_response(cand),
                score=score,
                reason=reason,
            )
            for score, reason, cand in top_candidates
        ]

        response = SimilarProductsResponse(
            product_id=product_id,
            items=items,
            total=len(items),
        )

        try:
            await cache_set(cache_key, response.model_dump_json(), ttl=CACHE_TTL_SIMILAR)
        except Exception as exc:
            await logger.awarning("cache_set_failed", key=cache_key, error=str(exc))

        return response

    # ── 2. Frequently Bought Together ────────────────────────────────────────

    async def get_frequently_bought_together(
        self,
        db: AsyncSession,
        product_id: uuid.UUID,
        limit: int = 4,
    ) -> FrequentlyBoughtTogetherResponse:
        """Analyze order_items from the same orders to find co-occurring products."""
        cache_key = f"recommendations:fbt:{product_id}:{limit}"
        try:
            cached = await cache_get(cache_key)
            if cached:
                data = json.loads(cached)
                return FrequentlyBoughtTogetherResponse.model_validate(data)
        except Exception as exc:
            await logger.awarning("cache_get_failed", key=cache_key, error=str(exc))

        # Ensure source product exists
        product_exists_stmt = select(Product.id).where(Product.id == product_id)
        result = await db.execute(product_exists_stmt)
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Product", f"Product with ID '{product_id}' was not found")

        # Find orders that contain any variant of the target product
        target_orders_subq = (
            select(OrderItem.order_id)
            .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                ProductVariant.product_id == product_id,
                Order.status != OrderStatus.CANCELED,
            )
            .distinct()
            .subquery()
        )

        # Count total valid orders with target product
        total_target_orders_stmt = select(func.count()).select_from(target_orders_subq)
        total_target_orders = (await db.execute(total_target_orders_stmt)).scalar() or 0

        # Query co-occurring products from those orders
        co_occurrence_stmt = (
            select(
                ProductVariant.product_id,
                func.count(distinct(OrderItem.order_id)).label("co_count"),
            )
            .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
            .join(target_orders_subq, OrderItem.order_id == target_orders_subq.c.order_id)
            .where(ProductVariant.product_id != product_id)
            .group_by(ProductVariant.product_id)
            .order_by(desc("co_count"))
            .limit(limit)
        )
        co_results = (await db.execute(co_occurrence_stmt)).all()

        items: list[RecommendedProductItem] = []
        if co_results:
            co_product_ids = [row[0] for row in co_results]
            products_map = await _fetch_products_by_ids(db, co_product_ids)

            for pid, count in co_results:
                product = products_map.get(pid)
                if not product:
                    continue
                # Calculate confidence score between 0.50 and 1.00 based on co-occurrence ratio
                ratio = count / total_target_orders if total_target_orders > 0 else 1.0
                norm_score = min(1.0, 0.50 + 0.50 * ratio)
                reason = f"Frequently bought together in {count} order{'s' if count > 1 else ''}"
                items.append(
                    RecommendedProductItem(
                        product_id=product.id,
                        product=_product_to_response(product),
                        score=round(norm_score, 4),
                        reason=reason,
                    )
                )

        # If no or insufficient co-occurrences found, supplement with similar products
        if len(items) < limit:
            similar_resp = await self.get_similar_products(db, product_id, limit=limit)
            existing_ids = {it.product_id for it in items} | {product_id}
            for sim_item in similar_resp.items:
                if sim_item.product_id not in existing_ids:
                    items.append(
                        RecommendedProductItem(
                            product_id=sim_item.product_id,
                            product=sim_item.product,
                            score=round(sim_item.score * 0.85, 4),
                            reason="Frequently viewed together with this item",
                        )
                    )
                    existing_ids.add(sim_item.product_id)
                    if len(items) >= limit:
                        break

        response = FrequentlyBoughtTogetherResponse(
            product_id=product_id,
            items=items,
            total=len(items),
        )

        try:
            await cache_set(cache_key, response.model_dump_json(), ttl=CACHE_TTL_FBT)
        except Exception as exc:
            await logger.awarning("cache_set_failed", key=cache_key, error=str(exc))

        return response

    # ── 3. Personalized Recommendations ──────────────────────────────────────

    async def get_personalized_recommendations(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 8,
    ) -> PersonalizedFeedResponse:
        """Analyze user's wishlist, recent orders, and category preferences to construct a personalized feed."""  # noqa: E501
        cache_key = f"recommendations:user:{user_id}:{limit}"
        try:
            cached = await cache_get(cache_key)
            if cached:
                data = json.loads(cached)
                return PersonalizedFeedResponse.model_validate(data)
        except Exception as exc:
            await logger.awarning("cache_get_failed", key=cache_key, error=str(exc))

        # 1. Fetch user's wishlist items
        wishlist_stmt = (
            select(WishlistItem.product_id)
            .join(Wishlist, WishlistItem.wishlist_id == Wishlist.id)
            .where(Wishlist.user_id == user_id)
        )
        wishlist_pids = set((await db.execute(wishlist_stmt)).scalars().all())

        # 2. Fetch user's recent orders (products purchased)
        orders_stmt = (
            select(ProductVariant.product_id)
            .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.user_id == user_id, Order.status != OrderStatus.CANCELED)
            .order_by(Order.created_at.desc())
            .limit(50)
        )
        ordered_pids = set((await db.execute(orders_stmt)).scalars().all())

        interacted_pids = wishlist_pids | ordered_pids

        # If user has zero interactions (cold start), fallback to top trending products
        if not interacted_pids:
            trending_resp = await self.get_trending_products(db, limit=limit)
            feed_items = [
                RecommendedProductItem(
                    product_id=it.product_id,
                    product=it.product,
                    score=it.score,
                    reason="Popular recommendation for you",
                )
                for it in trending_resp.items
            ]
            response = PersonalizedFeedResponse(
                user_id=user_id,
                items=feed_items,
                total=len(feed_items),
            )
            try:
                await cache_set(cache_key, response.model_dump_json(), ttl=CACHE_TTL_PERSONALIZED)
            except Exception as exc:
                await logger.awarning("cache_set_failed", key=cache_key, error=str(exc))
            return response

        # 3. Analyze category preferences from interactions
        cat_freq_stmt = (
            select(Product.category_id, func.count(Product.id).label("freq"))
            .where(Product.id.in_(interacted_pids))
            .group_by(Product.category_id)
            .order_by(desc("freq"))
        )
        cat_freq_rows = (await db.execute(cat_freq_stmt)).all()
        category_weights: dict[uuid.UUID, float] = {}
        if cat_freq_rows:
            max_freq = max(row[1] for row in cat_freq_rows)
            category_weights = {row[0]: row[1] / max_freq for row in cat_freq_rows}

        # 4. Fetch candidate products from preferred categories or wishlist
        preferred_cat_ids = list(category_weights.keys())
        cand_stmt = (
            select(Product)
            .options(*_product_options())
            .where(
                Product.is_active.is_(True),
                Product.status == ProductStatus.ACTIVE,
                or_(
                    Product.category_id.in_(preferred_cat_ids),
                    Product.id.in_(wishlist_pids),
                    Product.is_featured.is_(True),
                ),
            )
            .limit(100)
        )
        cand_result = await db.execute(cand_stmt)
        candidates = cand_result.unique().scalars().all()

        scored_items: list[tuple[float, str, Product]] = []

        for cand in candidates:
            # Base interaction score
            score = 0.50
            reason_parts: list[str] = []

            # In user's wishlist
            if cand.id in wishlist_pids:
                score += 0.35
                reason_parts.append("Saved in your wishlist")

            # In user's preferred category
            cat_wt = category_weights.get(cand.category_id, 0.0)
            if cat_wt > 0:
                score += 0.25 * cat_wt
                if not reason_parts:
                    reason_parts.append("Based on your browsing & shopping interests")

            # User has ordered this before (reorder recommendation)
            if cand.id in ordered_pids:
                score += 0.10
                if "Saved in your wishlist" not in reason_parts:
                    reason_parts.append("Buy it again")

            # Featured boost
            if cand.is_featured:
                score += 0.10

            final_score = min(0.99, round(score, 4))
            reason = reason_parts[0] if reason_parts else "Recommended for your preferences"
            scored_items.append((final_score, reason, cand))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored_items[:limit]

        items = [
            RecommendedProductItem(
                product_id=cand.id,
                product=_product_to_response(cand),
                score=score,
                reason=reason,
            )
            for score, reason, cand in top_candidates
        ]

        response = PersonalizedFeedResponse(
            user_id=user_id,
            items=items,
            total=len(items),
        )

        try:
            await cache_set(cache_key, response.model_dump_json(), ttl=CACHE_TTL_PERSONALIZED)
        except Exception as exc:
            await logger.awarning("cache_set_failed", key=cache_key, error=str(exc))

        return response

    # ── 4. Trending Products ─────────────────────────────────────────────────

    async def get_trending_products(
        self,
        db: AsyncSession,
        limit: int = 8,
    ) -> TrendingProductsResponse:
        """Find products with highest order volume and review activity over the last 14 days."""
        cache_key = f"recommendations:trending:{limit}"
        try:
            cached = await cache_get(cache_key)
            if cached:
                data = json.loads(cached)
                return TrendingProductsResponse.model_validate(data)
        except Exception as exc:
            await logger.awarning("cache_get_failed", key=cache_key, error=str(exc))

        cutoff_date = datetime.now(UTC) - timedelta(days=14)

        # 1. Order volume in the last 14 days
        order_vol_stmt = (
            select(
                ProductVariant.product_id,
                func.coalesce(func.sum(OrderItem.quantity), func.count(OrderItem.id)).label(
                    "volume"
                ),
            )
            .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.created_at >= cutoff_date,
                Order.status != OrderStatus.CANCELED,
            )
            .group_by(ProductVariant.product_id)
        )
        order_vol_rows = (await db.execute(order_vol_stmt)).all()
        order_volumes: dict[uuid.UUID, int] = {row[0]: int(row[1]) for row in order_vol_rows}

        # 2. Review activity in the last 14 days
        review_act_stmt = (
            select(
                Review.product_id,
                func.count(Review.id).label("cnt"),
            )
            .where(
                Review.created_at >= cutoff_date,
                Review.status == ReviewStatus.APPROVED,
            )
            .group_by(Review.product_id)
        )
        review_act_rows = (await db.execute(review_act_stmt)).all()
        review_counts: dict[uuid.UUID, int] = {row[0]: int(row[1]) for row in review_act_rows}

        # Combine activity scores: orders weighted 2.0x, reviews 1.0x
        activity_pids = set(order_volumes.keys()) | set(review_counts.keys())
        scored_trending: list[tuple[float, str, uuid.UUID]] = []

        max_raw_score = 1.0
        raw_scores: dict[uuid.UUID, float] = {}
        for pid in activity_pids:
            vol = order_volumes.get(pid, 0)
            rev = review_counts.get(pid, 0)
            raw = 2.0 * vol + 1.0 * rev
            raw_scores[pid] = raw
            if raw > max_raw_score:
                max_raw_score = raw

        for pid, raw in raw_scores.items():
            vol = order_volumes.get(pid, 0)
            rev = review_counts.get(pid, 0)
            norm_score = min(0.99, 0.60 + 0.39 * (raw / max_raw_score))

            if vol > 0 and rev > 0:
                reason = f"Trending: {vol} recent orders & {rev} new reviews"
            elif vol > 0:
                reason = f"Trending: {vol} recent orders"
            else:
                reason = f"Trending: {rev} new positive reviews"

            scored_trending.append((round(norm_score, 4), reason, pid))

        scored_trending.sort(key=lambda x: x[0], reverse=True)
        top_pids = [item[2] for item in scored_trending[:limit]]

        # Fetch products for the trending IDs
        products_map = await _fetch_products_by_ids(db, top_pids)
        items: list[RecommendedProductItem] = []

        for score, reason, pid in scored_trending[:limit]:
            prod = products_map.get(pid)
            if prod:
                items.append(
                    RecommendedProductItem(
                        product_id=prod.id,
                        product=_product_to_response(prod),
                        score=score,
                        reason=reason,
                    )
                )

        # If not enough trending items, backfill with featured / active products
        if len(items) < limit:
            existing_ids = {it.product_id for it in items}
            backfill_stmt = (
                select(Product)
                .options(*_product_options())
                .where(
                    Product.is_active.is_(True),
                    Product.status == ProductStatus.ACTIVE,
                    Product.id.not_in(existing_ids) if existing_ids else True,
                )
                .order_by(Product.is_featured.desc(), Product.created_at.desc())
                .limit(limit - len(items))
            )
            backfill_result = await db.execute(backfill_stmt)
            backfill_products = backfill_result.unique().scalars().all()

            for prod in backfill_products:
                reason = "Popular featured product" if prod.is_featured else "Top trending item"
                items.append(
                    RecommendedProductItem(
                        product_id=prod.id,
                        product=_product_to_response(prod),
                        score=0.75 if prod.is_featured else 0.65,
                        reason=reason,
                    )
                )

        response = TrendingProductsResponse(
            timeframe_days=14,
            items=items,
            total=len(items),
        )

        try:
            await cache_set(cache_key, response.model_dump_json(), ttl=CACHE_TTL_TRENDING)
        except Exception as exc:
            await logger.awarning("cache_set_failed", key=cache_key, error=str(exc))

        return response


# ── Global Singleton & Function Wrappers ─────────────────────────────────────

recommendation_service = RecommendationService()


async def get_similar_products(
    db: AsyncSession,
    product_id: uuid.UUID,
    limit: int = 6,
) -> SimilarProductsResponse:
    """Convenience function for get_similar_products."""
    return await recommendation_service.get_similar_products(db, product_id, limit=limit)


async def get_frequently_bought_together(
    db: AsyncSession,
    product_id: uuid.UUID,
    limit: int = 4,
) -> FrequentlyBoughtTogetherResponse:
    """Convenience function for get_frequently_bought_together."""
    return await recommendation_service.get_frequently_bought_together(db, product_id, limit=limit)


async def get_personalized_recommendations(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 8,
) -> PersonalizedFeedResponse:
    """Convenience function for get_personalized_recommendations."""
    return await recommendation_service.get_personalized_recommendations(db, user_id, limit=limit)


async def get_trending_products(
    db: AsyncSession,
    limit: int = 8,
) -> TrendingProductsResponse:
    """Convenience function for get_trending_products."""
    return await recommendation_service.get_trending_products(db, limit=limit)
