"""Celery background tasks for the Recommendation & AI module."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database.session import async_session_factory
from app.modules.catalog.domain.models import Product, ProductStatus
from app.modules.recommendations.application.recommendation_service import (
    recommendation_service,
)
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


async def _async_update_recommendations() -> dict[str, Any]:
    """Asynchronous worker logic to refresh and cache recommendations in Redis."""
    await logger.ainfo("recommendations_update_started")

    similar_count = 0
    trending_count = 0

    async with async_session_factory() as db:
        # 1. Compute and cache top trending products (standard limit 8 and extended limit 20)
        try:
            trending_8 = await recommendation_service.get_trending_products(db, limit=8)
            trending_count = trending_8.total
            await recommendation_service.get_trending_products(db, limit=20)
            await logger.ainfo("trending_products_cached", count=trending_count)
        except Exception as exc:
            await logger.aerror("trending_cache_failed", error=str(exc))

        # 2. Fetch active products to precompute similar and co-occurrence recommendations
        try:
            active_products_stmt = (
                select(Product.id)
                .where(
                    Product.is_active.is_(True),
                    Product.status == ProductStatus.ACTIVE,
                )
                .limit(500)
            )
            result = await db.execute(active_products_stmt)
            active_ids = list(result.scalars().all())

            for pid in active_ids:
                try:
                    await recommendation_service.get_similar_products(db, pid, limit=6)
                    await recommendation_service.get_frequently_bought_together(db, pid, limit=4)
                    similar_count += 1
                except Exception as exc:
                    await logger.awarning(
                        "product_recommendation_cache_failed",
                        product_id=str(pid),
                        error=str(exc),
                    )

            await logger.ainfo("similar_recommendations_cached", processed_count=similar_count)
        except Exception as exc:
            await logger.aerror("active_products_query_failed", error=str(exc))

    await logger.ainfo(
        "recommendations_update_completed",
        trending_count=trending_count,
        similar_cached_count=similar_count,
    )
    return {
        "status": "success",
        "trending_count": trending_count,
        "similar_cached_count": similar_count,
    }


@celery_app.task(name="app.modules.recommendations.application.tasks.update_recommendations")
def update_recommendations() -> dict[str, Any]:
    """Celery task that computes and caches top trending and similar product associations in Redis."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _async_update_recommendations())
            return future.result()
    else:
        return asyncio.run(_async_update_recommendations())
