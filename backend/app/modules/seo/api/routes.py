"""REST API routes for the SEO module.

Provides endpoints for fetching and managing per-resource SEO metadata.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions
from app.modules.blog.domain.models import BlogPost
from app.modules.catalog.infrastructure.catalog_repository import ProductRepository
from app.modules.seo.application.seo_analyzer import SeoAnalyzer, keyword_in_text
from app.modules.seo.application.seo_service import SEOService
from app.modules.seo.domain.models import SEOMetadata
from app.modules.seo.schemas.seo import (
    SeoAnalysisRequest,
    SeoAnalysisResponse,
    SEOMetadataCreate,
    SEOMetadataResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
