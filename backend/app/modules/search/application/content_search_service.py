"""Content storefront search: published blog posts and CMS pages.

Gap item 8 — storefront search used to be products-only, so a customer
looking for the "how to choose a woolen shawl" buying guide got nothing.
This service maintains two Elasticsearch indices built from the shared
Persian analyser (``{prefix}blog_posts`` and ``{prefix}cms_pages``), searches
them with one merged query, and powers "did you mean" phrase suggestions.

Source-of-truth rules
---------------------
ADR-009 keeps PostgreSQL as the source of truth and Elasticsearch as a
read-only projection for storefront search. Only *publicly visible* content
is indexed: ``status == PUBLISHED``, not soft-deleted, and (for posts, which
have the WordPress-parity visibility control) ``visibility == PUBLIC`` —
private and password-protected posts never leak into public search.

Failure model
-------------
Like every search surface here, Elasticsearch being unreachable degrades
instead of erroring: content search falls back to PostgreSQL ``ILIKE``
queries (the :mod:`admin_search_service` style), tagging the response with
``degraded=True`` so callers can tell relevance-ranked results from a
substring scan. Indexing helpers are best-effort — a downed ES logs a
warning and returns rather than breaking a blog save.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.core.config.settings import get_settings
from app.modules.search.application.admin_search_service import escape_like
from app.modules.search.infrastructure.elasticsearch_client import (
    PERSIAN_ANALYSIS_SETTINGS,
    ElasticsearchService,
    get_elasticsearch_service,
)
from app.modules.search.schemas.content import (
    ContentSearchResponse,
    ContentSearchResult,
    ContentSuggestion,
    ContentSuggestResponse,
    ContentType,
)
from app.modules.search.schemas.search import ReindexResponse

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Document type discriminator values (mirrors ContentSearchResult.type).
CONTENT_TYPE_POST: ContentType = "post"
CONTENT_TYPE_PAGE: ContentType = "page"

# ── Index mapping (shared by blog and CMS indices) ────────────────────────

#: Persian-analyzer-backed mapping for content documents. ``title.suggestion``
#: is stop-word free (``persian_suggest``) so the phrase suggester can build
#: candidate n-grams for "did you mean".
CONTENT_INDEX_MAPPING: dict[str, Any] = {
    "properties": {
        "id": {"type": "keyword"},
        "type": {"type": "keyword"},
        "title": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {
                "keyword": {"type": "keyword"},
                "autocomplete": {
                    "type": "text",
                    "analyzer": "persian_autocomplete",
                    "search_analyzer": "persian_analyzer",
                },
                "suggestion": {"type": "text", "analyzer": "persian_suggest"},
            },
        },
        "slug": {"type": "keyword"},
        "excerpt": {"type": "text", "analyzer": "persian_analyzer"},
        "body": {"type": "text", "analyzer": "persian_analyzer"},
        "locale": {"type": "keyword"},
        "category": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "category_slug": {"type": "keyword"},
        "tags": {
            "type": "text",
            "analyzer": "persian_analyzer",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "published_at": {"type": "date"},
        "is_featured": {"type": "boolean"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
        # Written for blog posts so a post later switched to private /
        # password-protected can be excluded even before a full reindex
        # replaces its stored document (a stale PUBLIC-era document would
        # otherwise keep serving the old body through search snippets).
        "visibility": {"type": "keyword"},
    },
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")


def strip_html(raw: str | None) -> str:
    """Reduce an HTML string (CMS ``body_html``) to plain text. Pure.

    Pages store rich HTML; indexing markup tags as search terms pollutes the
    index. Tags are dropped and runs of whitespace collapsed — no HTML parser
    needed for search purposes.
    """
    if not raw:
        return ""
    return _MULTI_SPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", raw)).strip()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class ContentSearchService:
    """Maintains and searches the blog-post and CMS-page search indices."""

    def __init__(self, es: ElasticsearchService | None = None) -> None:
        self._es = es or get_elasticsearch_service()
        self._settings = get_settings()
        self._indices_ready = False

    # ── Index names ───────────────────────────────────────────────────

    @property
    def blog_index_name(self) -> str:
        return f"{self._settings.ELASTICSEARCH_INDEX_PREFIX}blog_posts"

    @property
    def cms_index_name(self) -> str:
        return f"{self._settings.ELASTICSEARCH_INDEX_PREFIX}cms_pages"

    def _targets(self, content_type: str | None) -> str:
        """Comma-separated index list for a search (single index when typed)."""
        if content_type == CONTENT_TYPE_POST:
            return self.blog_index_name
        if content_type == CONTENT_TYPE_PAGE:
            return self.cms_index_name
        return f"{self.blog_index_name},{self.cms_index_name}"

    # ── Index management ──────────────────────────────────────────────

    async def create_indices(self, *, force: bool = False) -> None:
        """Create the blog and CMS indices with the shared Persian analyser.

        Raises when Elasticsearch is unreachable — callers decide between
        failing loudly (reindex commands) and degrading (search paths).
        """
        await self._es.create_index(
            self.blog_index_name,
            CONTENT_INDEX_MAPPING,
            settings=PERSIAN_ANALYSIS_SETTINGS,
            force=force,
        )
        await self._es.create_index(
            self.cms_index_name,
            CONTENT_INDEX_MAPPING,
            settings=PERSIAN_ANALYSIS_SETTINGS,
            force=force,
        )

    async def _ensure_indices(self, *, force: bool = False) -> None:
        """Idempotently make sure both content indices exist."""
        if self._indices_ready and not force:
            return
        await self.create_indices(force=force)
        self._indices_ready = True

    # ── Document builders ─────────────────────────────────────────────

    @staticmethod
    def blog_post_to_doc(post: Any) -> dict[str, Any]:
        """Convert a BlogPost ORM row into an indexable document.

        A password-protected post is indexed title-only: its body/excerpt
        would otherwise be readable through search results, which is exactly
        what the password exists to prevent. The title stays because the
        storefront listing (and its password form) is public.
        """
        protected = getattr(post.visibility, "value", str(post.visibility)) == "password"
        return {
            "id": str(post.id),
            "type": CONTENT_TYPE_POST,
            "title": post.title,
            "slug": post.slug,
            "excerpt": "" if protected else (post.excerpt or ""),
            "body": "" if protected else strip_html(post.content),
            "locale": post.locale or "fa",
            "category": post.category.name if post.category else None,
            "category_slug": post.category.slug if post.category else None,
            "tags": [pt.tag.name for pt in (post.post_tags or []) if pt.tag],
            "published_at": _iso(post.published_at),
            "is_featured": bool(post.is_featured),
            "visibility": getattr(post.visibility, "value", str(post.visibility or "public")),
            "created_at": _iso(post.created_at),
            "updated_at": _iso(post.updated_at),
        }

    @staticmethod
    def cms_page_to_doc(page: Any) -> dict[str, Any]:
        """Convert a CmsPage ORM row into an indexable document."""
        return {
            "id": str(page.id),
            "type": CONTENT_TYPE_PAGE,
            "title": page.title,
            "slug": page.slug,
            "excerpt": page.excerpt or "",
            "body": strip_html(page.body_html),
            "locale": page.locale or "fa",
            "category": None,
            "category_slug": None,
            "tags": [],
            "published_at": _iso(page.published_at),
            "is_featured": False,
            "created_at": _iso(page.created_at),
            "updated_at": _iso(page.updated_at),
        }

    # ── Single-document upsert / delete (best-effort) ─────────────────

    async def index_blog_post(self, post: Any) -> None:
        """Upsert one blog post into the blog index; never raises."""
        try:
            await self._ensure_indices()
            await self._es.index_document(
                str(post.id), self.blog_post_to_doc(post), index_name=self.blog_index_name
            )
        except Exception as exc:
            await logger.awarning(
                "content_index_blog_post_failed", post_id=str(post.id), error=str(exc)
            )

    async def index_cms_page(self, page: Any) -> None:
        """Upsert one CMS page into the CMS index; never raises."""
        try:
            await self._ensure_indices()
            await self._es.index_document(
                str(page.id), self.cms_page_to_doc(page), index_name=self.cms_index_name
            )
        except Exception as exc:
            await logger.awarning(
                "content_index_cms_page_failed", page_id=str(page.id), error=str(exc)
            )

    async def remove_blog_post(self, post_id: str | uuid.UUID) -> None:
        """Remove a blog post from the blog index; never raises."""
        try:
            await self._es.delete_document(str(post_id), index_name=self.blog_index_name)
        except Exception as exc:
            await logger.awarning(
                "content_remove_blog_post_failed", post_id=str(post_id), error=str(exc)
            )

    async def remove_cms_page(self, page_id: str | uuid.UUID) -> None:
        """Remove a CMS page from the CMS index; never raises."""
        try:
            await self._es.delete_document(str(page_id), index_name=self.cms_index_name)
        except Exception as exc:
            await logger.awarning(
                "content_remove_cms_page_failed", page_id=str(page_id), error=str(exc)
            )

    # ── Full reindex ──────────────────────────────────────────────────

    async def reindex_blog(self, db: AsyncSession, *, force: bool = False) -> ReindexResponse:
        """Re-index publicly visible published blog posts.

        Public and password-protected posts are indexed (the latter
        title-only — see ``blog_post_to_doc``); private, unpublished, and
        trashed posts are **removed** from the index, because a reindex only
        upserts: a post switched to private after being indexed would
        otherwise keep serving its old public document through search.
        """
        from app.modules.blog.domain.models import (
            BlogPost,
            BlogPostStatus,
            BlogPostTag,
            PostVisibility,
        )

        try:
            await self._ensure_indices(force=force)
        except Exception as exc:
            await logger.awarning("content_reindex_es_unreachable", error=str(exc))
            return ReindexResponse(
                success=False,
                indexed=0,
                errors=0,
                message=f"Elasticsearch unreachable: {exc}",
            )

        stmt = (
            select(BlogPost)
            .options(
                joinedload(BlogPost.category),
                joinedload(BlogPost.post_tags).joinedload(BlogPostTag.tag),
            )
            .where(
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
                BlogPost.visibility.in_(
                    [PostVisibility.PUBLIC, PostVisibility.PASSWORD]
                ),
            )
        )
        posts = (await db.execute(stmt)).unique().scalars().all()
        result = await self._bulk_flush(
            ((self.blog_post_to_doc(p), self.blog_index_name) for p in posts),
            label="blog posts",
        )

        # Purge documents for posts that must not be findable. Best-effort:
        # a purge failure must not fail the reindex (the stored document is
        # already masked when the post was re-indexed with new visibility,
        # and search filters by ``visibility`` as a second layer).
        purge_stmt = select(BlogPost.id).where(
            or_(
                BlogPost.deleted_at.is_not(None),
                BlogPost.status != BlogPostStatus.PUBLISHED,
                BlogPost.visibility == PostVisibility.PRIVATE,
            )
        )
        purge_ids = (await db.execute(purge_stmt)).scalars().all()
        for post_id in purge_ids:
            await self.remove_blog_post(post_id)

        return result

    async def reindex_cms(self, db: AsyncSession, *, force: bool = False) -> ReindexResponse:
        """Re-index every published, non-trashed CMS page."""
        from app.modules.content.domain.models import CmsPage, PageStatus

        try:
            await self._ensure_indices(force=force)
        except Exception as exc:
            await logger.awarning("content_reindex_es_unreachable", error=str(exc))
            return ReindexResponse(
                success=False,
                indexed=0,
                errors=0,
                message=f"Elasticsearch unreachable: {exc}",
            )

        stmt = select(CmsPage).where(
            CmsPage.status == PageStatus.PUBLISHED,
            CmsPage.deleted_at.is_(None),
        )
        pages = (await db.execute(stmt)).scalars().all()
        return await self._bulk_flush(
            ((self.cms_page_to_doc(p), self.cms_index_name) for p in pages),
            label="CMS pages",
        )

    async def reindex_all(self, db: AsyncSession, *, force: bool = False) -> ReindexResponse:
        """Re-index both content indices in one pass."""
        blog = await self.reindex_blog(db, force=force)
        cms = await self.reindex_cms(db, force=force)
        return ReindexResponse(
            success=blog.success and cms.success,
            indexed=blog.indexed + cms.indexed,
            errors=blog.errors + cms.errors,
            message=f"{blog.message}; {cms.message}",
        )

    async def _bulk_flush(self, docs_and_indexes: Any, *, label: str) -> ReindexResponse:
        """Bulk-index ``(_source, index)`` pairs; degrade on ES failure."""
        docs = list(docs_and_indexes)
        if not docs:
            return ReindexResponse(
                success=True, indexed=0, errors=0, message=f"No {label} to index"
            )
        actions = [{"_index": index, "_id": doc["id"], "_source": doc} for doc, index in docs]
        try:
            bulk = await self._es.bulk_index(actions)
        except Exception as exc:
            await logger.awarning("content_reindex_bulk_failed", label=label, error=str(exc))
            return ReindexResponse(
                success=False,
                indexed=0,
                errors=len(actions),
                message=f"Elasticsearch unreachable while indexing {label}: {exc}",
            )
        success_count = int(bulk.get("success", 0))
        error_list = bulk.get("errors", [])
        error_count = len(error_list) if isinstance(error_list, list) else 0
        return ReindexResponse(
            success=error_count == 0,
            indexed=success_count,
            errors=error_count,
            message=f"Indexed {success_count} {label} with {error_count} errors",
        )

    # ── Public search ─────────────────────────────────────────────────

    async def search_content(
        self,
        db: AsyncSession | None,
        query: str,
        *,
        content_type: str | None = None,
        locale: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> ContentSearchResponse:
        """Search published blog posts and CMS pages.

        ``content_type`` restricts the search to ``post`` or ``page``.
        Falls back to PostgreSQL ILIKE over the source tables when
        Elasticsearch is unreachable (``degraded=True``).
        """
        cleaned = (query or "").strip()
        if not cleaned:
            return ContentSearchResponse(query=cleaned, page=page, size=size)

        try:
            await self._ensure_indices()
        except Exception as exc:
            await logger.awarning("content_search_ensure_indices_failed", error=str(exc))

        body: dict[str, Any] = {
            "query": self._build_query(cleaned, locale),
            "from": (page - 1) * size,
            "size": size,
            "sort": [
                {"_score": {"order": "desc"}},
                {"published_at": {"order": "desc", "missing": "_last"}},
            ],
        }
        targets = self._targets(content_type)

        try:
            raw = await self._es.search(body, index_name=targets)
        except Exception as exc:
            await logger.awarning("content_search_es_failed", error=str(exc), query=cleaned)
            return await self._fallback_search(
                db, cleaned, content_type=content_type, locale=locale, page=page, size=size
            )

        hits = raw.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        results = [self._parse_hit(hit) for hit in hits.get("hits", [])]
        did_you_mean = await self._phrase_suggest(cleaned, targets)
        return ContentSearchResponse(
            results=results,
            total=total,
            page=page,
            size=size,
            total_pages=math.ceil(total / size) if size > 0 else 0,
            query=cleaned,
            did_you_mean=did_you_mean,
        )

    async def suggest_content(
        self,
        query: str,
        *,
        size: int = 5,
        db: AsyncSession | None = None,
    ) -> ContentSuggestResponse:
        """Autocomplete over published content titles (posts and pages)."""
        cleaned = (query or "").strip()
        if not cleaned:
            return ContentSuggestResponse(query=cleaned)

        try:
            await self._ensure_indices()
        except Exception as exc:
            await logger.awarning("content_suggest_ensure_indices_failed", error=str(exc))

        body: dict[str, Any] = {
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": cleaned,
                                "fields": [
                                    "title.autocomplete^3",
                                    "title.keyword^2",
                                    "tags.keyword",
                                    "category.keyword",
                                ],
                                "type": "best_fields",
                            },
                        },
                    ],
                    # Same guard as _build_query: a stale document for a post
                    # switched to private must not autocomplete either.
                    "must_not": [{"term": {"visibility": "private"}}],
                },
            },
            "_source": ["id", "type", "title", "slug"],
        }

        try:
            raw = await self._es.search(body, index_name=self._targets(None))
            hits = raw.get("hits", {}).get("hits", [])
        except Exception as exc:
            await logger.awarning("content_suggest_es_failed", error=str(exc), query=cleaned)
            if db is not None:
                return await self._fallback_suggest(db, cleaned, size)
            return ContentSuggestResponse(suggestions=[], query=cleaned)

        suggestions = [
            ContentSuggestion(
                text=hit["_source"].get("title", ""),
                type=hit["_source"].get("type", CONTENT_TYPE_POST),
                slug=hit["_source"].get("slug"),
                id=hit["_source"].get("id"),
                score=hit.get("_score"),
            )
            for hit in hits
        ]
        return ContentSuggestResponse(suggestions=suggestions, query=cleaned)

    # ── "Did you mean" ────────────────────────────────────────────────

    async def _phrase_suggest(self, query: str, index_name: str) -> str | None:
        """Closest phrase correction from the ES phrase suggester.

        A separate, optional round trip so a suggester problem (index missing
        the ``title.suggestion`` subfield, ES blip) can never degrade the
        main results — it only costs the suggestion.
        """
        cleaned = query.strip()
        if not cleaned:
            return None
        body: dict[str, Any] = {
            "size": 0,
            "suggest": {
                "text": cleaned,
                "did_you_mean": {
                    "phrase": {
                        "field": "title.suggestion",
                        "size": 1,
                        "gram_size": 3,
                        "max_errors": 2,
                    },
                },
            },
        }
        try:
            raw = await self._es.search(body, index_name=index_name)
        except Exception as exc:
            await logger.awarning("content_phrase_suggest_failed", error=str(exc))
            return None
        entries = raw.get("suggest", {}).get("did_you_mean", [])
        if not entries:
            return None
        options = entries[0].get("options", []) if isinstance(entries[0], dict) else []
        for option in options:
            text = option.get("text")
            if text and text.strip().lower() != cleaned.lower():
                return text
        return None

    # ── Query building / parsing ──────────────────────────────────────

    @staticmethod
    def _build_query(query: str, locale: str | None) -> dict[str, Any]:
        """Elasticsearch bool query: fuzzy multi-match + locale filter.

        Private posts are excluded outright (defence in depth: the reindex
        purges them and masks password-protected bodies, but a stale
        document from before either ran must still never surface).
        """
        filter_clauses: list[dict[str, Any]] = []
        if locale:
            filter_clauses.append({"term": {"locale": locale}})
        return {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "excerpt", "body", "category^2", "tags^2"],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                            "prefix_length": 2,
                        },
                    },
                ],
                "must_not": [{"term": {"visibility": "private"}}],
                "filter": filter_clauses,
            },
        }

    @staticmethod
    def _parse_hit(hit: dict[str, Any]) -> ContentSearchResult:
        """Parse a single ES hit into a ContentSearchResult."""
        source = hit.get("_source", {})
        published_at: datetime | None = None
        raw_published = source.get("published_at")
        if raw_published:
            try:
                published_at = datetime.fromisoformat(str(raw_published))
            except ValueError:
                published_at = None
        return ContentSearchResult(
            id=source.get("id", ""),
            type=source.get("type", CONTENT_TYPE_POST),
            title=source.get("title", ""),
            slug=source.get("slug", ""),
            excerpt=source.get("excerpt") or None,
            locale=source.get("locale"),
            category=source.get("category"),
            category_slug=source.get("category_slug"),
            tags=source.get("tags", []) or [],
            published_at=published_at,
            is_featured=bool(source.get("is_featured", False)),
            score=hit.get("_score"),
        )

    # ── PostgreSQL ILIKE fallback (Elasticsearch unreachable) ─────────

    async def _fallback_search(
        self,
        db: AsyncSession | None,
        term: str,
        *,
        content_type: str | None,
        locale: str | None,
        page: int,
        size: int,
    ) -> ContentSearchResponse:
        """ILIKE scan over published content, ordered by recency.

        Mirrors the admin global search style: escaped LIKE patterns through
        bound parameters, no ES dependency. Relevance scoring is unavailable,
        so the response is flagged ``degraded``.
        """
        if db is None:
            return ContentSearchResponse(query=term, page=page, size=size, degraded=True)

        include_posts = content_type in (None, CONTENT_TYPE_POST)
        include_pages = content_type in (None, CONTENT_TYPE_PAGE)
        limit = page * size
        pattern = f"%{escape_like(term)}%"

        results: list[ContentSearchResult] = []
        total = 0

        if include_posts:
            try:
                post_total, posts = await self._fallback_posts(db, pattern, locale, limit)
                total += post_total
                results.extend(self._post_hit(p) for p in posts)
            except Exception as exc:
                await logger.awarning("content_fallback_posts_failed", error=str(exc))

        if include_pages:
            try:
                page_total, pages = await self._fallback_pages(db, pattern, locale, limit)
                total += page_total
                results.extend(self._page_hit(p) for p in pages)
            except Exception as exc:
                await logger.awarning("content_fallback_pages_failed", error=str(exc))

        results.sort(
            key=lambda r: r.published_at.timestamp() if r.published_at else float("-inf"),
            reverse=True,
        )
        window = results[(page - 1) * size : page * size]
        return ContentSearchResponse(
            results=window,
            total=total,
            page=page,
            size=size,
            total_pages=math.ceil(total / size) if size > 0 else 0,
            query=term,
            degraded=True,
        )

    @staticmethod
    async def _fallback_posts(
        db: AsyncSession, pattern: str, locale: str | None, limit: int
    ) -> tuple[int, list[Any]]:
        """Published public posts matching the ILIKE pattern, newest first.

        Password-protected posts match on **title only** — matching their
        body/excerpt would expose protected content through search snippets,
        the same leak the ES document builder closes. Private posts are
        excluded outright.
        """
        from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility

        conditions = [
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            or_(
                and_(
                    BlogPost.visibility == PostVisibility.PUBLIC,
                    or_(
                        BlogPost.title.ilike(pattern, escape="\\"),
                        BlogPost.excerpt.ilike(pattern, escape="\\"),
                        BlogPost.content.ilike(pattern, escape="\\"),
                    ),
                ),
                and_(
                    BlogPost.visibility == PostVisibility.PASSWORD,
                    BlogPost.title.ilike(pattern, escape="\\"),
                ),
            ),
        ]
        if locale:
            conditions.append(BlogPost.locale == locale)

        count_stmt = select(func.count()).select_from(BlogPost).where(*conditions)
        post_total = int((await db.execute(count_stmt)).scalar_one())

        stmt = (
            select(BlogPost)
            .options(joinedload(BlogPost.category))
            .where(*conditions)
            .order_by(BlogPost.published_at.desc().nullslast())
            .limit(limit)
        )
        posts = list((await db.execute(stmt)).unique().scalars().all())
        return post_total, posts

    @staticmethod
    async def _fallback_pages(
        db: AsyncSession, pattern: str, locale: str | None, limit: int
    ) -> tuple[int, list[Any]]:
        """Published, non-trashed pages matching the ILIKE pattern."""
        from app.modules.content.domain.models import CmsPage, PageStatus

        conditions = [
            CmsPage.status == PageStatus.PUBLISHED,
            CmsPage.deleted_at.is_(None),
            or_(
                CmsPage.title.ilike(pattern, escape="\\"),
                CmsPage.excerpt.ilike(pattern, escape="\\"),
                CmsPage.body_html.ilike(pattern, escape="\\"),
            ),
        ]
        if locale:
            conditions.append(CmsPage.locale == locale)

        count_stmt = select(func.count()).select_from(CmsPage).where(*conditions)
        page_total = int((await db.execute(count_stmt)).scalar_one())

        stmt = (
            select(CmsPage)
            .where(*conditions)
            .order_by(CmsPage.published_at.desc().nullslast())
            .limit(limit)
        )
        pages = list((await db.execute(stmt)).scalars().all())
        return page_total, pages

    def _post_hit(self, post: Any) -> ContentSearchResult:
        """ContentSearchResult straight from a fallback BlogPost row."""
        doc = self.blog_post_to_doc(post)
        return self._parse_hit({"_source": doc})

    def _page_hit(self, page_row: Any) -> ContentSearchResult:
        """ContentSearchResult straight from a fallback CmsPage row."""
        doc = self.cms_page_to_doc(page_row)
        return self._parse_hit({"_source": doc})

    async def _fallback_suggest(
        self, db: AsyncSession, term: str, size: int
    ) -> ContentSuggestResponse:
        """Title-prefix ILIKE suggestions over published content."""
        suggestions: list[ContentSuggestion] = []
        pattern = f"%{escape_like(term)}%"
        try:
            from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility

            stmt = (
                select(BlogPost)
                .where(
                    BlogPost.status == BlogPostStatus.PUBLISHED,
                    BlogPost.deleted_at.is_(None),
                    BlogPost.visibility == PostVisibility.PUBLIC,
                    BlogPost.title.ilike(pattern, escape="\\"),
                )
                .order_by(BlogPost.published_at.desc().nullslast())
                .limit(size)
            )
            for post in (await db.execute(stmt)).scalars().all():
                suggestions.append(
                    ContentSuggestion(
                        text=post.title,
                        type=CONTENT_TYPE_POST,
                        slug=post.slug,
                        id=str(post.id),
                    )
                )

            from app.modules.content.domain.models import CmsPage, PageStatus

            stmt = (
                select(CmsPage)
                .where(
                    CmsPage.status == PageStatus.PUBLISHED,
                    CmsPage.deleted_at.is_(None),
                    CmsPage.title.ilike(pattern, escape="\\"),
                )
                .order_by(CmsPage.published_at.desc().nullslast())
                .limit(size)
            )
            for page_row in (await db.execute(stmt)).scalars().all():
                suggestions.append(
                    ContentSuggestion(
                        text=page_row.title,
                        type=CONTENT_TYPE_PAGE,
                        slug=page_row.slug,
                        id=str(page_row.id),
                    )
                )
        except Exception as exc:
            await logger.awarning("content_fallback_suggest_failed", error=str(exc))
            return ContentSuggestResponse(suggestions=[], query=term)

        return ContentSuggestResponse(suggestions=suggestions[:size], query=term)


# ── Module-level convenience ──────────────────────────────────────────────

_content_search_service: ContentSearchService | None = None


def get_content_search_service() -> ContentSearchService:
    """Return (and lazily create) the module-level ContentSearchService."""
    global _content_search_service
    if _content_search_service is None:
        _content_search_service = ContentSearchService()
    return _content_search_service
