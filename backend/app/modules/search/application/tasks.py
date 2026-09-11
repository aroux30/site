"""Search background Celery tasks.

Handles full re-indexing of active products to Elasticsearch and incremental
synchronisation when individual products are created or updated.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.database.session import async_session_factory
from app.modules.catalog.domain.models import Product, ProductTag
from app.modules.search.application.search_service import SearchService, get_search_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

INDEX_NAME = "ecommerce_products"


async def _full_reindex_async() -> dict[str, Any]:
    """Async execution logic for full product search reindexing."""
    search_service = get_search_service()

    async with async_session_factory() as db:
        try:
            # Reindex into both the primary 'ecommerce_products' index and the configured prefix index  # noqa: E501
            result = await search_service.reindex_all(db, index_name=INDEX_NAME)
            if search_service._es.index_name != INDEX_NAME:
                await search_service.reindex_all(db)

            await logger.ainfo(
                "full_reindex_task_completed",
                indexed=result.indexed,
                errors=result.errors,
            )
            return {
                "status": "success",
                "indexed": result.indexed,
                "errors": result.errors,
                "message": result.message,
            }
        except Exception:
            await logger.aexception("full_reindex_task_failed")
            raise


async def _sync_single_product_async(product_id: str | uuid.UUID) -> dict[str, Any]:
    """Async execution logic for single product synchronisation."""
    search_service = get_search_service()
    prod_uuid = uuid.UUID(str(product_id))

    async with async_session_factory() as db:
        try:
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
                .where(Product.id == prod_uuid)
            )
            result = await db.execute(stmt)
            product = result.unique().scalar_one_or_none()

            doc_id = str(prod_uuid)

            if product is None or not product.is_active:
                # Remove from search index
                await search_service.delete_product_index(doc_id, index_name=INDEX_NAME)
                if search_service._es.index_name != INDEX_NAME:
                    await search_service.delete_product_index(doc_id)
                await logger.ainfo("search_sync_product_deleted", product_id=doc_id)
                return {"status": "success", "action": "deleted", "product_id": doc_id}

            rating_avg, rating_count = await SearchService._get_rating_aggregate(db, product.id)
            doc = SearchService._product_to_doc(
                product,
                rating_average=rating_avg,
                rating_count=rating_count,
            )
            await search_service.index_product(doc, index_name=INDEX_NAME)
            if search_service._es.index_name != INDEX_NAME:
                await search_service.index_product(doc)

            await logger.ainfo("search_sync_product_indexed", product_id=doc_id)
            return {"status": "success", "action": "indexed", "product_id": doc_id}
        except Exception:
            await logger.aexception("sync_single_product_failed", product_id=str(product_id))
            raise


@celery_app.task(name="app.modules.search.application.tasks.full_reindex")
def full_reindex() -> dict[str, Any]:
    """Fetch active products and syncs/indexes them to Elasticsearch index 'ecommerce_products'."""
    return asyncio.run(_full_reindex_async())


@celery_app.task(name="app.modules.search.application.tasks.sync_single_product")
def sync_single_product(product_id: str) -> dict[str, Any]:
    """Synchronise a single product to Elasticsearch after create or update."""
    return asyncio.run(_sync_single_product_async(product_id))
