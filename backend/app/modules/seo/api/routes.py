"""REST API routes for the SEO module.

Provides endpoints for fetching and managing per-resource SEO metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Runtime import, not TYPE_CHECKING: FastAPI evaluates the `db: AsyncSession`
# annotations with get_type_hints at boot. A name it cannot resolve makes it
# classify the parameter by fallback rules rather than as the dependency —
# the same failure that left the email-template preview reading its body from
# the query string. See scripts/check_endpoint_annotations.py.
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions
from app.modules.blog.domain.models import BlogPost
from app.modules.catalog.infrastructure.catalog_repository import ProductRepository
from app.modules.seo.application.seo_analyzer import SeoAnalyzer, keyword_in_text
from app.modules.seo.application.seo_service import SEOService
from app.modules.seo.domain.models import RedirectRule, SEOMetadata
from app.modules.seo.schemas.seo import (
    SeoAnalysisRequest,
    SeoAnalysisResponse,
    SEOMetadataCreate,
    SEOMetadataResponse,
)

router = APIRouter()

admin_router = APIRouter(
    prefix="/admin/seo",
    tags=["admin-seo"],
)

_require_seo_write = Depends(RequirePermissions("seo:write"))


# ============================================================================
# SEO Scoring Engine Endpoints (Rank Math / Yoast for Iran Market)
# ============================================================================


@router.post(
    "/analyze",
    response_model=SeoAnalysisResponse,
    summary="Analyze SEO score for content",
    description=(
        "Automated 0-100 SEO scoring engine similar to Rank Math / Yoast for the Iranian market. "
        "Evaluates title, content, focus keyword, slug, meta description, media, and links. "
        "Returns complete score (0-100), grade (عالی, متوسط و نیازمند بهبود, ضعیف), "
        "checklist, and recommendations."
    ),
)
async def analyze_seo(
    data: SeoAnalysisRequest,
) -> SeoAnalysisResponse:
    """Analyze provided metadata and content for SEO scoring."""
    analyzer = SeoAnalyzer()
    return analyzer.analyze(
        title=data.title,
        content=data.content,
        focus_keyword=data.focus_keyword,
        slug=data.slug,
        meta_description=data.meta_description,
        images=data.images,
        internal_links=data.internal_links,
        images_count=data.images_count,
        has_image_alt=data.has_image_alt,
        internal_links_count=data.internal_links_count,
    )


@router.get(
    "/indexnow/{key}.txt",
    summary="IndexNow key file (public, protocol requirement)",
    include_in_schema=False,
)
async def indexnow_key_file(key: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Serve the IndexNow ownership file at /{key}.txt.

    IndexNow requires the key to be fetchable at ``https://host/{key}.txt``
    before it accepts submissions. The key is public by design — it is an
    ownership token, not a secret. A wrong key path 404s (plain text), which
    is exactly what the protocol expects.
    """
    from app.modules.seo.application.indexing_service import KEY_OPTION
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    stored = await SiteOptionsService.get(db, KEY_OPTION)
    if not stored or key != stored:
        return Response(content="not found", status_code=404, media_type="text/plain")
    return Response(content=stored, media_type="text/plain; charset=utf-8")


@router.get(
    "/products/{id}/score",
    response_model=SeoAnalysisResponse,
    summary="Analyze SEO score for a product",
    description=(
        "Fetches product, extracts description and tags as keyword, runs analysis, returns score."
    ),
)
async def get_product_seo_score(
    id: str,  # noqa: A002  # API parameter name is the public contract
    focus_keyword: str | None = Query(None, description="Optional custom focus keyword override"),
    db: AsyncSession = Depends(get_db),
) -> SeoAnalysisResponse:
    """Fetch product by ID or slug, extract fields, and evaluate SEO score."""
    repo = ProductRepository(db)
    product = None

    try:
        product_uuid = uuid.UUID(id)
        product = await repo.get_by_id(product_uuid, eager=True)
    except (ValueError, AttributeError):
        pass

    if not product:
        product = await repo.get_by_slug(id)

    if not product:
        raise NotFoundError("Product", f"Product '{id}' not found")

    # Extract tags
    tag_names: list[str] = []
    if product.product_tags:
        for pt in product.product_tags:
            if pt.tag and pt.tag.name:
                tag_names.append(pt.tag.name)

    # Determine focus keyword: query param override > tags > meta_keywords > product name
    resolved_keyword = focus_keyword
    if not resolved_keyword:
        if tag_names:
            resolved_keyword = tag_names[0]
        elif product.meta_keywords:
            resolved_keyword = product.meta_keywords.split(",")[0].strip()
        else:
            resolved_keyword = product.name

    # Build image metadata
    images_data: list[dict[str, str | None]] = []
    has_matching_alt = False
    if product.images:
        for img in product.images:
            images_data.append({"url": img.url, "alt": img.alt_text})
            if img.alt_text and keyword_in_text(resolved_keyword, img.alt_text):
                has_matching_alt = True

    title = product.seo_title or product.name
    content = product.description or product.short_description or ""
    meta_desc = product.seo_description or product.short_description or ""

    analyzer = SeoAnalyzer()
    return analyzer.analyze(
        title=title,
        content=content,
        focus_keyword=resolved_keyword,
        slug=product.slug,
        meta_description=meta_desc,
        images=images_data,
        images_count=len(product.images) if product.images else 0,
        has_image_alt=has_matching_alt,
    )


@router.get(
    "/blog/{slug}/score",
    response_model=SeoAnalysisResponse,
    summary="Analyze SEO score for a blog post",
    description="Fetches blog post by slug, runs SEO analysis, returns score.",
)
async def get_blog_post_seo_score(
    slug: str,
    focus_keyword: str | None = Query(None, description="Optional custom focus keyword override"),
    db: AsyncSession = Depends(get_db),
) -> SeoAnalysisResponse:
    """Fetch blog post by slug, check SEO metadata, and calculate SEO score."""
    stmt = select(BlogPost).options(selectinload(BlogPost.category)).where(BlogPost.slug == slug)
    post = (await db.execute(stmt)).scalar_one_or_none()
    if not post:
        raise NotFoundError("BlogPost", f"Blog post '{slug}' not found")

    # Retrieve custom SEOMetadata if saved
    seo_stmt = select(SEOMetadata).where(
        SEOMetadata.resource_type == "blog_post",
        SEOMetadata.resource_id == post.id,
    )
    seo_meta = (await db.execute(seo_stmt)).scalar_one_or_none()

    # Determine focus keyword
    resolved_keyword = focus_keyword
    if not resolved_keyword:
        if post.category and post.category.name:
            resolved_keyword = post.category.name
        else:
            words = post.title.split()
            resolved_keyword = " ".join(words[:3]) if len(words) >= 3 else post.title

    title = (seo_meta.title if seo_meta and seo_meta.title else None) or post.title
    content = post.content or ""
    meta_desc = (
        (seo_meta.description if seo_meta and seo_meta.description else None) or post.excerpt or ""
    )

    images_data: list[dict[str, str | None]] = []
    has_matching_alt = False
    if post.cover_image_url:
        images_data.append({"url": post.cover_image_url, "alt": post.title})
        if keyword_in_text(resolved_keyword, post.title):
            has_matching_alt = True

    analyzer = SeoAnalyzer()
    return analyzer.analyze(
        title=title,
        content=content,
        focus_keyword=resolved_keyword,
        slug=post.slug,
        meta_description=meta_desc,
        images=images_data,
        images_count=len(images_data),
        has_image_alt=has_matching_alt,
    )


# ============================================================================
# Public Endpoints (on router: /api/v1/seo/...)
# ============================================================================


# NOTE: the redirect block is registered BEFORE the generic
# "/{resource_type}/{resource_id}" SEO-metadata routes on purpose — FastAPI
# matches in registration order, and `DELETE /admin/seo/redirects/{id}` was
# being swallowed by the generic metadata-delete handler (404 while the rule
# plainly existed). Keep this block above those routes.

# ── Redirect management (admin) + storefront rule feed ──────────────────────

from typing import Any  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402

from app.modules.seo.application import redirect_service  # noqa: E402


class RedirectCreateRequest(BaseModel):
    from_path: str = Field(..., min_length=1, max_length=500)
    # Nullable: 410/451 rules have no destination (their meaning is
    # "not coming back"). The service enforces which codes need a target.
    to_path: str | None = Field(None, max_length=500)
    status_code: int = Field(301)
    is_regex: bool = False
    note: str | None = Field(None, max_length=500)


class RedirectResponse(BaseModel):
    id: uuid.UUID
    from_path: str
    to_path: str | None
    status_code: int
    hit_count: int
    # Needed by the admin list to render the real active/inactive state.
    is_active: bool = True
    is_regex: bool = False
    note: str | None = None

    class Config:
        from_attributes = True


@router.get(
    "/redirects",
    response_model=list[dict[str, Any]],
    summary="Active redirect rules for the storefront middleware (public, cacheable)",
)
async def list_active_redirects(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.core.cache.redis import cache_get, cache_set

    cached = await cache_get("seo:redirects:active")
    if cached:
        import json

        return json.loads(cached)
    rules = await redirect_service.list_redirects(db)
    managed = [
        {
            "from_path": r.from_path,
            "to_path": r.to_path,
            "status_code": r.status_code,
            # The middleware needs the mode to pick the matcher and the
            # $1-substitution path for regex rules.
            "is_regex": r.is_regex,
        }
        for r in rules
        if r.is_active
    ]
    # Slug-history rules are appended rather than served from a second endpoint:
    # the storefront middleware has exactly one redirect feed, and a feed the
    # middleware does not read is a feed that never fires. They are not stored
    # as RedirectRule rows, so the admin's redirects screen still shows only
    # what an operator wrote.
    payload = managed + await redirect_service.slug_history_redirects(db)
    import json

    await cache_set("seo:redirects:active", json.dumps(payload), ttl=60)
    return payload


@admin_router.get(
    "/redirects",
    response_model=list[RedirectResponse],
    summary="List all redirect rules (admin)",
    dependencies=[_require_seo_write],
)
async def admin_list_redirects(
    db: AsyncSession = Depends(get_db),
) -> list[RedirectResponse]:
    rules = await redirect_service.list_redirects(db)
    return [RedirectResponse.model_validate(r) for r in rules]


@admin_router.post(
    "/redirects",
    response_model=RedirectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a redirect rule (admin)",
    dependencies=[_require_seo_write],
)
async def admin_create_redirect(
    body: RedirectCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    rule = await redirect_service.create_redirect(
        db,
        from_path=body.from_path,
        to_path=body.to_path,
        status_code=body.status_code,
        is_regex=body.is_regex,
        note=body.note,
    )
    from app.core.cache.redis import cache_delete

    await cache_delete("seo:redirects:active")
    return RedirectResponse.model_validate(rule)


class RedirectUpdateRequest(BaseModel):
    from_path: str | None = Field(None, min_length=1, max_length=500)
    to_path: str | None = Field(None, max_length=500)
    status_code: int | None = None
    is_active: bool | None = None
    is_regex: bool | None = None
    note: str | None = Field(None, max_length=500)


class RedirectHitRequest(BaseModel):
    """Storefront middleware reports which rules matched (fire-and-forget)."""

    from_paths: list[str] = Field(..., min_length=1, max_length=50)


@admin_router.patch(
    "/redirects/{rule_id}",
    response_model=RedirectResponse,
    summary="Update or (de)activate a redirect rule (admin)",
    dependencies=[_require_seo_write],
)
async def admin_update_redirect(
    rule_id: uuid.UUID,
    body: RedirectUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    rule = await redirect_service.update_redirect(
        db,
        rule_id,
        from_path=body.from_path,
        to_path=body.to_path,
        status_code=body.status_code,
        is_active=body.is_active,
        is_regex=body.is_regex,
        note=body.note,
    )
    from app.core.cache.redis import cache_delete

    await cache_delete("seo:redirects:active")
    return RedirectResponse.model_validate(rule)


@router.post(
    "/redirects/hit",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record redirect hits (called by the storefront middleware)",
)
async def record_redirect_hits(
    body: RedirectHitRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Increment hit counters for matched rules. Public + cheap so the
    middleware can report matches without holding up the redirect itself."""
    count = await redirect_service.record_hits(db, body.from_paths)
    return {"recorded": count}


class NotFoundHitRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    referrer: str | None = Field(None, max_length=500)
    user_agent: str | None = Field(None, max_length=300)


@router.post(
    "/404/hit",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record a 404 hit (called by the storefront's not-found page)",
)
async def record_notfound_hit(
    body: NotFoundHitRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Public and fire-and-forget, like the redirect hit recorder.

    The storefront's not-found page calls this with `keepalive` so the
    record survives the page unload; a failure here is swallowed on both
    ends (the recorder never raises), because monitoring must not turn a
    404 into a 500.

    A dedicated endpoint rather than server-side logging in the page: the
    Next.js not-found render has no database, and this keeps the write on
    the API side where the upsert lives.
    """
    from app.modules.seo.application.notfound_service import record_miss

    await record_miss(
        db, body.path, referrer=body.referrer, user_agent=body.user_agent
    )
    return {"recorded": True}


@admin_router.delete(
    "/redirects/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a redirect rule (admin)",
    dependencies=[_require_seo_write],
)
async def admin_delete_redirect(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await redirect_service.delete_redirect(db, rule_id)
    from app.core.cache.redis import cache_delete

    await cache_delete("seo:redirects:active")

@router.get(
    "/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    summary="Get SEO metadata for a resource",
    description=(
        "Retrieve SEO, Open Graph tags, and JSON-LD schema for a specific product, "
        "category, or blog post."
    ),
)
async def get_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    svc = SEOService(db)
    return await svc.get_by_resource(resource_type=resource_type, resource_id=resource_id)


# ============================================================================
# Admin Endpoints (on admin_router: /api/v1/admin/seo/...)
# ============================================================================


@admin_router.put(
    "/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    summary="Upsert SEO metadata for a resource (Admin)",
    dependencies=[_require_seo_write],
)
async def admin_upsert_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    data: SEOMetadataCreate,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    svc = SEOService(db)
    return await svc.upsert_for_resource(
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
    )


@admin_router.delete(
    "/{resource_type}/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete SEO metadata for a resource (Admin)",
    dependencies=[_require_seo_write],
)
async def admin_delete_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = SEOService(db)
    await svc.delete_for_resource(resource_type=resource_type, resource_id=resource_id)


# ── Also mount on router directly as aliases ───────────────────────────────────


@router.put(
    "/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    summary="Upsert SEO metadata for a resource",
    dependencies=[_require_seo_write],
)
async def router_upsert_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    data: SEOMetadataCreate,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    return await admin_upsert_seo_metadata(
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        db=db,
    )


@router.put(
    "/admin/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    include_in_schema=False,
    dependencies=[_require_seo_write],
)
async def router_alias_admin_upsert_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    data: SEOMetadataCreate,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    return await admin_upsert_seo_metadata(
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        db=db,
    )




# ============================================================================
# 404 Monitor (Rank Math parity — the "404 Monitor" module)
# ============================================================================


class NotFoundLogResponse(BaseModel):
    id: uuid.UUID
    path: str
    referrer: str | None = None
    user_agent: str | None = None
    hit_count: int
    first_seen_at: datetime
    last_seen_at: datetime

    class Config:
        from_attributes = True


class NotFoundLogListResponse(BaseModel):
    items: list[NotFoundLogResponse]
    total: int
    page: int
    page_size: int


class SeoDashboardResponse(BaseModel):
    """Counts for the SEO dashboard landing panel."""

    redirects_total: int
    redirects_active: int
    not_found_distinct_paths: int
    not_found_total_hits: int
    not_found_paths_last_7_days: int
    blog_posts_with_seo: int
    blog_posts_missing_seo: int


@admin_router.get(
    "/404",
    response_model=NotFoundLogListResponse,
    summary="List recorded 404 hits (admin)",
    dependencies=[_require_seo_write],
)
async def admin_list_404(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, description="Filter paths containing this text"),
    db: AsyncSession = Depends(get_db),
) -> NotFoundLogListResponse:
    from app.modules.seo.application.notfound_service import list_misses

    rows, total = await list_misses(db, page=page, page_size=page_size, search=search)
    return NotFoundLogListResponse(
        items=[NotFoundLogResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.delete(
    "/404",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one 404 record (admin)",
    dependencies=[_require_seo_write],
)
async def admin_delete_404(
    miss_id: uuid.UUID = Query(..., description="The 404 log row to remove"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """`miss_id` is a QUERY parameter, not a path segment.

    `DELETE /admin/seo/{resource_type}/{resource_id}` (the metadata route)
    is registered earlier and matches any two-segment path — so
    `/admin/seo/404/<uuid>` was captured by it and answered by the metadata
    handler with `resource_type="404"`: the row was never deleted and no
    error said so. A one-segment path cannot collide. Same trap as the
    `/{key}` shadowing documented in the project memory.
    """
    from app.modules.seo.application.notfound_service import delete_miss

    await delete_miss(db, miss_id)


@admin_router.post(
    "/404/clear",
    summary="Clear the whole 404 monitor (admin)",
    dependencies=[_require_seo_write],
)
async def admin_clear_404(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    from app.modules.seo.application.notfound_service import clear_all

    removed = await clear_all(db)
    return {"removed": removed}


@admin_router.get(
    "/dashboard",
    response_model=SeoDashboardResponse,
    summary="SEO dashboard counts (admin)",
    dependencies=[_require_seo_write],
)
async def admin_seo_dashboard(db: AsyncSession = Depends(get_db)) -> SeoDashboardResponse:
    """One read for the dashboard tiles.

    Counting here rather than in the client: four small aggregate queries
    against indexed columns beat four paginated list fetches the browser
    would have to count itself.
    """
    from sqlalchemy import func

    from app.modules.blog.domain.models import BlogPost as _BlogPost
    from app.modules.seo.application.notfound_service import summary as nf_summary

    redirects_total = (
        await db.execute(select(func.count()).select_from(RedirectRule))
    ).scalar_one()
    redirects_active = (
        await db.execute(
            select(func.count())
            .select_from(RedirectRule)
            .where(RedirectRule.is_active.is_(True))
        )
    ).scalar_one()
    posts_total = (
        await db.execute(
            select(func.count())
            .select_from(_BlogPost)
            .where(_BlogPost.deleted_at.is_(None))
        )
    ).scalar_one()
    posts_with_seo = (
        await db.execute(
            select(func.count(func.distinct(SEOMetadata.resource_id))).where(
                SEOMetadata.resource_type == "blog_post"
            )
        )
    ).scalar_one()
    nf = await nf_summary(db)
    return SeoDashboardResponse(
        redirects_total=int(redirects_total),
        redirects_active=int(redirects_active),
        not_found_distinct_paths=nf["distinct_paths"],
        not_found_total_hits=nf["total_hits"],
        not_found_paths_last_7_days=nf["paths_last_7_days"],
        blog_posts_with_seo=int(posts_with_seo),
        blog_posts_missing_seo=max(0, int(posts_total) - int(posts_with_seo)),
    )


# ============================================================================
# Titles & Meta (Rank Math parity): default templates per content type
# ============================================================================


class TitlesMetaTemplateEntry(BaseModel):
    """One content type's title/description template pair."""

    content_type: str
    label: str
    title_template: str
    description_template: str
    #: True when the value came from site_options (operator-set), False when
    #: it is the built-in default. The UI shows which rows were customized.
    title_customized: bool = False
    description_customized: bool = False


class TitlesMetaResponse(BaseModel):
    separator: str
    templates: list[TitlesMetaTemplateEntry]
    variables: list[dict[str, str]]


class TitlesMetaUpdateRequest(BaseModel):
    """Partial update: only the keys present are written."""

    separator: str | None = None
    templates: dict[str, dict[str, str]] | None = None
    # templates shape: {"post": {"title": "...", "description": "..."}, ...}


class TitlesMetaPreviewRequest(BaseModel):
    """Render a template against sample values (live preview in the panel)."""

    template: str
    content_type: str = "post"
    sample_title: str = "راهنمای خرید کالای دیجیتال"
    sample_excerpt: str = "در این مطلب بهترین روش‌های خرید را می‌آموزید."
    sample_focus_keyword: str = "خرید آنلاین"
    sample_category: str = "آموزش"
    sample_sitename: str = "فروشگاه"


class TitlesMetaPreviewResponse(BaseModel):
    rendered: str
    used_default: bool = False


_CT_LABELS: dict[str, str] = {
    "post": "نوشته‌ها",
    "page": "برگه‌ها",
    "product": "محصولات",
    "category": "دسته‌بندی‌ها",
    "tag": "برچسب‌ها",
    "author": "نویسنده",
    "archive": "آرشیوها",
    "home": "صفحه اصلی",
}


@admin_router.get(
    "/titles-meta",
    response_model=TitlesMetaResponse,
    summary="Default title/description templates per content type (admin)",
    dependencies=[_require_seo_write],
)
async def admin_get_titles_meta(db: AsyncSession = Depends(get_db)) -> TitlesMetaResponse:
    """Every content type's effective template, plus the variable catalog.

    Effective = the operator's site-option value when set, else the built-in
    default; the response marks which rows are customized so the panel can
    show "reset to default" only where it means something.
    """
    from app.modules.seo.application.titles_meta_service import (
        CONTENT_TYPES,
        DEFAULT_DESCRIPTION_TEMPLATES,
        DEFAULT_TITLE_TEMPLATES,
        TitlesMetaService,
        description_option_key,
        title_option_key,
    )
    from app.modules.seo.application.template_engine import VARIABLE_CATALOG
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    svc = TitlesMetaService(db)
    separator = await svc.separator()

    templates: list[TitlesMetaTemplateEntry] = []
    for content_type in CONTENT_TYPES:
        raw_title = await SiteOptionsService.get(db, title_option_key(content_type))
        raw_desc = await SiteOptionsService.get(
            db, description_option_key(content_type)
        )
        templates.append(
            TitlesMetaTemplateEntry(
                content_type=content_type,
                label=_CT_LABELS.get(content_type, content_type),
                title_template=raw_title
                or DEFAULT_TITLE_TEMPLATES.get(content_type, "%title% %sep% %sitename%"),
                description_template=raw_desc
                or DEFAULT_DESCRIPTION_TEMPLATES.get(content_type, "%excerpt%"),
                title_customized=bool(raw_title),
                description_customized=bool(raw_desc),
            )
        )

    return TitlesMetaResponse(
        separator=separator,
        templates=templates,
        variables=list(VARIABLE_CATALOG),
    )


@admin_router.put(
    "/titles-meta",
    response_model=TitlesMetaResponse,
    summary="Update default templates (admin)",
    dependencies=[_require_seo_write],
)
async def admin_update_titles_meta(
    body: TitlesMetaUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TitlesMetaResponse:
    """Write the operator's templates; unknown content types are rejected.

    Rejecting unknown keys matters: a typo'd content type would otherwise be
    stored and never read, and the operator would believe the template was
    applied while every page still used the default.
    """
    from app.modules.seo.application.titles_meta_service import (
        CONTENT_TYPES,
        description_option_key,
        title_option_key,
    )
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    if body.separator is not None:
        await SiteOptionsService.set(db, "seo_title_separator", body.separator)

    if body.templates:
        for content_type, pair in body.templates.items():
            if content_type not in CONTENT_TYPES:
                from app.core.exceptions.handlers import ValidationError

                raise ValidationError(
                    detail=(
                        f"نوع محتوای نامعتبر: {content_type}؛ "
                        f"مقادیر مجاز: {', '.join(CONTENT_TYPES)}"
                    ),
                    error_code="INVALID_CONTENT_TYPE",
                )
            if "title" in pair:
                await SiteOptionsService.set(
                    db, title_option_key(content_type), pair["title"] or ""
                )
            if "description" in pair:
                await SiteOptionsService.set(
                    db,
                    description_option_key(content_type),
                    pair["description"] or "",
                )

    return await admin_get_titles_meta(db)


@admin_router.post(
    "/titles-meta/preview",
    response_model=TitlesMetaPreviewResponse,
    summary="Render a title/description template against sample values (admin)",
    dependencies=[_require_seo_write],
)
async def admin_preview_titles_meta(
    body: TitlesMetaPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> TitlesMetaPreviewResponse:
    """Live preview for the settings panel — same engine the storefront uses."""
    from app.modules.seo.application.template_engine import (
        TemplateEngine,
        build_variables,
    )
    from app.modules.seo.application.titles_meta_service import TitlesMetaService

    svc = TitlesMetaService(db)
    separator = await svc.separator()
    engine = TemplateEngine(
        build_variables(
            title=body.sample_title,
            sitename=body.sample_sitename,
            separator=separator,
            excerpt=body.sample_excerpt,
            focus_keyword=body.sample_focus_keyword,
            category=body.sample_category,
        )
    )
    rendered = engine.render(body.template)
    return TitlesMetaPreviewResponse(rendered=rendered)


# ============================================================================
# Schema (Rich Snippets): type catalog, builder, validator (Rank Math parity)
# ============================================================================


class SchemaTypeField(BaseModel):
    key: str
    label: str
    kind: str
    required: bool
    placeholder: str = ""
    options: list[str] | None = None


class SchemaTypeEntry(BaseModel):
    type: str
    label: str
    description: str
    fields: list[SchemaTypeField]


class SchemaTypesResponse(BaseModel):
    types: list[SchemaTypeEntry]


class SchemaBuildRequest(BaseModel):
    schema_type: str
    fields: dict[str, str] = {}
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None


class SchemaBuildResponse(BaseModel):
    node: dict[str, Any]
    problems: list[str] = []


@admin_router.get(
    "/schema/types",
    response_model=SchemaTypesResponse,
    summary="Schema type catalog with field specs (admin)",
    dependencies=[_require_seo_write],
)
async def admin_schema_types() -> SchemaTypesResponse:
    """The type catalog the builder form renders from — one source for the
    UI and the backend builder, so an offered field is always consumable."""
    from app.modules.seo.application.schema_service import SCHEMA_TYPES

    return SchemaTypesResponse(
        types=[
            SchemaTypeEntry(
                type=t["type"],
                label=t["label"],
                description=t["description"],
                fields=[SchemaTypeField(**f) for f in t["fields"]],
            )
            for t in SCHEMA_TYPES
        ]
    )


@admin_router.post(
    "/schema/build",
    response_model=SchemaBuildResponse,
    summary="Build and validate a schema node from field values (admin)",
    dependencies=[_require_seo_write],
)
async def admin_schema_build(
    body: SchemaBuildRequest,
    db: AsyncSession = Depends(get_db),
) -> SchemaBuildResponse:
    """Assemble + validate without saving — the builder's live preview.

    When a resource is given, required-but-empty fields fall back to the
    resource row (a product's name), so the preview matches what the
    storefront would render for a partially filled form.
    """
    from app.core.exceptions.handlers import ValidationError
    from app.modules.seo.application.schema_service import (
        build_schema_node,
        get_type_spec,
        validate_schema_node,
    )

    if get_type_spec(body.schema_type) is None:
        raise ValidationError(
            detail=f"نوع اسکیمای نامعتبر: {body.schema_type}",
            error_code="INVALID_SCHEMA_TYPE",
        )

    resource_defaults: dict[str, Any] = {}
    if body.resource_type and body.resource_id:
        if body.resource_type in ("product", "products"):
            from app.modules.catalog.domain.models import Product

            product = await db.get(Product, body.resource_id)
            if product:
                resource_defaults = {
                    "name": product.name,
                    "description": product.short_description or product.description or "",
                }
        elif body.resource_type in ("blog_post", "post", "blog"):
            from app.modules.blog.domain.models import BlogPost

            post = await db.get(BlogPost, body.resource_id)
            if post:
                resource_defaults = {"headline": post.title, "name": post.title}

    node = build_schema_node(
        body.schema_type, body.fields, resource_defaults=resource_defaults
    )
    return SchemaBuildResponse(node=node, problems=validate_schema_node(node))


@admin_router.post(
    "/schema/apply",
    response_model=SchemaBuildResponse,
    summary="Build, validate, and store a schema node on a resource (admin)",
    dependencies=[_require_seo_write],
)
async def admin_schema_apply(
    body: SchemaBuildRequest,
    db: AsyncSession = Depends(get_db),
) -> SchemaBuildResponse:
    """Build → validate → store into seo_metadata.schema_markup.

    Validation failures reject the write: Google rejects invalid nodes
    silently, and storing one the storefront then renders is worse than
    refusing it while the operator is looking at the error.
    """
    from app.core.exceptions.handlers import ValidationError
    from app.modules.seo.application.schema_service import (
        build_schema_node,
        get_type_spec,
        validate_schema_node,
    )

    if not body.resource_type or not body.resource_id:
        raise ValidationError(
            detail="برای ذخیرهٔ اسکیما، نوع و شناسهٔ منبع الزامی است",
            error_code="RESOURCE_REQUIRED",
        )
    if get_type_spec(body.schema_type) is None:
        raise ValidationError(
            detail=f"نوع اسکیمای نامعتبر: {body.schema_type}",
            error_code="INVALID_SCHEMA_TYPE",
        )

    resource_defaults: dict[str, Any] = {}
    if body.resource_type in ("product", "products"):
        from app.modules.catalog.domain.models import Product

        product = await db.get(Product, body.resource_id)
        if product:
            resource_defaults = {
                "name": product.name,
                "description": product.short_description or product.description or "",
            }

    node = build_schema_node(
        body.schema_type, body.fields, resource_defaults=resource_defaults
    )
    problems = validate_schema_node(node)
    if problems:
        raise ValidationError(
            detail="؛ ".join(problems),
            error_code="INVALID_SCHEMA",
        )

    from app.modules.seo.schemas.seo import SEOMetadataCreate

    svc = SEOService(db)
    await svc.upsert_for_resource(
        body.resource_type, body.resource_id, SEOMetadataCreate(schema_markup=node)
    )
    return SchemaBuildResponse(node=node, problems=[])


# ============================================================================
# Redirect import / export (Rank Math's Redirections CSV tools)
# ============================================================================


class RedirectImportResponse(BaseModel):
    created: int
    updated: int
    total: int
    errors: list[dict[str, Any]]


@admin_router.get(
    "/redirects/export",
    summary="Export all redirect rules as CSV (admin)",
    dependencies=[_require_seo_write],
    responses={200: {"content": {"text/csv": {}}}},
)
async def admin_export_redirects(db: AsyncSession = Depends(get_db)) -> Response:
    """UTF-8 BOM CSV so Excel opens Persian notes correctly."""
    from app.modules.seo.application.redirect_service import export_redirects_csv

    rules = await redirect_service.list_redirects(db)
    csv_text = export_redirects_csv(rules)
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="redirects.csv"'},
    )


@admin_router.post(
    "/redirects/import",
    response_model=RedirectImportResponse,
    summary="Import redirect rules from CSV (admin)",
    dependencies=[_require_seo_write],
)
async def admin_import_redirects(
    body: dict[str, str],
    db: AsyncSession = Depends(get_db),
) -> RedirectImportResponse:
    """Import from a CSV body (``{"content": "..."}``).

    Partial success is deliberate and reported: one bad row in a 200-row
    htaccess migration must not discard the other 199, and the operator sees
    every failure with its line number.
    """
    content = body.get("content") or ""
    if not content.strip():
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("محتوای CSV خالی است", error_code="EMPTY_CSV")

    from app.core.cache.redis import cache_delete
    from app.modules.seo.application.redirect_service import import_redirects_csv

    result = await import_redirects_csv(db, content)
    await cache_delete("seo:redirects:active")
    return RedirectImportResponse(
        created=int(result["created"]),
        updated=int(result["updated"]),
        total=int(result["total"]),
        errors=result["errors"],  # type: ignore[arg-type]
    )


# ============================================================================
# Link counter (Rank Math's Link Counter): per-post internal/external counts
# ============================================================================


class PostLinkCounts(BaseModel):
    post_id: uuid.UUID
    slug: str
    title: str
    internal: int
    external: int
    anchor: int
    total: int
    external_urls: list[str] = []
    #: True when the post body has no internal link at all — the content-side
    #: orphan an operator most wants to find (Rank Math's "Orphan Posts"
    #: filter is the page-side equivalent).
    is_orphan: bool = False


class LinkCounterResponse(BaseModel):
    items: list[PostLinkCounts]
    total: int
    page: int
    page_size: int
    orphan_count: int
    #: Distinct external hosts across the whole page, so a dead domain used in
    #: many posts appears once.
    external_hosts: list[str] = []


@admin_router.get(
    "/link-counter",
    response_model=LinkCounterResponse,
    summary="Internal/external link counts per post (admin)",
    dependencies=[_require_seo_write],
)
async def admin_link_counter(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    orphans_only: bool = Query(False, description="Only posts without internal links"),
    db: AsyncSession = Depends(get_db),
) -> LinkCounterResponse:
    """Count links in each published post's body.

    Computed on demand from the stored bodies (no index table): the page is
    bounded by ``page_size``, and a materialized count would be one more thing
    to keep in sync on every edit — a scan stays correct by construction.
    """
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.seo.application.link_counter_service import (
        count_links,
        site_hosts_from,
    )
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
        public_base_url,
    )

    base = await public_base_url(db)
    hosts = site_hosts_from(base)

    stmt = (
        select(BlogPost)
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
        )
        .order_by(BlogPost.published_at.desc().nullslast())
    )
    posts = list((await db.execute(stmt)).scalars().all())

    items: list[PostLinkCounts] = []
    all_external_hosts: set[str] = set()
    for post in posts:
        counts = count_links(post.content or "", site_hosts=hosts)
        if orphans_only and counts["internal"] > 0:
            continue
        for url in counts["external_urls"]:
            host = urlparse(url).hostname
            if host:
                all_external_hosts.add(host.lower())
        items.append(
            PostLinkCounts(
                post_id=post.id,
                slug=post.slug,
                title=post.title,
                internal=counts["internal"],
                external=counts["external"],
                anchor=counts["anchor"],
                total=counts["total"],
                external_urls=counts["external_urls"],
                is_orphan=counts["internal"] == 0,
            )
        )

    total = len(items)
    start = (page - 1) * page_size
    return LinkCounterResponse(
        items=items[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
        orphan_count=sum(1 for i in items if i.is_orphan),
        external_hosts=sorted(all_external_hosts),
    )


# ============================================================================
# Instant Indexing (Rank Math parity): IndexNow + Google skeleton
# ============================================================================


class IndexingStatusResponse(BaseModel):
    indexnow_enabled: bool
    indexnow_key: str | None
    key_file_path: str | None
    google: dict[str, Any]


class IndexingToggleRequest(BaseModel):
    enabled: bool


class IndexingSubmitRequest(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=500)


class IndexingSubmitResponse(BaseModel):
    submitted: int
    status: str
    reason: str | None = None
    http_status: int | None = None


@admin_router.get(
    "/indexing",
    response_model=IndexingStatusResponse,
    summary="Instant Indexing status: IndexNow key + Google connection (admin)",
    dependencies=[_require_seo_write],
)
async def admin_indexing_status(
    db: AsyncSession = Depends(get_db),
) -> IndexingStatusResponse:
    """Everything the settings card needs: the key (generated on first read),
    its public file path, and the honest Google connection state."""
    from app.modules.seo.application.indexing_service import (
        get_or_create_key,
        google_status,
        is_enabled,
        key_file_url,
    )
    from app.modules.settings.application.site_options_service import public_base_url

    key = await get_or_create_key(db)
    base = await public_base_url(db)
    return IndexingStatusResponse(
        indexnow_enabled=await is_enabled(db),
        indexnow_key=key,
        # Same builder the submission payload uses — the card shows the URL
        # IndexNow will actually fetch, not a different one.
        key_file_path=key_file_url(base, key),
        google=await google_status(db),
    )


@admin_router.put(
    "/indexing",
    response_model=IndexingStatusResponse,
    summary="Enable or disable IndexNow submissions (admin)",
    dependencies=[_require_seo_write],
)
async def admin_indexing_toggle(
    body: IndexingToggleRequest,
    db: AsyncSession = Depends(get_db),
) -> IndexingStatusResponse:
    from app.modules.settings.application.site_options_service import SiteOptionsService

    from app.modules.seo.application.indexing_service import ENABLED_OPTION

    await SiteOptionsService.set(db, ENABLED_OPTION, "1" if body.enabled else "0")
    return await admin_indexing_status(db)


@admin_router.post(
    "/indexing/submit",
    response_model=IndexingSubmitResponse,
    summary="Submit URLs to IndexNow (admin, manual)",
    dependencies=[_require_seo_write],
)
async def admin_indexing_submit(
    body: IndexingSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> IndexingSubmitResponse:
    """Manual submission for URLs the operator wants indexed now.

    Same service the publish hook uses, so a manual submit and an automatic
    one cannot behave differently.
    """
    from app.modules.seo.application.indexing_service import submit_urls

    result = await submit_urls(db, body.urls)
    return IndexingSubmitResponse(
        submitted=int(result.get("submitted", 0)),
        status=str(result.get("status", "unknown")),
        reason=result.get("reason"),  # type: ignore[arg-type]
        http_status=result.get("http_status"),  # type: ignore[arg-type]
    )


# ============================================================================
# Status & Tools (Rank Math's Status & Tools page)
# ============================================================================


class SeoStatusCheck(BaseModel):
    key: str
    label: str
    status: str  # pass | warn | fail
    detail: str
    fix: str = ""


class SeoStatusResponse(BaseModel):
    checks: list[SeoStatusCheck]
    pass_count: int
    warn_count: int
    fail_count: int


class IncompleteDataResponse(BaseModel):
    blog_posts_without_seo_metadata: int
    blog_post_ids: list[str]
    products_without_seo_title: int


class SettingsExportResponse(BaseModel):
    settings: dict[str, str]


class SettingsImportRequest(BaseModel):
    settings: dict[str, str]


class SettingsImportResponse(BaseModel):
    written: int
    total: int
    errors: list[dict[str, str]]


@admin_router.get(
    "/status",
    response_model=SeoStatusResponse,
    summary="SEO status checks (admin)",
    dependencies=[_require_seo_write],
)
async def admin_seo_status(db: AsyncSession = Depends(get_db)) -> SeoStatusResponse:
    from app.modules.seo.application.status_tools_service import run_status_checks

    checks = await run_status_checks(db)
    return SeoStatusResponse(
        checks=[SeoStatusCheck(**c) for c in checks],
        pass_count=sum(1 for c in checks if c["status"] == "pass"),
        warn_count=sum(1 for c in checks if c["status"] == "warn"),
        fail_count=sum(1 for c in checks if c["status"] == "fail"),
    )


@admin_router.get(
    "/tools/incomplete-data",
    response_model=IncompleteDataResponse,
    summary="Rows missing SEO data (admin, read-only)",
    dependencies=[_require_seo_write],
)
async def admin_incomplete_data(
    db: AsyncSession = Depends(get_db),
) -> IncompleteDataResponse:
    from app.modules.seo.application.status_tools_service import find_incomplete_data

    result = await find_incomplete_data(db)
    return IncompleteDataResponse(**result)


@admin_router.get(
    "/tools/settings-export",
    response_model=SettingsExportResponse,
    summary="Export SEO settings as JSON (admin)",
    dependencies=[_require_seo_write],
)
async def admin_settings_export(
    db: AsyncSession = Depends(get_db),
) -> SettingsExportResponse:
    from app.modules.seo.application.status_tools_service import export_settings

    return SettingsExportResponse(settings=await export_settings(db))


@admin_router.post(
    "/tools/settings-import",
    response_model=SettingsImportResponse,
    summary="Import SEO settings from JSON (admin)",
    dependencies=[_require_seo_write],
)
async def admin_settings_import(
    body: SettingsImportRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingsImportResponse:
    """Per-key results: unknown keys are errors, valid keys are written.

    The export file from one environment imports cleanly into another; a
    hand-edited file with a typo reports the bad key instead of pretending.
    """
    from app.modules.seo.application.status_tools_service import import_settings

    result = await import_settings(db, body.settings)
    return SettingsImportResponse(
        written=int(result["written"]),
        total=int(result["total"]),
        errors=result["errors"],  # type: ignore[arg-type]
    )


# ============================================================================
# Local SEO (Rank Math's Local SEO): business profile + LocalBusiness schema
# ============================================================================


class BusinessFieldSpec(BaseModel):
    key: str
    label: str
    placeholder: str


class LocalSeoResponse(BaseModel):
    values: dict[str, str]
    fields: list[BusinessFieldSpec]
    business_types: list[str]


class LocalSeoSaveRequest(BaseModel):
    values: dict[str, str]


@admin_router.get(
    "/local-seo",
    response_model=LocalSeoResponse,
    summary="Local business profile (admin)",
    dependencies=[_require_seo_write],
)
async def admin_get_local_seo(db: AsyncSession = Depends(get_db)) -> LocalSeoResponse:
    """The profile values + the field vocabulary the card renders from."""
    from app.modules.seo.application.local_seo_service import (
        BUSINESS_FIELDS,
        BUSINESS_TYPES,
        get_business_info,
    )

    return LocalSeoResponse(
        values=await get_business_info(db),
        fields=[BusinessFieldSpec(key=k, label=l, placeholder=p) for k, l, p in BUSINESS_FIELDS],
        business_types=list(BUSINESS_TYPES),
    )


@admin_router.put(
    "/local-seo",
    response_model=LocalSeoResponse,
    summary="Save local business profile (admin)",
    dependencies=[_require_seo_write],
)
async def admin_save_local_seo(
    body: LocalSeoSaveRequest,
    db: AsyncSession = Depends(get_db),
) -> LocalSeoResponse:
    """Unknown keys are rejected — a typo'd field must not save silently."""
    from app.modules.seo.application.local_seo_service import save_business_info

    await save_business_info(db, body.values)
    return await admin_get_local_seo(db)


@admin_router.get(
    "/local-seo/preview",
    summary="The LocalBusiness JSON-LD the storefront would emit (admin)",
    dependencies=[_require_seo_write],
)
async def admin_local_seo_preview(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Live preview — same builder the storefront uses, so what the operator
    sees is exactly what Google reads."""
    from app.modules.seo.application.local_seo_service import (
        build_local_business_jsonld,
    )
    from app.modules.settings.application.site_options_service import public_base_url

    node = await build_local_business_jsonld(db, base_url=await public_base_url(db))
    return {"node": node, "configured": node is not None}


# ============================================================================
# Content AI (Rank Math's Content AI): meta suggestions via a configured LLM
# ============================================================================


class ContentAiStatusResponse(BaseModel):
    connected: bool
    model: str
    note: str


class ContentAiConfigRequest(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class ContentAiGenerateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field("", max_length=10000)
    kind: str = Field("description", pattern="^(title|description)$")


class ContentAiGenerateResponse(BaseModel):
    status: str
    suggestion: str | None = None
    reason: str | None = None


@admin_router.get(
    "/content-ai",
    response_model=ContentAiStatusResponse,
    summary="Content AI connection status (admin)",
    dependencies=[_require_seo_write],
)
async def admin_content_ai_status(db: AsyncSession = Depends(get_db)) -> ContentAiStatusResponse:
    """Connection state only — the API key is never echoed back."""
    from app.modules.seo.application.content_ai_service import status

    return ContentAiStatusResponse(**await status(db))


@admin_router.put(
    "/content-ai",
    response_model=ContentAiStatusResponse,
    summary="Configure Content AI endpoint/key (admin)",
    dependencies=[_require_seo_write],
)
async def admin_content_ai_config(
    body: ContentAiConfigRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentAiStatusResponse:
    """Write whichever fields were sent. The key is stored as-is (site
    options, same store as the Akismet key) and never returned."""
    from app.modules.seo.application.content_ai_service import (
        AI_BASE_URL_OPTION,
        AI_KEY_OPTION,
        AI_MODEL_OPTION,
        status,
    )
    from app.modules.settings.application.site_options_service import SiteOptionsService

    if body.api_key is not None:
        await SiteOptionsService.set(db, AI_KEY_OPTION, body.api_key.strip())
    if body.base_url is not None:
        await SiteOptionsService.set(db, AI_BASE_URL_OPTION, body.base_url.strip())
    if body.model is not None:
        await SiteOptionsService.set(db, AI_MODEL_OPTION, body.model.strip())
    return ContentAiStatusResponse(**await status(db))


@admin_router.post(
    "/content-ai/generate",
    response_model=ContentAiGenerateResponse,
    summary="Generate a meta title/description suggestion (admin)",
    dependencies=[_require_seo_write],
)
async def admin_content_ai_generate(
    body: ContentAiGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentAiGenerateResponse:
    """A suggestion for the operator to review — never auto-written to any
    post. No key configured → an honest refusal, not a silent empty result."""
    from app.modules.seo.application.content_ai_service import generate_meta_suggestion

    result = await generate_meta_suggestion(
        db, title=body.title, content=body.content, kind=body.kind
    )
    return ContentAiGenerateResponse(
        status=str(result["status"]),
        suggestion=result.get("suggestion"),  # type: ignore[arg-type]
        reason=result.get("reason"),  # type: ignore[arg-type]
    )
