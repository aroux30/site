"""Elasticsearch async client with Persian analyzer support.

Manages the connection lifecycle and index creation for the product search
index, including a custom Persian analyzer with Arabic-to-Persian character
normalisation, ZWNJ handling, and Persian stop-word removal.
"""

from __future__ import annotations

from typing import Any

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError as ESNotFoundError

from app.core.config.settings import get_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# ── Module-level singleton ────────────────────────────────────────────────

_client: AsyncElasticsearch | None = None


# ── Persian analyser settings ─────────────────────────────────────────────

PERSIAN_ANALYSIS_SETTINGS: dict[str, Any] = {
    "analysis": {
        "char_filter": {
            "arabic_to_persian": {
                "type": "mapping",
                "mappings": [
                    # Arabic Yeh → Persian Yeh
                    "\\u064A=>\\u06CC",
                    # Arabic Kaf → Persian Kaf
                    "\\u0643=>\\u06A9",
                    # Arabic digits → Persian digits
                    "\\u0660=>\\u06F0",
                    "\\u0661=>\\u06F1",
                    "\\u0662=>\\u06F2",
                    "\\u0663=>\\u06F3",
                    "\\u0664=>\\u06F4",
                    "\\u0665=>\\u06F5",
                    "\\u0666=>\\u06F6",
                    "\\u0667=>\\u06F7",
                    "\\u0668=>\\u06F8",
                    "\\u0669=>\\u06F9",
                ],
            },
            "zwnj_handler": {
                "type": "mapping",
                "mappings": [
                    # Zero-width non-joiner → space (allows compound-word splitting)
                    "\\u200C=> ",
                ],
            },
        },
        "filter": {
            "persian_stop": {
                "type": "stop",
                "stopwords": "_persian_",
            },
            "persian_normalization": {
                "type": "persian_normalization",
            },
            "arabic_normalization": {
                "type": "arabic_normalization",
            },
        },
        "analyzer": {
            "persian_analyzer": {
                "type": "custom",
                "char_filter": ["arabic_to_persian", "zwnj_handler"],
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "arabic_normalization",
                    "persian_normalization",
                    "persian_stop",
                ],
            },
            "persian_autocomplete": {
                "type": "custom",
                "char_filter": ["arabic_to_persian", "zwnj_handler"],
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "arabic_normalization",
                    "persian_normalization",
                    "edge_ngram_filter",
                ],
            },
        },
        "filter": {
            "persian_stop": {
                "type": "stop",
                "stopwords": "_persian_",
            },
            "persian_normalization": {
                "type": "persian_normalization",
            },
            "arabic_normalization": {
                "type": "arabic_normalization",
            },
            "edge_ngram_filter": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 15,
            },
        },
    },
}


PRODUCT_INDEX_MAPPING: dict[str, Any] = {
    "properties": {
        "id": {"type": "keyword"},
        "name": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {
                "keyword": {"type": "keyword"},
                "autocomplete": {
                    "type": "text",
                    "analyzer": "persian_autocomplete",
                    "search_analyzer": "persian_analyzer",
                },
            },
        },
        "description": {
            "type": "text",
            "analyzer": "persian_analyzer",
        },
        "short_description": {
            "type": "text",
            "analyzer": "persian_analyzer",
        },
        "category_id": {"type": "keyword"},
        "category_name": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "category_slug": {"type": "keyword"},
        "brand_id": {"type": "keyword"},
        "brand_name": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "brand_slug": {"type": "keyword"},
        "price": {"type": "long"},
        "compare_at_price": {"type": "long"},
        "rating_average": {"type": "float"},
        "rating_count": {"type": "integer"},
        "tags": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "attributes": {
            "type": "nested",
            "properties": {
                "name": {"type": "keyword"},
                "value": {"type": "keyword"},
            },
        },
        "slug": {"type": "keyword"},
        "sku": {"type": "keyword"},
        "image_url": {"type": "keyword", "index": False},
        "is_active": {"type": "boolean"},
        "is_featured": {"type": "boolean"},
        "status": {"type": "keyword"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    },
}


class ElasticsearchService:
    """Manages the async Elasticsearch connection and product index."""

    def __init__(self) -> None:
        self._client: AsyncElasticsearch | None = None
        self._settings = get_settings()
        self._index_name = f"{self._settings.ELASTICSEARCH_INDEX_PREFIX}products"

    # ── Connection lifecycle ──────────────────────────────────────────

    async def connect(self) -> AsyncElasticsearch:
        """Create or return the async Elasticsearch client."""
        if self._client is None:
            self._client = AsyncElasticsearch(
                hosts=[str(self._settings.ELASTICSEARCH_URL)],
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True,
            )
            info = await self._client.info()
            await logger.ainfo(
                "elasticsearch_connected",
                cluster_name=info.get("cluster_name"),
                version=info.get("version", {}).get("number"),
            )
        return self._client

    async def disconnect(self) -> None:
        """Close the Elasticsearch client transport."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            await logger.ainfo("elasticsearch_disconnected")

    @property
    def client(self) -> AsyncElasticsearch:
        """Return the active client or raise."""
        if self._client is None:
            raise RuntimeError(
                "Elasticsearch client not connected. Call connect() first."
            )
        return self._client

    @property
    def index_name(self) -> str:
        return self._index_name

    # ── Index management ──────────────────────────────────────────────

    async def create_product_index(self, *, force: bool = False) -> None:
        """Create the product search index with Persian analyser.

        Parameters
        ----------
        force:
            If ``True``, delete the existing index before recreating it.
        """
        client = await self.connect()

        if force:
            try:
                await client.indices.delete(index=self._index_name)
                await logger.ainfo(
                    "elasticsearch_index_deleted", index=self._index_name
                )
            except ESNotFoundError:
                pass

        exists = await client.indices.exists(index=self._index_name)
        if not exists:
            await client.indices.create(
                index=self._index_name,
                body={
                    "settings": {
                        **PERSIAN_ANALYSIS_SETTINGS,
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    },
                    "mappings": PRODUCT_INDEX_MAPPING,
                },
            )
            await logger.ainfo(
                "elasticsearch_index_created", index=self._index_name
            )
        else:
            await logger.ainfo(
                "elasticsearch_index_exists", index=self._index_name
            )

    async def delete_index(self) -> None:
        """Delete the product search index."""
        client = await self.connect()
        try:
            await client.indices.delete(index=self._index_name)
            await logger.ainfo(
                "elasticsearch_index_deleted", index=self._index_name
            )
        except ESNotFoundError:
            await logger.awarning(
                "elasticsearch_index_not_found", index=self._index_name
            )

    # ── Document operations ───────────────────────────────────────────

    async def index_document(
        self, doc_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Index a single document."""
        client = await self.connect()
        result = await client.index(
            index=self._index_name,
            id=doc_id,
            body=body,
        )
        await logger.adebug("elasticsearch_doc_indexed", doc_id=doc_id)
        return result

    async def bulk_index(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        """Perform bulk indexing operations."""
        from elasticsearch.helpers import async_bulk

        client = await self.connect()
        success, errors = await async_bulk(
            client,
            actions,
            raise_on_error=False,
            stats_only=False,
        )
        await logger.ainfo(
            "elasticsearch_bulk_index",
            success=success,
            errors=len(errors) if isinstance(errors, list) else errors,
        )
        return {"success": success, "errors": errors}

    async def delete_document(self, doc_id: str) -> None:
        """Delete a single document by ID."""
        client = await self.connect()
        try:
            await client.delete(index=self._index_name, id=doc_id)
            await logger.adebug("elasticsearch_doc_deleted", doc_id=doc_id)
        except ESNotFoundError:
            await logger.awarning(
                "elasticsearch_doc_not_found_for_delete", doc_id=doc_id
            )

    async def search(self, body: dict[str, Any]) -> dict[str, Any]:
        """Execute a search query and return raw ES response."""
        client = await self.connect()
        return await client.search(index=self._index_name, body=body)

    async def count(self, body: dict[str, Any] | None = None) -> int:
        """Return the number of documents matching a query."""
        client = await self.connect()
        result = await client.count(
            index=self._index_name,
            body=body or {"query": {"match_all": {}}},
        )
        return result["count"]


# ── Module-level singleton instance ───────────────────────────────────────

_es_service: ElasticsearchService | None = None


def get_elasticsearch_service() -> ElasticsearchService:
    """Return (and lazily create) the module-level ElasticsearchService."""
    global _es_service  # noqa: PLW0603
    if _es_service is None:
        _es_service = ElasticsearchService()
    return _es_service
