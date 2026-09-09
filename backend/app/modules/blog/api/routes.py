"""REST API routes for the Blog module.

Provides public endpoints for browsing articles and categories,
and admin endpoints for managing blog posts and categories.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user
from app.modules.blog.application.blog_service import BlogService
from app.modules.blog.domain.models import BlogPostStatus
from app.modules.blog.schemas.blog import (
    BlogCategoryCreate,
    BlogCategoryResponse,
    BlogListResponse,
    BlogPostCreate,
    BlogPostDetailResponse,
    BlogPostResponse,
    BlogPostUpdate,
)

# Public router mounted at /api/v1/blog
router = APIRouter()

# Admin router mounted at /api/v1/admin/blog via main.py _include_routers
admin_router = APIRouter(
    prefix="/admin/blog",
    tags=["admin-blog"],
)

_require_blog_write = Depends(RequirePermissions("blog:write"))


# ============================================================================
# Public Endpoints (on router)
# ============================================================================


@router.get(
    "/posts",
    response_model=BlogListResponse,
    summary="List published blog posts",
    description="Retrieve paginated published blog posts with optional category and search filters.",
)
async def list_posts(
    category: Optional[str] = Query(None, description="Filter by category slug"),
    search: Optional[str] = Query(None, description="Search query matching title/excerpt/content"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> BlogListResponse:
    svc = BlogService(db)
    return await svc.list_posts(
        category_slug=category,
        status=BlogPostStatus.PUBLISHED,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/posts/{slug}",
    response_model=BlogPostDetailResponse,
    summary="Get blog post by slug",
    description="Retrieve full details for a published blog post and increment its view count.",
)
async def get_post_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> BlogPostDetailResponse:
    svc = BlogService(db)
    return await svc.get_post_by_slug(slug=slug, increment_views=True, only_published=True)


@router.get(
    "/categories",
    response_model=list[BlogCategoryResponse],
    summary="List blog categories",
    description="Retrieve all blog categories along with their published post count.",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> list[BlogCategoryResponse]:
    svc = BlogService(db)
    return await svc.list_categories()


@router.get(
    "/recent",
    response_model=list[BlogPostResponse],
    summary="Get recent blog posts",
    description="Retrieve a small list of recent published posts for widgets or home page.",
)
async def get_recent_posts(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[BlogPostResponse]:
    svc = BlogService(db)
    return await svc.get_recent_posts(limit=limit)


# ============================================================================
# Admin Endpoints (on admin_router: /api/v1/admin/blog/...)
# ============================================================================


@admin_router.post(
    "/posts",
    response_model=BlogPostDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create blog post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_create_post(
    data: BlogPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    svc = BlogService(db)
    author_id = data.author_id
    if not author_id:
        try:
            author_id = uuid.UUID(current_user["sub"])
        except Exception:
            author_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    return await svc.create_post(data, author_id=author_id)


@admin_router.patch(
    "/posts/{post_id}",
    response_model=BlogPostDetailResponse,
    summary="Update blog post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_update_post(
    post_id: uuid.UUID,
    data: BlogPostUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlogPostDetailResponse:
    svc = BlogService(db)
    return await svc.update_post(post_id=post_id, data=data)


@admin_router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete blog post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_delete_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = BlogService(db)
    await svc.delete_post(post_id=post_id)


@admin_router.post(
    "/categories",
    response_model=BlogCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create blog category (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_create_category(
    data: BlogCategoryCreate,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryResponse:
    svc = BlogService(db)
    return await svc.create_category(data)


# ── Also mount admin endpoints on public router with /admin prefix as aliases ─
# This ensures both /admin/blog/posts and /blog/admin/posts / router-direct work

@router.post(
    "/admin/posts",
    response_model=BlogPostDetailResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_create_post(
    data: BlogPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    return await admin_create_post(data=data, db=db, current_user=current_user)


@router.patch(
    "/admin/posts/{post_id}",
    response_model=BlogPostDetailResponse,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_update_post(
    post_id: uuid.UUID,
    data: BlogPostUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlogPostDetailResponse:
    return await admin_update_post(post_id=post_id, data=data, db=db)


@router.delete(
    "/admin/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_delete_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await admin_delete_post(post_id=post_id, db=db)


@router.post(
    "/admin/categories",
    response_model=BlogCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_create_category(
    data: BlogCategoryCreate,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryResponse:
    return await admin_create_category(data=data, db=db)
