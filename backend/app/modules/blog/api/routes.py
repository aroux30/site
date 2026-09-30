"""REST API routes for the Blog module.

Provides public endpoints for browsing articles and categories,
and admin endpoints for managing blog posts and categories.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from fastapi.responses import Response

from app.core.security.rate_limiter import get_real_client_ip
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user,
    get_current_user_optional,
)
from app.modules.blog.application.blog_service import BlogService
from app.modules.blog.application.autosave_service import AutosaveService
from app.modules.blog.application.comment_service import CommentService
from app.modules.blog.application.feed_service import (
    generate_atom_feed,
    generate_rss_feed,
    generate_term_feed,
)
from app.modules.blog.application.post_lock_service import PostLockService
from app.modules.blog.domain.models import BlogPostStatus, CommentStatus
from app.modules.blog.schemas.blog import (
    BlogCategoryCreate,
    BlogCategoryResponse,
    BlogCommentCreate,
    BlogAuthorArchiveResponse,
    BlogCategoryDeleteResult,
    BlogCategoryUpdate,
    BlogAuthorResponse,
    BlogCommentListResponse,
    BlogCommentAdminListResponse,
    BlogCommentAdminResponse,
    BlogCommentResponse,
    BlogCommentUpdate,
    BlogListResponse,
    BlogPostCreate,
    BlogPostDetailResponse,
    BlogPostMetaCreate,
    BlogPostMetaResponse,
    BlogPostResponse,
    BlogPostRevisionDetailResponse,
    BlogPostRevisionResponse,
    BlogPostUpdate,
    BlogTagCreate,
    BlogTagUpdate,
    BlogTagResponse,
    RevisionDiffResponse,
)

# Public router mounted at /api/v1/blog
router = APIRouter()

# Admin router mounted at /api/v1/admin/blog via main.py _include_routers
admin_router = APIRouter(
    prefix="/admin/blog",
    tags=["admin-blog"],
)

_require_blog_write = Depends(RequirePermissions("blog:write"))

#: Comment moderation is a separate codename from writing, mirroring
#: WordPress's ``moderate_comments``. Both the route guard and the per-object
#: check are needed: this one asks "may you moderate at all", the other asks
#: "is this your discussion".
_require_moderate_comments = Depends(RequirePermissions("blog:moderate_comments"))


async def _require_post_access(
    post_id: uuid.UUID,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Gate a post mutation on ownership, not just on ``blog:write``.

    ``_require_blog_write`` only proves the caller may write blog content in
    general; it says nothing about *whose*. This is the per-object half of
    the check (the ``map_meta_cap`` equivalent) and is what keeps an author
    from editing a colleague's post.

    The post is loaded by primary key rather than through the service: this
    runs before the handler and only needs to know who owns the row. It
    raises the service's own ``NotFoundError`` shape for a missing post, so a
    caller still gets 404 rather than being told "you may not edit this"
    about a post that does not exist — otherwise the 403 would double as an
    existence oracle.
    """
    from app.core.exceptions.handlers import NotFoundError
    from app.core.security.object_capabilities import (
        OBJECT_RULES,
        require_object_capability,
    )
    from app.modules.blog.domain.models import BlogPost

    post = await db.get(BlogPost, post_id)
    if post is None:
        raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

    await require_object_capability(current_user, post, OBJECT_RULES["posts"])


async def _require_comment_access(
    comment_id: uuid.UUID,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Gate a comment mutation on the post that owns the discussion.

    A comment has no author the caller can be compared against in the sense
    that matters here — the question is whether you may moderate *this
    conversation*, and that is the post's question. So the ownership check
    runs against the parent post, resolved in one query. Moderating on someone
    else's post would otherwise be a way to rewrite their pages from the
    comments tab.
    """
    from app.core.exceptions.handlers import NotFoundError
    from app.modules.blog.domain.models import (
        COMMENT_RESOURCE_BLOG_POST,
        COMMENT_RESOURCE_CMS_PAGE,
        BlogComment,
    )

    comment = await db.get(BlogComment, comment_id)
    if comment is None:
        raise NotFoundError("BlogComment", f"Comment {comment_id} not found")

    # Comments are polymorphic: ``post_id`` is set only for blog-post comments
    # and is NULL for CMS-page comments (a check constraint keeps the pair
    # consistent). Resolving through the legacy ``post_id`` alone meant every
    # page comment resolved to None, so approve / spam / delete on a page
    # comment all 404'd — the moderation surface silently covered only one of
    # the two kinds of thread it claims to manage.
    if comment.resource_type == COMMENT_RESOURCE_CMS_PAGE and comment.resource_id:
        await _require_page_access(comment.resource_id, current_user, db)
        return

    if not comment.post_id:
        raise NotFoundError(
            "BlogComment",
            f"Comment {comment_id} is not attached to a moderatable object",
        )
    await _require_post_access(comment.post_id, current_user, db)


async def _require_page_access(
    page_id: uuid.UUID,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> None:
    """The CMS-page equivalent of :func:`_require_post_access`.

    ``settings:write`` proves the caller may edit site content in general; this
    is the per-object half. CMS pages have no separate editor role, so the
    capability check is the same one the route guard already applies — what
    this adds is a 404 for a page that does not exist rather than a 403, so
    the check cannot be used as an existence oracle.
    """
    from app.core.exceptions.handlers import NotFoundError
    from app.modules.content.domain.models import CmsPage

    page = await db.get(CmsPage, page_id)
    if page is None or page.deleted_at is not None:
        raise NotFoundError("CmsPage", f"Page {page_id} not found")


# ============================================================================
# Public Endpoints (on router)
# ============================================================================


@router.get(
    "/posts",
    response_model=BlogListResponse,
    summary="List published blog posts",
    description="Retrieve paginated published blog posts with optional category and search filters.",  # noqa: E501
)
async def list_posts(
    category: str | None = Query(None, description="Filter by category slug"),
    tag: str | None = Query(None, description="Filter by tag slug"),
    search: str | None = Query(None, description="Search query matching title/excerpt/content"),
    sort: str | None = Query(
        None,
        description="Strapi-style ordering: <field>[:asc|desc] — title, published_at, created_at, updated_at",  # noqa: E501
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description="Items per page; defaults to the admin's posts_per_page setting",
    ),
    db: AsyncSession = Depends(get_db),
) -> BlogListResponse:
    from app.modules.settings.application.site_options_service import SiteOptionsService

    if page_size is None:
        page_size = await SiteOptionsService.get_int(
            db, "posts_per_page", 10, minimum=1, maximum=100
        )
    svc = BlogService(db)
    return await svc.list_posts(
        category_slug=category,
        status=BlogPostStatus.PUBLISHED,
        search=search,
        tag_slug=tag,
        page=page,
        page_size=page_size,
        sort=sort,
        # Storefront listing: private posts are hidden and a protected
        # post's body-derived excerpt is replaced by a placeholder.
        public_only=True,
    )


@router.get(
    "/authors",
    response_model=list[BlogAuthorResponse],
    summary="List authors that have published at least once",
)
async def list_authors(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[BlogAuthorResponse]:
    from app.modules.blog.application.author_service import AuthorService

    return await AuthorService(db).list_authors(limit=limit)


@router.get(
    "/authors/{slug}",
    response_model=BlogAuthorArchiveResponse,
    summary="Author archive with their published posts",
    description=(
        "Resolve an author by their stable public slug and return their published "
        "posts. The slug comes from users.author_slug, never from the display "
        "name, so renaming a profile cannot break a published /author/ URL."
    ),
)
async def get_author_archive(
    slug: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int | None = Query(
        None, ge=1, le=100, description="Items per page; defaults to posts_per_page"
    ),
    db: AsyncSession = Depends(get_db),
) -> BlogAuthorArchiveResponse:
    from app.modules.settings.application.site_options_service import SiteOptionsService
    from app.modules.blog.application.author_service import AuthorService

    if page_size is None:
        page_size = await SiteOptionsService.get_int(
            db, "posts_per_page", 10, minimum=1, maximum=100
        )
    return await AuthorService(db).get_archive(
        slug=slug, page=page, page_size=page_size, public_only=True
    )


@router.get(
    "/posts/{slug}",
    response_model=BlogPostDetailResponse,
    summary="Get blog post by slug",
    description=(
        "Retrieve full details for a published blog post and increment its view count. "
        "Password-protected posts return metadata with ``content_locked=true`` and an "
        "empty body until the correct ``password`` is supplied."
    ),
)
async def get_post_by_slug(
    slug: str,
    password: str | None = Query(
        None,
        max_length=255,
        description="Access password for a password-protected post",
    ),
    db: AsyncSession = Depends(get_db),
) -> BlogPostDetailResponse:
    svc = BlogService(db)
    return await svc.get_post_by_slug(
        slug=slug,
        increment_views=True,
        only_published=True,
        access_password=password,
    )


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
    "/categories/tree",
    response_model=list[BlogCategoryResponse],
    summary="Category tree with nested children and post counts",
)
async def category_tree(
    db: AsyncSession = Depends(get_db),
) -> list[BlogCategoryResponse]:
    """Roots first, each carrying its children.

    Declared before ``/categories/{category_id}`` on purpose: FastAPI matches
    in declaration order, so a parameter route declared first would swallow
    "tree" and fail to parse it as a UUID.
    """
    svc = BlogService(db)
    return await svc.get_category_tree()


@router.patch(
    "/categories/{category_id}",
    response_model=BlogCategoryResponse,
    summary="Update a blog category",
    dependencies=[_require_blog_write],
)
async def update_category(
    category_id: uuid.UUID,
    body: BlogCategoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryResponse:
    svc = BlogService(db)
    return await svc.update_category(category_id, body)


@router.delete(
    "/categories/{category_id}",
    response_model=BlogCategoryDeleteResult,
    summary="Delete a blog category, orphaning rather than deleting its posts",
    dependencies=[_require_blog_write],
)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryDeleteResult:
    svc = BlogService(db)
    return await svc.delete_category(category_id)


@router.get(
    "/tags",
    response_model=list[BlogTagResponse],
    summary="List blog tags",
    description="Retrieve all blog tags along with their published post count.",
)
async def list_tags(
    db: AsyncSession = Depends(get_db),
) -> list[BlogTagResponse]:
    svc = BlogService(db)
    return await svc.list_tags()


@router.patch(
    "/tags/{tag_id}",
    response_model=BlogTagResponse,
    summary="Update a blog tag",
    dependencies=[_require_blog_write],
)
async def update_tag(
    tag_id: uuid.UUID,
    body: BlogTagUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlogTagResponse:
    svc = BlogService(db)
    return await svc.update_tag(tag_id, body)


@router.delete(
    "/tags/{tag_id}",
    response_model=BlogCategoryDeleteResult,
    summary="Delete a blog tag, unlinking it from its posts",
    dependencies=[_require_blog_write],
)
async def delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryDeleteResult:
    svc = BlogService(db)
    return await svc.delete_tag(tag_id)


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
# RSS/Atom Feed Endpoints (on router)
# ============================================================================


async def _feed_settings(db: AsyncSession) -> dict[str, Any]:
    """Site options shared by every feed endpoint (WordPress parity reads)."""
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
        public_base_url,
    )

    limit = await SiteOptionsService.get_int(db, "posts_per_rss", 20, minimum=1, maximum=100)
    return {
        "limit": limit,
        "base_url": await public_base_url(db),
        "site_title": await SiteOptionsService.get(db, "blogname") or "وبلاگ",
        "site_description": (
            await SiteOptionsService.get(db, "blogdescription") or "آخرین مطالب وبلاگ"
        ),
        "permalink_structure": await SiteOptionsService.get(db, "permalink_structure"),
        # WordPress's "Excerpt only" radio in Reading → Feed. The option was
        # seeded and editable but read by nothing, so a site that asked for
        # excerpts always published full bodies.
        "use_excerpt": (
            await SiteOptionsService.get(db, "rss_use_excerpt", "0") or "0"
        )
        in {"1", "true", "yes", "on"},
    }


@router.get(
    "/feed/rss",
    summary="RSS feed of published blog posts",
    response_class=Response,
)
async def rss_feed(
    db: AsyncSession = Depends(get_db),
) -> Response:
    xml = await generate_rss_feed(db, **await _feed_settings(db))
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get(
    "/feed/rss/category/{slug}",
    summary="RSS feed scoped to one category",
    response_class=Response,
)
async def category_rss_feed(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    xml = await generate_rss_feed(db, category_slug=slug, **await _feed_settings(db))
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get(
    "/feed/rss/tag/{slug}",
    summary="RSS feed scoped to one tag",
    response_class=Response,
)
async def tag_rss_feed(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    xml = await generate_rss_feed(db, tag_slug=slug, **await _feed_settings(db))
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get(
    "/feed/atom",
    summary="Atom feed of published blog posts",
    response_class=Response,
)
async def atom_feed(
    db: AsyncSession = Depends(get_db),
) -> Response:
    xml = await generate_atom_feed(db, **await _feed_settings(db))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get(
    "/opml",
    summary="OPML 2.0 export of feeds and curated links",
    response_class=Response,
)
async def export_opml(
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.modules.blog.application.opml_service import export_opml as _export

    xml = await _export(db)
    return Response(
        content=xml,
        media_type="text/x-opml; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="subscriptions.opml"'},
    )


@router.post(
    "/admin/opml/import",
    summary="Import outline links from an OPML document",
    dependencies=[_require_blog_write],
)
async def import_opml(
    file: UploadFile = File(...),
    replace_existing: bool = Query(False, description="Delete existing links first"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    # `replace_existing=True` runs `DELETE FROM blog_links` in opml_service, so
    # this route used to let any anonymous visitor wipe and replace the whole
    # links table. The path says "admin" and the guard now matches it.
    from app.core.exceptions.handlers import ValidationError
    from app.modules.blog.application.opml_service import import_opml as _import

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(detail="فایل باید با کدگذاری UTF-8 باشد") from exc
    return await _import(db, text, replace_existing=replace_existing)


@router.get(
    "/feed/rdf",
    summary="RDF 1.0 (RSS 1.0) feed of published blog posts",
    response_class=Response,
)
async def rdf_feed(
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.modules.blog.application.feed_service import _fetch_feed_posts, build_rdf_xml
    from app.modules.settings.application.site_options_service import SiteOptionsService

    settings = await _feed_settings(db)
    _, _, posts = await _fetch_feed_posts(db, limit=settings["limit"])
    site_title = await SiteOptionsService.get(db, "blogname", "فروشگاه") or "فروشگاه"
    xml = build_rdf_xml(
        posts,
        base_url=settings["base_url"],
        title=site_title,
        description=await SiteOptionsService.get(db, "blogdescription", "") or site_title,
        self_path="/api/v1/blog/feed/rdf",
    )
    return Response(content=xml, media_type="application/rdf+xml; charset=utf-8")


@router.get(
    "/feed/comments/rss",
    summary="Recent comments across the blog (RSS 2.0)",
    response_class=Response,
)
async def comments_feed(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.modules.blog.application.feed_service import (
        build_comments_rss_xml,
        generate_comments_feed,
    )
    from app.modules.settings.application.site_options_service import SiteOptionsService

    settings = await _feed_settings(db)
    comments, title, link = await generate_comments_feed(db, limit=limit)
    xml = build_comments_rss_xml(
        comments,
        base_url=settings["base_url"],
        title=title,
        link=link,
        self_path="/api/v1/blog/feed/comments/rss",
    )
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get(
    "/feed/comments/rss/{post_id}",
    summary="Comments on one post (RSS 2.0)",
    response_class=Response,
)
async def post_comments_feed(
    post_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.modules.blog.application.feed_service import (
        build_comments_rss_xml,
        generate_comments_feed,
    )

    settings = await _feed_settings(db)
    comments, title, link = await generate_comments_feed(
        db, post_id=post_id, limit=limit
    )
    xml = build_comments_rss_xml(
        comments,
        base_url=settings["base_url"],
        title=title,
        link=link,
        self_path=f"/api/v1/blog/feed/comments/rss/{post_id}",
    )
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get(
    "/feed/rss/{slug}",
    summary="RSS feed for one category or tag",
    response_class=Response,
)
async def rss_term_feed(
    slug: str,
    taxonomy: str = Query(
        "auto",
        pattern="^(auto|category|tag)$",
        description="auto resolves the slug as a category first, then a tag",
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    xml = await _term_feed_xml(db, slug=slug, fmt="rss", taxonomy=taxonomy)
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


@router.get(
    "/feed/atom/{slug}",
    summary="Atom feed for one category or tag",
    response_class=Response,
)
async def atom_term_feed(
    slug: str,
    taxonomy: str = Query(
        "auto",
        pattern="^(auto|category|tag)$",
        description="auto resolves the slug as a category first, then a tag",
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    xml = await _term_feed_xml(db, slug=slug, fmt="atom", taxonomy=taxonomy)
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


async def _term_feed_xml(
    db: AsyncSession,
    *,
    slug: str,
    fmt: str,
    taxonomy: str,
) -> str:
    """Feed XML for one category/tag slug; 404 when the slug matches neither."""
    settings = await _feed_settings(db)
    if taxonomy in {"auto", "category", "tag"}:
        # auto: generate_term_feed resolves the slug as category, then tag.
        if taxonomy == "auto":
            return await generate_term_feed(db, slug=slug, fmt=fmt, **settings)
        scope = {f"{taxonomy}_slug": slug}
        generator = generate_rss_feed if fmt == "rss" else generate_atom_feed
        return await generator(db, **settings, **scope)
    raise ValueError(f"Unknown feed taxonomy: {taxonomy}")


# ============================================================================
# Public Comment Endpoints (on router)
# ============================================================================


@router.get(
    "/posts/{post_id}/comments",
    response_model=BlogCommentListResponse,
    summary="List approved comments for a post",
)
async def list_post_comments(
    post_id: uuid.UUID,
    threaded: bool = Query(
        True,
        description="Nest replies under their parents (false = flat list of all comments)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> BlogCommentListResponse:
    svc = CommentService(db)
    return await svc.list_comments(
        post_id=post_id,
        status=CommentStatus.APPROVED,
        page=page,
        page_size=page_size,
        include_replies=threaded,
    )


@router.get(
    "/comments",
    response_model=BlogCommentListResponse,
    summary="List approved comments for any commentable resource (post or page)",
)
async def list_resource_comments(
    resource_type: str = Query(
        "blog_post",
        pattern="^(blog_post|cms_page)$",
        description="Which CMS object type the comments belong to",
    ),
    resource_id: uuid.UUID = Query(..., description="UUID of the target post or page"),
    threaded: bool = Query(
        True,
        description="Nest replies under their parents (false = flat list of all comments)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> BlogCommentListResponse:
    svc = CommentService(db)
    return await svc.list_comments(
        resource_type=resource_type,
        resource_id=resource_id,
        status=CommentStatus.APPROVED,
        page=page,
        page_size=page_size,
        include_replies=threaded,
    )


@router.post(
    "/comments",
    response_model=BlogCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a comment on any commentable resource (post or page)",
)
async def create_resource_comment(
    data: BlogCommentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] | None = Depends(get_current_user_optional),
) -> BlogCommentResponse:
    svc = CommentService(db)
    author_id = None
    if current_user:
        try:
            author_id = uuid.UUID(current_user["sub"])
        except Exception:
            pass
    return await svc.create_comment(
        data,
        author_id=author_id,
        author_ip=get_real_client_ip(request),
        author_user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "/posts/by-id/{post_id}/slug",
    summary="Resolve a post slug from its id (permalink middleware helper)",
)
async def get_post_slug_by_id(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Map ``%post_id%`` permalink structures back to a canonical slug.

    The Next.js middleware rewrites pretty URLs onto the file-tree routes;
    numeric structures carry no slug, so it resolves the identity here. Only
    the slug is exposed — the same field every list endpoint already gives.
    """
    from app.core.exceptions.handlers import NotFoundError

    from app.modules.blog.domain.models import BlogPost

    post = await db.get(BlogPost, post_id)
    if post is None or post.deleted_at is not None:
        raise NotFoundError(resource="BlogPost")
    return {"slug": post.slug}


@router.post(
    "/posts/{post_id}/comments",
    response_model=BlogCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a comment on a post",
)
async def create_comment(
    post_id: uuid.UUID,
    data: BlogCommentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] | None = Depends(get_current_user_optional),
) -> BlogCommentResponse:
    svc = CommentService(db)
    author_id = None
    if current_user:
        try:
            author_id = uuid.UUID(current_user["sub"])
        except Exception:
            pass
    # Override post_id from path
    data.post_id = post_id
    return await svc.create_comment(
        data,
        author_id=author_id,
        author_ip=get_real_client_ip(request),
        author_user_agent=request.headers.get("user-agent"),
    )


# ============================================================================
# Admin Endpoints (on admin_router: /api/v1/admin/blog/...)
# ============================================================================


@admin_router.get(
    "/posts",
    response_model=BlogListResponse,
    summary="List blog posts in any status (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_list_posts(
    category: str | None = Query(None, description="Filter by category slug"),
    status_filter: BlogPostStatus | None = Query(
        None, alias="status", description="draft / pending_review / published / archived; omit for all"
    ),
    search: str | None = Query(None, description="Search title/excerpt/content"),
    sort: str | None = Query(
        None,
        description="Strapi-style ordering: <field>[:asc|desc] — title, published_at, created_at, updated_at",  # noqa: E501
    ),
    include_trashed: bool = Query(False, description="Include soft-deleted posts"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> BlogListResponse:
    svc = BlogService(db)
    return await svc.list_posts(
        category_slug=category,
        status=status_filter,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
        include_trashed=include_trashed,
    )


@admin_router.get(
    "/posts/{post_id}",
    response_model=BlogPostDetailResponse,
    summary="Get blog post by id, any status (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BlogPostDetailResponse:
    svc = BlogService(db)
    return await svc.get_post_by_id(post_id)


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
    return await svc.create_post(
        data,
        author_id=author_id,
        # The status is client-supplied; without the actor's permissions a
        # contributor could publish by sending {"status": "published"}.
        permissions=set(current_user.get("permissions") or ()),
    )


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
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    svc = BlogService(db)
    await _require_post_access(post_id, current_user, db)
    try:
        actor_id = uuid.UUID(current_user["sub"])
    except Exception:
        actor_id = None
    return await svc.update_post(
        post_id=post_id,
        data=data,
        actor_id=actor_id,
        # Same publish check as create: patching status to "published" is
        # publishing, and the route guard alone only proves blog:write.
        permissions=set(current_user.get("permissions") or ()),
    )


@admin_router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete blog post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_delete_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    svc = BlogService(db)
    await _require_post_access(post_id, current_user, db)
    await svc.delete_post(post_id=post_id)


@admin_router.post(
    "/posts/{post_id}/restore",
    response_model=BlogPostDetailResponse,
    summary="Restore a trashed blog post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_restore_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    await _require_post_access(post_id, current_user, db)
    svc = BlogService(db)
    return await svc.restore_post(post_id=post_id)


@admin_router.delete(
    "/posts/{post_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a trashed blog post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_hard_delete_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    # Permanent delete is what the storefront admin's "delete permanently"
    # button actually calls, so an ungated route here left the original
    # complaint wide open: any blog:write holder could destroy another
    # author's post outright.
    await _require_post_access(post_id, current_user, db)
    svc = BlogService(db)
    await svc.hard_delete_post(post_id=post_id)


# ── Admin Comment Moderation ─────────────────────────────────────────────


@admin_router.get(
    "/comments",
    response_model=BlogCommentAdminListResponse,
    summary="List all comments (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_list_comments(
    post_id: uuid.UUID | None = Query(None, description="Filter by post"),
    resource_type: str | None = Query(
        None,
        pattern="^(blog_post|cms_page)$",
        description="Filter by resource type (alone, or paired with resource_id)",
    ),
    resource_id: uuid.UUID | None = Query(
        None, description="Filter by target object UUID (pairs with resource_type)"
    ),
    comment_status: CommentStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
    threaded: bool = Query(
        False,
        description="Nest replies under their parents (default: flat list)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> BlogCommentListResponse:
    svc = CommentService(db)
    return await svc.list_comments(
        post_id=post_id,
        status=comment_status,
        page=page,
        page_size=page_size,
        include_replies=threaded,
        resource_type=resource_type,
        resource_id=resource_id,
        # Behind ``_require_blog_write``: the moderation table shows the
        # commenter's address, so it must be the admin schema.
        include_moderation_fields=True,
    )


@admin_router.patch(
    "/comments/{comment_id}",
    response_model=BlogCommentAdminResponse,
    summary="Update or moderate a comment (Admin)",
    dependencies=[_require_moderate_comments],
)
async def admin_update_comment(
    comment_id: uuid.UUID,
    data: BlogCommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogCommentResponse:
    # Moderating on someone else's post rewrites their page: the comment body,
    # its status and its visibility are all part of what a reader sees there.
    # The check resolves through the parent post, since a comment has no author
    # in the sense that matters for this question.
    await _require_comment_access(comment_id, current_user, db)
    svc = CommentService(db)
    return await svc.update_comment(comment_id, data)


@admin_router.post(
    "/comments/{comment_id}/approve",
    response_model=BlogCommentAdminResponse,
    summary="Approve a comment (Admin)",
    dependencies=[_require_moderate_comments],
)
async def admin_approve_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogCommentResponse:
    await _require_comment_access(comment_id, current_user, db)
    svc = CommentService(db)
    return await svc.moderate_comment(comment_id, CommentStatus.APPROVED)


@admin_router.post(
    "/comments/{comment_id}/spam",
    response_model=BlogCommentAdminResponse,
    summary="Mark a comment as spam (Admin)",
    dependencies=[_require_moderate_comments],
)
async def admin_spam_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogCommentResponse:
    await _require_comment_access(comment_id, current_user, db)
    svc = CommentService(db)
    return await svc.moderate_comment(comment_id, CommentStatus.SPAM)


@admin_router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment (Admin)",
    dependencies=[_require_moderate_comments],
)
async def admin_delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    await _require_comment_access(comment_id, current_user, db)
    svc = CommentService(db)
    await svc.delete_comment(comment_id)


# ── Admin Duplicate & Post Meta ──────────────────────────────────────────


@admin_router.post(
    "/posts/{post_id}/duplicate",
    response_model=BlogPostDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a blog post as a new draft (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_duplicate_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    await _require_post_access(post_id, current_user, db)
    # `svc` was never bound here, so a successful duplicate raised NameError
    # and 500'd instead of creating the post.
    svc = BlogService(db)
    try:
        actor_id = uuid.UUID(current_user["sub"])
    except Exception:
        actor_id = None
    return await svc.duplicate_post(post_id, author_id=actor_id)


@admin_router.get(
    "/posts/{post_id}/meta",
    response_model=list[BlogPostMetaResponse],
    summary="List custom fields for a post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_list_post_meta(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[BlogPostMetaResponse]:
    from app.modules.blog.domain.models import BlogPostMeta
    from sqlalchemy import select

    stmt = select(BlogPostMeta).where(BlogPostMeta.post_id == post_id).order_by(BlogPostMeta.meta_key)
    rows = (await db.execute(stmt)).scalars().all()
    return [BlogPostMetaResponse.model_validate(r) for r in rows]


@admin_router.post(
    "/posts/{post_id}/meta",
    response_model=BlogPostMetaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add or update a custom field (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_upsert_post_meta(
    post_id: uuid.UUID,
    data: BlogPostMetaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostMetaResponse:
    await _require_post_access(post_id, current_user, db)
    from app.modules.blog.domain.models import BlogPostMeta
    from sqlalchemy import select

    stmt = select(BlogPostMeta).where(
        BlogPostMeta.post_id == post_id,
        BlogPostMeta.meta_key == data.meta_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.meta_value = data.meta_value
        await db.commit()
        await db.refresh(existing)
        return BlogPostMetaResponse.model_validate(existing)

    meta = BlogPostMeta(post_id=post_id, meta_key=data.meta_key, meta_value=data.meta_value)
    db.add(meta)
    await db.commit()
    await db.refresh(meta)
    return BlogPostMetaResponse.model_validate(meta)


@admin_router.delete(
    "/posts/{post_id}/meta/{meta_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom field (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_delete_post_meta(
    post_id: uuid.UUID,
    meta_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    await _require_post_access(post_id, current_user, db)
    from app.modules.blog.domain.models import BlogPostMeta
    from sqlalchemy import select

    stmt = select(BlogPostMeta).where(
        BlogPostMeta.post_id == post_id,
        BlogPostMeta.meta_key == meta_key,
    )
    meta = (await db.execute(stmt)).scalar_one_or_none()
    if meta:
        await db.delete(meta)
        await db.commit()


# ── Admin Post Locking ───────────────────────────────────────────────────


@admin_router.post(
    "/posts/{post_id}/lock",
    summary="Acquire editing lock on a post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_acquire_lock(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    # `db` was missing from this signature, so `_require_post_access` raised
    # NameError and the bare `except` below turned it into a plain 200 instead
    # of 403. The access check must run for real, and a 403 from it must not be
    # swallowed into a "benign" answer — hence HTTPException is re-raised.
    await _require_post_access(post_id, current_user, db)
    user_id = uuid.UUID(current_user["sub"])
    acquired = await PostLockService.acquire(post_id, user_id)
    if not acquired:
        holder = await PostLockService.get_lock_holder(post_id)
        return {"locked": False, "locked_by": str(holder) if holder else None}
    return {"locked": True, "locked_by": str(user_id)}


@admin_router.delete(
    "/posts/{post_id}/lock",
    summary="Release editing lock on a post (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_release_lock(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, bool]:
    await _require_post_access(post_id, current_user, db)
    user_id = uuid.UUID(current_user["sub"])
    released = await PostLockService.release(post_id, user_id)
    return {"released": released}


@admin_router.post(
    "/posts/{post_id}/lock/heartbeat",
    summary="Extend editing lock TTL (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_lock_heartbeat(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, bool]:
    await _require_post_access(post_id, current_user, db)
    user_id = uuid.UUID(current_user["sub"])
    extended = await PostLockService.heartbeat(post_id, user_id)
    return {"extended": extended}


@admin_router.get(
    "/posts/{post_id}/lock",
    summary="Check who holds the editing lock (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_check_lock(
    post_id: uuid.UUID,
) -> dict[str, Any]:
    holder = await PostLockService.get_lock_holder(post_id)
    return {"locked": holder is not None, "locked_by": str(holder) if holder else None}


# ── Admin Autosave & Preview ─────────────────────────────────────────────


@admin_router.post(
    "/posts/{post_id}/autosave",
    summary="Store autosave snapshot (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_autosave(
    post_id: uuid.UUID,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    await _require_post_access(post_id, current_user, db)
    user_id = uuid.UUID(current_user["sub"])
    result = await AutosaveService.save(post_id, user_id, data)
    return {"saved": bool(result), "saved_at": result.get("saved_at")}


@admin_router.get(
    "/posts/{post_id}/autosave",
    summary="Retrieve autosave snapshot (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_get_autosave(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    await _require_post_access(post_id, current_user, db)
    user_id = uuid.UUID(current_user["sub"])
    result = await AutosaveService.get(post_id, user_id)
    if result:
        return {"has_autosave": True, **result}
    return {"has_autosave": False}


@admin_router.delete(
    "/posts/{post_id}/autosave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear autosave after explicit save (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_clear_autosave(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    await _require_post_access(post_id, current_user, db)
    user_id = uuid.UUID(current_user["sub"])
    await AutosaveService.clear(post_id, user_id)


@admin_router.get(
    "/posts/{post_id}/preview",
    response_model=BlogPostDetailResponse,
    summary="Preview a post in any status without publishing (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_preview_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    # Preview returns a post in *any* status, so it hands out drafts and
    # pending-review content — content that is not on the public site precisely
    # because it has not been approved yet. Ungated, this was a read-only
    # exfiltration path for every writer's unpublished work.
    await _require_post_access(post_id, current_user, db)
    svc = BlogService(db)
    return await svc.get_post_by_id(post_id)


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


@admin_router.post(
    "/tags",
    response_model=BlogTagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create blog tag (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_create_tag(
    data: BlogTagCreate,
    db: AsyncSession = Depends(get_db),
) -> BlogTagResponse:
    svc = BlogService(db)
    return await svc.create_tag(data)


@admin_router.get(
    "/posts/{post_id}/revisions",
    response_model=list[BlogPostRevisionResponse],
    summary="List blog post revisions (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_list_post_revisions(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[BlogPostRevisionResponse]:
    svc = BlogService(db)
    return await svc.list_revisions(post_id)


@admin_router.get(
    "/posts/{post_id}/revisions/{revision_number}",
    response_model=BlogPostRevisionDetailResponse,
    summary="Get a blog post revision (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_get_post_revision(
    post_id: uuid.UUID,
    revision_number: int,
    db: AsyncSession = Depends(get_db),
) -> BlogPostRevisionDetailResponse:
    svc = BlogService(db)
    return await svc.get_revision(post_id, revision_number)


@admin_router.post(
    "/posts/{post_id}/revisions/{revision_number}/restore",
    response_model=BlogPostDetailResponse,
    summary="Restore a blog post to a revision (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_restore_post_revision(
    post_id: uuid.UUID,
    revision_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    await _require_post_access(post_id, current_user, db)
    # Same missing binding as admin_duplicate_post above.
    svc = BlogService(db)
    try:
        actor_id = uuid.UUID(current_user["sub"])
    except Exception:
        actor_id = None
    return await svc.restore_revision(post_id, revision_number, actor_id=actor_id)


@admin_router.get(
    "/posts/{post_id}/revisions/{rev_a_id}/diff/{rev_b_id}",
    response_model=RevisionDiffResponse,
    summary="Field-level diff between two post revisions (Admin)",
    description=(
        "Compares title, excerpt, body (with a word-level inline diff), slug, "
        "status, cover image, and the snapshotted SEO fields."
    ),
    dependencies=[_require_blog_write],
)
async def admin_diff_post_revisions(
    post_id: uuid.UUID,
    rev_a_id: uuid.UUID,
    rev_b_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RevisionDiffResponse:
    from app.modules.blog.application.revision_diff_service import diff_post_revisions

    return await diff_post_revisions(db, post_id, rev_a_id, rev_b_id)


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
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogPostDetailResponse:
    return await admin_update_post(post_id=post_id, data=data, db=db, current_user=current_user)


@router.delete(
    "/admin/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_delete_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    # `current_user` must be passed through: the delete path resolves the
    # author from it, and leaving the parameter on its Depends() default made
    # the capability check call .get() on a Depends object, raising an
    # AttributeError that paused the whole site via recovery mode.
    await admin_delete_post(post_id=post_id, db=db, current_user=current_user)


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


@router.post(
    "/admin/tags",
    response_model=BlogTagResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_create_tag(
    data: BlogTagCreate,
    db: AsyncSession = Depends(get_db),
) -> BlogTagResponse:
    from app.modules.blog.application.blog_service import BlogService

    return await BlogService(db).create_tag(data)


@router.patch(
    "/admin/categories/{category_id}",
    response_model=BlogCategoryResponse,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_update_category(
    category_id: uuid.UUID,
    data: BlogCategoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryResponse:
    from app.modules.blog.application.blog_service import BlogService

    return await BlogService(db).update_category(category_id, data)


@router.delete(
    "/admin/categories/{category_id}",
    response_model=BlogCategoryDeleteResult,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryDeleteResult:
    from app.modules.blog.application.blog_service import BlogService

    return await BlogService(db).delete_category(category_id)


@router.patch(
    "/admin/tags/{tag_id}",
    response_model=BlogTagResponse,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_update_tag(
    tag_id: uuid.UUID,
    data: BlogTagUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlogTagResponse:
    from app.modules.blog.application.blog_service import BlogService

    return await BlogService(db).update_tag(tag_id, data)


@router.delete(
    "/admin/tags/{tag_id}",
    response_model=BlogCategoryDeleteResult,
    include_in_schema=False,
    dependencies=[_require_blog_write],
)
async def router_alias_delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BlogCategoryDeleteResult:
    from app.modules.blog.application.blog_service import BlogService

    return await BlogService(db).delete_tag(tag_id)


# ── Comment meta ────────────────────────────────────────────────────────────
# The blog_comment_meta table existed with no reader or writer, so a stored key
# could never be read back. Same shape as the post meta routes above.


@admin_router.get(
    "/comments/{comment_id}/meta",
    summary="List custom fields for a comment (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_list_comment_meta(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.blog.application.meta_service import CommentMetaService

    return await CommentMetaService.list(db, comment_id)


@admin_router.post(
    "/comments/{comment_id}/meta",
    summary="Add or update a custom field on a comment (Admin)",
    dependencies=[_require_moderate_comments],
)
async def admin_upsert_comment_meta(
    comment_id: uuid.UUID,
    data: BlogPostMetaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.blog.application.meta_service import CommentMetaService

    await _require_comment_access(comment_id, current_user, db)
    return await CommentMetaService.upsert(db, comment_id, data.meta_key, data.meta_value)


@admin_router.delete(
    "/comments/{comment_id}/meta/{meta_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom field from a comment (Admin)",
    dependencies=[_require_moderate_comments],
)
async def admin_delete_comment_meta(
    comment_id: uuid.UUID,
    meta_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    from app.modules.blog.application.meta_service import CommentMetaService

    await _require_comment_access(comment_id, current_user, db)
    await CommentMetaService.delete(db, comment_id, meta_key)


# ── Term meta ───────────────────────────────────────────────────────────────
# Keyed by (term_type, term_id) because a term id is unique only within its
# taxonomy — a category, a tag, and a custom-taxonomy term can share an id.


@admin_router.get(
    "/terms/{term_type}/{term_id}/meta",
    summary="List custom fields for a term (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_list_term_meta(
    term_type: str,
    term_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.blog.application.meta_service import TermMetaService

    return await TermMetaService.list(db, term_type, term_id)


@admin_router.post(
    "/terms/{term_type}/{term_id}/meta",
    summary="Add or update a custom field on a term (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_upsert_term_meta(
    term_type: str,
    term_id: uuid.UUID,
    data: BlogPostMetaCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.blog.application.meta_service import TermMetaService

    return await TermMetaService.upsert(db, term_type, term_id, data.meta_key, data.meta_value)


@admin_router.delete(
    "/terms/{term_type}/{term_id}/meta/{meta_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom field from a term (Admin)",
    dependencies=[_require_blog_write],
)
async def admin_delete_term_meta(
    term_type: str,
    term_id: uuid.UUID,
    meta_key: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.modules.blog.application.meta_service import TermMetaService

    await TermMetaService.delete(db, term_type, term_id, meta_key)


@router.get(
    "/posts/{slug}/alternates",
    summary="Locale alternates for a post (hreflang source)",
)
async def post_alternates(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The post's own locale plus every translation in its group.

    Hrefs are built from the operator's permalink structure, so an alternate
    points at the path that actually serves that translation rather than at a
    guessed /blog/<slug>.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.exceptions.handlers import NotFoundError
    from app.modules.blog.domain.models import BlogPost
    from app.modules.settings.application.site_options_service import SiteOptionsService
    from app.shared.permalinks import PermalinkParts, build_post_path, is_default_structure

    # ``category`` is eager-loaded: ``_path`` touches ``row.category.slug`` and
    # the relationship is lazy="select", so without this a custom permalink
    # structure raised MissingGreenlet on every post whose category was not
    # already in the identity map.
    post = (await db.execute(
        select(BlogPost)
        .options(selectinload(BlogPost.category))
        .where(BlogPost.slug == slug, BlogPost.deleted_at.is_(None))
    )).scalar_one_or_none()
    if post is None:
        raise NotFoundError("BlogPost", f"نوشته با اسلاگ {slug} یافت نشد.")

    structure = await SiteOptionsService.get(db, "permalink_structure")

    # ``BlogPost`` has no ``author`` relationship — only ``author_id`` — so the
    # old ``row.author.author_slug`` raised AttributeError. That is not an
    # AppException, so it reached the generic handler, which calls
    # RecoveryMode.pause(): every article page 500'd and the whole store
    # served 503 for 60 minutes whenever an operator picked one of the four
    # non-default permalink presets the settings screen offers. Resolve the
    # slug from the users row the same way BlogService.get_author_slug does.
    author_slugs: dict[uuid.UUID, str] = {}
    author_ids = {p.author_id for p in [post] if p.author_id}
    if post.translation_group is not None:
        author_ids |= {
            s.author_id
            for s in (await db.execute(
                select(BlogPost.author_id).where(
                    BlogPost.translation_group == post.translation_group,
                    BlogPost.id != post.id,
                    BlogPost.status == "published",
                    BlogPost.deleted_at.is_(None),
                )
            )).scalars().all()
            if s is not None
        }
    if author_ids:
        from app.modules.users.domain.models import User

        rows = await db.execute(select(User.id, User.author_slug).where(User.id.in_(author_ids)))
        author_slugs = {uid: slug for uid, slug in rows.all() if slug}

    def _path(row: Any) -> str:
        if not structure or is_default_structure(structure):
            return f"/blog/{row.slug}"
        published = row.published_at or datetime.now(UTC)
        return build_post_path(structure, PermalinkParts(
            postname=row.slug,
            post_id=str(row.id),
            year=f"{published.year:04d}",
            monthnum=f"{published.month:02d}",
            day=f"{published.day:02d}",
            category=row.category.slug if row.category else "",
            author=author_slugs.get(row.author_id, "") if row.author_id else "",
        ))

    alternates: list[dict[str, str]] = [
        {"locale": post.locale, "slug": post.slug, "path": _path(post)}
    ]
    if post.translation_group is not None:
        siblings = (await db.execute(
            select(BlogPost)
            .options(selectinload(BlogPost.category))
            .where(
                BlogPost.translation_group == post.translation_group,
                BlogPost.id != post.id,
                BlogPost.status == "published",
                BlogPost.deleted_at.is_(None),
            )
        )).scalars().all()
        alternates += [
            {"locale": s.locale, "slug": s.slug, "path": _path(s)} for s in siblings
        ]
    return {"self": {"locale": post.locale, "slug": post.slug}, "alternates": alternates}


@router.get("/posts/{slug}/neighbors", summary="Adjacent published posts (public)")
async def post_neighbors(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The previous and next published post, by publish time.

    WordPress exposes these as get_previous_post()/get_next_post(); without
    them a reader who lands mid-archive has no way to keep reading.
    """
    from sqlalchemy import and_, or_, select

    from app.core.exceptions.handlers import NotFoundError
    from app.modules.blog.domain.models import BlogPost

    post = (await db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.deleted_at.is_(None))
    )).scalar_one_or_none()
    if post is None:
        raise NotFoundError("BlogPost", f"نوشته با اسلاگ {slug} یافت نشد.")

    published = post.published_at or post.created_at

    def _summary(row: BlogPost | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": str(row.id),
            "slug": row.slug,
            "title": row.title,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }

    # "Previous" is the most recent post published before this one; ties are
    # broken by id so two posts with the same timestamp stay deterministic.
    previous = (await db.execute(
        select(BlogPost).where(
            BlogPost.status == "published",
            BlogPost.deleted_at.is_(None),
            BlogPost.id != post.id,
            or_(BlogPost.published_at < published, and_(
                BlogPost.published_at == published, BlogPost.id < post.id)),
        ).order_by(BlogPost.published_at.desc(), BlogPost.id.desc()).limit(1)
    )).scalar_one_or_none()

    following = (await db.execute(
        select(BlogPost).where(
            BlogPost.status == "published",
            BlogPost.deleted_at.is_(None),
            BlogPost.id != post.id,
            or_(BlogPost.published_at > published, and_(
                BlogPost.published_at == published, BlogPost.id > post.id)),
        ).order_by(BlogPost.published_at.asc(), BlogPost.id.asc()).limit(1)
    )).scalar_one_or_none()

    return {"previous": _summary(previous), "next": _summary(following)}


@router.get("/archive/{year}", summary="Posts published in a year (public)")
@router.get("/archive/{year}/{month}", summary="Posts published in a month (public)")
async def post_date_archive(
    year: int,
    month: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Date archive, the /2026/09 form the permalink structure advertises.

    The permalink tokens %year%/%monthnum%/%day% already produced these paths
    in links, but nothing served them, so every date-based permalink 404'd.
    """
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from app.core.exceptions.handlers import ValidationError
    from app.modules.blog.domain.models import BlogPost

    if not 1970 <= year <= 2200:
        raise ValidationError(f"سال نامعتبر: {year}")
    if month is not None and not 1 <= month <= 12:
        raise ValidationError(f"ماه نامعتبر: {month}")

    window_start = datetime(year, month or 1, 1, tzinfo=UTC)
    window_end = (
        datetime(year + 1, 1, 1, tzinfo=UTC) if month is None
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    published = BlogPost.published_at.between(window_start, window_end)
    live = (BlogPost.status == "published", BlogPost.deleted_at.is_(None))

    total = (await db.execute(
        select(func.count()).select_from(BlogPost).where(*live, published)
    )).scalar_one()
    rows = (await db.execute(
        select(BlogPost).where(*live, published)
        .order_by(BlogPost.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "year": year,
        "month": month,
        "total": total,
        "page": page,
        "page_size": page_size,
        "posts": [
            {
                "id": str(p.id), "slug": p.slug, "title": p.title,
                "excerpt": p.excerpt, "cover_image_url": p.cover_image_url,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in rows
        ],
    }


class BlogBulkActionRequest(BaseModel):
    """Post ids to act on. Capped so one request cannot fan out unbounded."""

    ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Post ids to act on (max 200 per request)",
    )


class BlogBulkActionResponse(BaseModel):
    action: str
    ok: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=0)
    results: list[dict[str, Any]]


@admin_router.post(
    "/posts/bulk/{action}",
    response_model=BlogBulkActionResponse,
    summary="Bulk publish/draft/archive/trash/restore blog posts (admin)",
    dependencies=[_require_blog_write],
)
async def admin_bulk_posts(
    action: str,
    body: BlogBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BlogBulkActionResponse:
    """One action over many posts.

    Per-post ownership is re-checked inside the service, so this is exactly as
    strict as the equivalent individual calls — and the response reports a
    per-post outcome rather than a single boolean, because "20 selected, 17
    done, 3 not yours" and "20 done" are different facts.
    """
    svc = BlogService(db)
    result = await svc.bulk_posts(body.ids, action, actor_payload=current_user)
    return BlogBulkActionResponse(**result)
