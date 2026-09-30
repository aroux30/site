"""Content API routes: Homepage Blocks, Tree Menus, FAQs, and CMS pages (Karta Phase 7/9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user
from app.modules.content.application import cms_page_service, content_service, single_type_service
from app.modules.content.application.reusable_block_service import ReusableBlockService
from app.modules.content.domain.models import MenuLocation, PageStatus
from app.modules.content.schemas.content import (
    BlockPatternCategoryGroup,
    BlockPatternRenderRequest,
    BlockPatternRenderResponse,
    BlockReorderRequest,
    BulkActionRequest,
    BulkActionResult,
    CmsPageCreateRequest,
    CmsPageListResponse,
    CmsPageResponse,
    CmsPageRevisionResponse,
    CmsPageUpdateRequest,
    FAQItemCreateRequest,
    FAQItemResponse,
    FAQItemUpdateRequest,
    FAQListWithGoogleSchemaResponse,
    HomepageBlockCreateRequest,
    HomepageBlockResponse,
    HomepageBlockUpdateRequest,
    MenuItemCreateRequest,
    MenuItemResponse,
    MenuItemUpdateRequest,
    PublicPageSummary,
    PublicPageSummaryList,
    ReusableBlockCreateRequest,
    ReusableBlockResponse,
    ReusableBlockUpdateRequest,
    RevisionDiffResponse,
    SingleTypeResponse,
    SingleTypeUpdateRequest,
    SitemapEntriesResponse,
    TreeMenuItemNode,
)

router = APIRouter(tags=["content"])

_require_content_write = Depends(RequirePermissions("settings:write"))

_FAQ_CACHE_PATTERN = "content:faqs:*"


def _actor_id(current_user: dict[str, Any] | None) -> uuid.UUID | None:
    """UUID of the authenticated actor, or None when it cannot be resolved."""
    if not current_user:
        return None
    try:
        return uuid.UUID(str(current_user.get("sub")))
    except (TypeError, ValueError):
        return None


async def _require_page_access(
    page_id: uuid.UUID,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Gate a page mutation on ownership, not just on ``settings:write``.

    ``_require_content_write`` proves the caller may edit site content; it
    says nothing about *whose*. This is the per-object half of the check (the
    ``map_meta_cap`` equivalent) and is what keeps one settings-writer from
    silently rewriting another's page.

    Loaded by primary key rather than through the service, and raising the
    service's own ``NotFoundError`` shape, so a missing page still returns
    404 instead of a 403 that would double as an existence oracle.
    """
    from app.core.security.object_capabilities import (
        OBJECT_RULES,
        require_object_capability,
    )
    from app.modules.content.domain.models import CmsPage

    page = await db.get(CmsPage, page_id)
    if page is None:
        raise NotFoundError("CmsPage", f"Page {page_id} not found")

    await require_object_capability(current_user, page, OBJECT_RULES["pages"])


async def _require_entry_access(
    entry_id: uuid.UUID,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Gate a content-entry mutation on its creating revision's author.

    A ``ContentEntry`` has no author column — the schema is shared across
    every content type, so ownership is carried by the revision that created
    the row. Revisions are immutable and ``revision_number`` 1 is the
    creator, which makes it the only stable answer to "who owns this entry".

    The row is loaded with a single join to that revision rather than by
    primary key, because the object the guard needs is the revision (for its
    ``created_by``) and the entry (only to prove it exists).
    """
    from sqlalchemy import select

    from app.core.security.object_capabilities import (
        OBJECT_RULES,
        require_object_capability,
    )
    from app.modules.content.domain.builder import ContentEntry
    from app.modules.content.domain.entry_extras import ContentEntryRevision

    revision = (
        await db.execute(
            select(ContentEntryRevision)
            .join(ContentEntry, ContentEntry.id == ContentEntryRevision.entry_id)
            .where(
                ContentEntry.id == entry_id,
                ContentEntryRevision.revision_number == 1,
            )
        )
    ).scalar_one_or_none()
    if revision is None:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")

    await require_object_capability(
        current_user, revision, OBJECT_RULES["custom_posts"]
    )


async def _invalidate_faq_cache() -> None:
    """Drop cached FAQ payloads after any FAQ write (create/update/delete)."""
    from app.core.cache.redis import cache_delete_pattern

    await cache_delete_pattern(_FAQ_CACHE_PATTERN)



# ── Homepage Blocks Endpoints ─────────────────────────────────────────────


@router.get(
    "/blocks",
    response_model=list[HomepageBlockResponse],
    summary="Get active homepage layout blocks ordered by position",
)
async def get_homepage_blocks(
    db: AsyncSession = Depends(get_db),
) -> list[HomepageBlockResponse]:
    blocks = await content_service.get_active_homepage_blocks(db)
    return [HomepageBlockResponse.model_validate(b) for b in blocks]


@router.get(
    "/admin/blocks",
    response_model=list[HomepageBlockResponse],
    summary="List ALL homepage blocks incl. inactive (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def admin_list_blocks(
    db: AsyncSession = Depends(get_db),
) -> list[HomepageBlockResponse]:
    """Admin view: the public list hides inactive blocks, so an operator who
    switched one off could never see (or re-enable) it again."""
    blocks = await content_service.list_all_homepage_blocks(db)
    return [HomepageBlockResponse.model_validate(b) for b in blocks]


@router.post(
    "/admin/blocks",
    response_model=HomepageBlockResponse,
    summary="Create a new homepage block (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_block(
    body: HomepageBlockCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> HomepageBlockResponse:
    block = await content_service.create_homepage_block(
        db,
        title=body.title,
        block_type=body.block_type,
        config=body.config,
        position=body.position,
    )
    return HomepageBlockResponse.model_validate(block)


@router.put(
    "/admin/blocks/reorder",
    response_model=list[HomepageBlockResponse],
    summary="Reorder homepage blocks display positions (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def reorder_blocks(
    body: BlockReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> list[HomepageBlockResponse]:
    blocks = await content_service.reorder_homepage_blocks(db, positions=body.positions)
    return [HomepageBlockResponse.model_validate(b) for b in blocks]


# ── Hierarchical Tree Menus Endpoints ─────────────────────────────────────


@router.get(
    "/menus/{location}",
    response_model=list[TreeMenuItemNode],
    summary="Get hierarchical navigation tree for a location (header, footer, mobile)",
)
async def get_tree_menu(
    location: MenuLocation,
    db: AsyncSession = Depends(get_db),
) -> list[TreeMenuItemNode]:
    tree = await content_service.build_tree_menu(db, location=location)
    return [TreeMenuItemNode.model_validate(node) for node in tree]


@router.post(
    "/admin/menus",
    response_model=MenuItemResponse,
    summary="Add a menu navigation link (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_menu_item(
    body: MenuItemCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    item = await content_service.create_menu_item(
        db,
        location=body.location,
        title=body.title,
        url=body.url,
        parent_id=body.parent_id,
        position=body.position,
        icon=body.icon,
    )
    return MenuItemResponse.model_validate(item)


# ── FAQs with Automated Google FAQPage Schema.org ─────────────────────────


@router.get(
    "/faqs",
    response_model=FAQListWithGoogleSchemaResponse,
    summary="Get active FAQs with automated Google FAQPage Schema.org JSON-LD for rich snippets",
)
async def get_faqs(
    category: str | None = Query(None, description="Filter FAQs by category"),
    db: AsyncSession = Depends(get_db),
) -> FAQListWithGoogleSchemaResponse:
    from app.core.cache.redis import cache_get, cache_set

    clean_cat = category.strip().lower() if category else "all"
    cache_key = f"content:faqs:{clean_cat}"
    hit = await cache_get(cache_key)
    if hit:
        return FAQListWithGoogleSchemaResponse.model_validate_json(hit)

    res = await content_service.get_active_faqs_with_schema(db, category=category)
    response_obj = FAQListWithGoogleSchemaResponse(
        items=[FAQItemResponse.model_validate(f) for f in res["items"]],
        total=res["total"],
        schema_json_ld=res["schema_json_ld"],
    )
    await cache_set(cache_key, response_obj.model_dump_json(), ttl=3600)
    return response_obj


@router.post(
    "/admin/faqs",
    response_model=FAQItemResponse,
    summary="Create a new FAQ entry (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_faq(
    body: FAQItemCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> FAQItemResponse:
    from app.modules.content.domain.models import FAQItem

    faq = FAQItem(
        question=body.question.strip(),
        answer_html=body.answer_html,
        category=body.category.strip(),
        position=body.position,
        is_active=True,
    )
    db.add(faq)
    await db.flush()
    await _invalidate_faq_cache()
    return FAQItemResponse.model_validate(faq)


# ── CMS Pages (WordPress-style pages with revisions) ──────────────────────


@router.get(
    "/pages",
    response_model=PublicPageSummaryList,
    summary="List published CMS page addresses (storefront / sitemap)",
)
async def list_public_pages(
    locale: str | None = Query(None, description="Filter to one content language"),
    db: AsyncSession = Depends(get_db),
) -> PublicPageSummaryList:
    """Every published page's slug, for sitemap and navigation discovery.

    Unauthenticated by design — the sitemap generator has no session. It is
    therefore deliberately narrower than the admin list: no ``body_html``, no
    SEO overrides, no author, and trashed or draft pages are excluded. Keep it
    that way; widening the projection here would publish unpublished content.
    """
    pages = await cms_page_service.list_published_page_summaries(db, locale=locale)
    items = [PublicPageSummary.model_validate(p) for p in pages]
    return PublicPageSummaryList(items=items, total=len(items))


@router.get(
    "/sitemap-entries",
    response_model=SitemapEntriesResponse,
    summary="Every crawlable address in one payload: pages, blog taxonomy, products",
)
async def get_sitemap_entries(
    db: AsyncSession = Depends(get_db),
) -> SitemapEntriesResponse:
    """Extended sitemap source for the storefront ``sitemap.ts``.

    ``items``/``total`` keep the exact shape of ``GET /pages``; blog
    categories/tags, active products, and the rendered XML ``<url>`` fragment
    are additive keys. Unauthenticated by design — the sitemap generator has
    no session. Blog/catalog sections fail open: an outage skips that section
    instead of dropping the whole sitemap.
    """
    from app.modules.content.application import sitemap_service

    return await sitemap_service.build_sitemap_payload(db)


@router.get(
    "/pages/{slug}",
    response_model=CmsPageResponse,
    summary="Get a published CMS page by slug (storefront)",
)
async def get_page(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> CmsPageResponse:
    page = await cms_page_service.get_page_by_slug(db, slug, only_published=True)
    return await _rendered(db, page)


@router.get(
    "/pages/by-path/{path:path}",
    response_model=CmsPageResponse,
    summary="Get a published CMS page by its parent/child path (storefront)",
)
async def get_page_by_path(
    path: str,
    db: AsyncSession = Depends(get_db),
) -> CmsPageResponse:
    """Resolve a nested page path, e.g. ``about/team/history``.

    Declared after ``/pages/{slug}`` deliberately: the single-segment route
    would otherwise match the first segment of a nested path. The path form
    also keeps a working ``/pages/<slug>`` link valid for every page, so
    nothing that already links to a page breaks when a tree is introduced.
    """
    page = await cms_page_service.get_page_by_slug_path(db, path, only_published=True)
    return await _rendered(db, page)


async def _rendered(db: AsyncSession, page: CmsPageResponse) -> CmsPageResponse:
    """Expand reusable blocks and shortcodes in a page body for display.

    Runs after sanitization, so a filter that injects raw markup here would
    reintroduce exactly what the sanitizer just removed. That is deliberate:
    plugins are trusted code in this codebase, not user input.
    """
    from app.shared.content.render import render_body

    body = await render_body(db, page.body_html)

    # ``HOOK_PAGE_BODY_RENDER`` was declared and never dispatched, so a plugin
    # binding it looked wired and silently never ran.
    from app.shared.plugins.registry import HOOK_PAGE_BODY_RENDER, registry

    body = await registry.apply_filters(
        HOOK_PAGE_BODY_RENDER, body, page_slug=page.slug
    )

    if body == page.body_html:
        return page
    return page.model_copy(update={"body_html": body})


@router.get(
    "/admin/pages/by-slug/{slug}",
    response_model=CmsPageResponse,
    summary="Preview a CMS page by slug in any status (admin)",
    dependencies=[_require_content_write],
)
async def admin_preview_page(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> CmsPageResponse:
    """Strapi-style preview: drafts are viewable to editors before publishing."""
    page = await cms_page_service.get_page_by_slug(db, slug, only_published=False)
    # Editors previewing a page also want to see their draft reusable blocks
    # in place, so preview resolves blocks that are not published yet.
    from app.shared.content.render import render_body

    body = await render_body(db, page.body_html, include_unpublished=True)
    return page if body == page.body_html else page.model_copy(update={"body_html": body})


@router.get(
    "/admin/pages",
    response_model=CmsPageListResponse,
    summary="List CMS pages (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_pages(
    status_filter: PageStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Match title or slug"),
    sort: str | None = Query(
        None,
        description="Strapi-style ordering: <field>[:asc|desc] — title, slug, status, published_at, created_at, updated_at",  # noqa: E501
    ),
    locale: str | None = Query(None, min_length=2, max_length=10),
    include_trashed: bool = Query(
        False, description="Include soft-deleted pages (trash) in the listing"
    ),
    db: AsyncSession = Depends(get_db),
) -> CmsPageListResponse:
    return await cms_page_service.list_pages(
        db,
        status=status_filter,
        search=search,
        sort=sort,
        locale=locale,
        include_trashed=include_trashed,
    )


@router.post(
    "/admin/pages",
    response_model=CmsPageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a CMS page (admin)",
    dependencies=[_require_content_write],
)
async def admin_create_page(
    body: CmsPageCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    author_id: uuid.UUID | None = None
    try:
        author_id = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = None
    return await cms_page_service.create_page(db, body, author_id=author_id)


@router.get(
    "/admin/pages/{page_id}",
    response_model=CmsPageResponse,
    summary="Get a CMS page by id, any status (admin preview)",
    dependencies=[_require_content_write],
)
async def admin_get_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CmsPageResponse:
    return await cms_page_service.get_page_by_id(db, page_id)


@router.patch(
    "/admin/pages/{page_id}",
    response_model=CmsPageResponse,
    summary="Update a CMS page (admin)",
    dependencies=[_require_content_write],
)
async def admin_update_page(
    page_id: uuid.UUID,
    body: CmsPageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    await _require_page_access(page_id, current_user, db)
    editor_id: uuid.UUID | None = _actor_id(current_user)
    return await cms_page_service.update_page(db, page_id, body, editor_id=editor_id)


@router.delete(
    "/admin/pages/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Trash a CMS page (soft delete, admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    await _require_page_access(page_id, current_user, db)
    await cms_page_service.delete_page(db, page_id)


@router.post(
    "/admin/pages/{page_id}/duplicate",
    response_model=CmsPageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a CMS page as a new draft (admin)",
    dependencies=[_require_content_write],
)
async def admin_duplicate_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    # Duplicating publishes a new page derived from someone else's, so it is a
    # write to *their* content, not a neutral read.
    await _require_page_access(page_id, current_user, db)
    try:
        author_id: uuid.UUID | None = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = None
    return await cms_page_service.duplicate_page(db, page_id, author_id=author_id)


@router.post(
    "/admin/pages/{page_id}/restore",
    response_model=CmsPageResponse,
    summary="Restore a trashed CMS page (admin)",
    dependencies=[_require_content_write],
)
async def admin_restore_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    await _require_page_access(page_id, current_user, db)
    return await cms_page_service.restore_page(db, page_id)


@router.delete(
    "/admin/pages/{page_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a trashed CMS page (admin)",
    dependencies=[_require_content_write],
)
async def admin_hard_delete_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    # Irreversible: there is no trash to restore from, so this is the route
    # where an over-broad guard does the most damage if it is missing.
    await _require_page_access(page_id, current_user, db)
    await cms_page_service.hard_delete_page(db, page_id)


@router.post(
    "/admin/pages/bulk/{action}",
    response_model=BulkActionResult,
    summary="Bulk publish/unpublish/trash/restore CMS pages (admin)",
    dependencies=[_require_content_write],
)
async def admin_bulk_pages(
    action: str,
    body: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> BulkActionResult:
    if action not in {"publish", "unpublish", "trash", "restore"}:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError(f"عملیات ناشناخته: {action}")
    try:
        actor_id: uuid.UUID | None = uuid.UUID(current_user["sub"])
    except Exception:
        actor_id = None
    return await cms_page_service.bulk_pages(
        db, body.ids, action, actor_id=actor_id, actor_payload=current_user
    )


@router.get(
    "/admin/pages/{page_id}/revisions",
    response_model=list[CmsPageRevisionResponse],
    summary="List a CMS page's revision history (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_page_revisions(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[CmsPageRevisionResponse]:
    return await cms_page_service.list_revisions(db, page_id)


@router.post(
    "/admin/pages/{page_id}/revisions/{revision_number}/restore",
    response_model=CmsPageResponse,
    summary="Restore a CMS page to an earlier revision (admin)",
    dependencies=[_require_content_write],
)
async def admin_restore_page_revision(
    page_id: uuid.UUID,
    revision_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    # Restoring a revision rewrites the live page, discarding whatever the
    # author has written since. It is an edit of *their* page, not of history.
    await _require_page_access(page_id, current_user, db)
    try:
        editor_id: uuid.UUID | None = uuid.UUID(current_user["sub"])
    except Exception:
        editor_id = None
    return await cms_page_service.restore_revision(
        db, page_id, revision_number, editor_id=editor_id
    )


@router.get(
    "/admin/pages/{page_id}/revisions/{rev_a}/diff/{rev_b}",
    response_model=RevisionDiffResponse,
    summary="Diff two revisions of a CMS page: field changes + inline body tokens (admin)",
    dependencies=[_require_content_write],
)
async def admin_diff_page_revisions(
    page_id: uuid.UUID,
    rev_a: int,
    rev_b: int,
    db: AsyncSession = Depends(get_db),
) -> RevisionDiffResponse:
    """Field-level comparison of two immutable revision snapshots.

    Revisions are addressed by revision number (not row id), matching the
    neighboring restore route. The response reports every compared field
    (title, slug, excerpt, status, SEO) with before/after values, plus
    word-level ``{op, text}`` tokens for ``body_html`` so the editor UI can
    highlight what moved inline.
    """
    from app.modules.content.application import revision_diff_service

    return await revision_diff_service.diff_page_revisions(db, page_id, rev_a, rev_b)


# ── Block patterns (code-registered section templates, WordPress parity) ────
#
# Like the shortcode registry, patterns live in code — no table, no migration.
# The editor lists them here, renders one with real copy via the render
# endpoint, and inserts the resulting HTML into a page body.


@router.get(
    "/block-patterns",
    response_model=list[BlockPatternCategoryGroup],
    summary="List code-registered block patterns grouped by category (editor)",
)
async def list_block_patterns() -> list[BlockPatternCategoryGroup]:
    """Ready-made section templates with their editable slots and defaults.

    Public read like the rest of the content registry surfaces: patterns are
    static templates, not content.
    """
    from app.modules.content.domain import block_patterns

    return [
        BlockPatternCategoryGroup.model_validate(group)
        for group in block_patterns.grouped_patterns()
    ]


@router.post(
    "/block-patterns/{slug}/render",
    response_model=BlockPatternRenderResponse,
    summary="Render one block pattern with variables substituted (admin)",
    dependencies=[_require_content_write],
)
async def render_block_pattern(
    slug: str,
    body: BlockPatternRenderRequest,
) -> BlockPatternRenderResponse:
    """Substitute ``variables`` into a pattern's ``{{slots}}``.

    Slots the caller omits fall back to their declared defaults, so rendering
    a fresh pattern yields sensible placeholder copy. Values are HTML-escaped
    before substitution. Unknown variables are ignored.
    """
    from app.modules.content.domain import block_patterns

    pattern = block_patterns.get_pattern(slug)
    html = block_patterns.render_pattern(slug, body.variables)
    applied = [v.name for v in pattern.variables if body.variables.get(v.name)]
    return BlockPatternRenderResponse(slug=slug, html=html, applied_variables=applied)


# ── URL embeds (oEmbed/Open Graph) for the editor ───────────────────────────


@router.get(
    "/admin/embed",
    summary="Resolve a URL into embed metadata (oEmbed/OG, admin)",
    dependencies=[_require_content_write],
)
async def admin_resolve_embed(
    url: str = Query(..., min_length=8, max_length=2000),
) -> dict[str, Any]:
    from app.modules.content.application import embed_service

    return await embed_service.resolve_embed(url)


# ── Content import/export (WordPress/Strapi parity) ─────────────────────────


@router.get(
    "/admin/content/export",
    summary="Export all CMS content as one JSON document (admin)",
    dependencies=[_require_content_write],
)
async def admin_export_content(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.content.application import transfer_service

    return await transfer_service.export_content(db)


@router.post(
    "/admin/content/import",
    summary="Import a CMS content JSON document (admin, upsert by slug)",
    dependencies=[_require_content_write],
)
async def admin_import_content(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, int]:
    from app.modules.content.application import transfer_service

    try:
        author_id: uuid.UUID | None = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = None
    return await transfer_service.import_content(db, body, author_id=author_id)


# ── Dynamic Content-Type Builder (Strapi parity) ────────────────────────────


class ContentTypeCreateRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=120)
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(None, max_length=500)
    kind: str = Field("collection", pattern="^(collection|single)$")
    fields: list[dict[str, Any]] = Field(..., min_length=1)


class ContentEntryWriteRequest(BaseModel):
    data: dict[str, Any]
    status: PageStatus = PageStatus.DRAFT
    locale: str = Field("fa", min_length=2, max_length=10)
    scheduled_publish_at: datetime | None = None


class ContentEntryPatchRequest(BaseModel):
    data: dict[str, Any] | None = None
    status: PageStatus | None = None
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None


@router.get(
    "/admin/content-types",
    summary="List dynamic content types (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_content_types(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.content.application import builder_service

    types = await builder_service.list_content_types(db)
    return [
        {
            "id": str(t.id),
            "slug": t.slug,
            "name": t.name,
            "kind": t.kind.value,
            "fields": t.fields,
            "description": t.description,
        }
        for t in types
    ]


@router.post(
    "/admin/content-types",
    status_code=status.HTTP_201_CREATED,
    summary="Create a dynamic content type (admin)",
    dependencies=[_require_content_write],
)
async def admin_create_content_type(
    body: ContentTypeCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.content.application import builder_service
    from app.modules.content.domain.builder import ContentTypeKind

    ct = await builder_service.create_content_type(
        db,
        slug=body.slug,
        name=body.name,
        fields=body.fields,
        kind=ContentTypeKind(body.kind),
        description=body.description,
    )
    return {"id": str(ct.id), "slug": ct.slug}


@router.get(
    "/content-types/{type_slug}/entries",
    summary="List published entries of a content type (storefront)",
)
async def list_public_entries(
    type_slug: str,
    locale: str | None = Query(None, min_length=2, max_length=10),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.content.application import builder_service

    entries = await builder_service.list_entries(
        db, type_slug, status=PageStatus.PUBLISHED, locale=locale
    )
    return [
        {"id": str(e.id), "data": e.data, "locale": e.locale, "position": e.position}
        for e in entries
    ]


@router.get(
    "/admin/content-types/{type_slug}/entries",
    summary="List entries of a content type in any status (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_entries(
    type_slug: str,
    status_filter: PageStatus | None = Query(None, alias="status"),
    locale: str | None = Query(None, min_length=2, max_length=10),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.content.application import builder_service

    entries = await builder_service.list_entries(
        db, type_slug, status=status_filter, locale=locale
    )
    return [
        {
            "id": str(e.id),
            "data": e.data,
            "status": e.status.value,
            "locale": e.locale,
            "position": e.position,
        }
        for e in entries
    ]


@router.post(
    "/admin/content-types/{type_slug}/entries",
    status_code=status.HTTP_201_CREATED,
    summary="Create a validated entry with first revision (admin)",
    dependencies=[_require_content_write],
)
async def admin_create_entry(
    type_slug: str,
    body: ContentEntryWriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.content.application import entry_revision_service

    try:
        author_id: uuid.UUID | None = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = None
    entry = await entry_revision_service.create_entry_v2(
        db,
        type_slug,
        body.data,
        status=body.status,
        locale=body.locale,
        scheduled_publish_at=body.scheduled_publish_at,
        author_id=author_id,
    )
    return {
        "id": str(entry.id),
        "data": entry.data,
        "status": entry.status.value,
        "revision_number": entry.revision_number,
    }


@router.patch(
    "/admin/entries/{entry_id}",
    summary="Update an entry (validated + revisioned, admin)",
    dependencies=[_require_content_write],
)
async def admin_update_entry(
    entry_id: uuid.UUID,
    body: ContentEntryPatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.content.application import entry_revision_service

    await _require_entry_access(entry_id, current_user, db)
    editor_id: uuid.UUID | None = _actor_id(current_user)
    entry = await entry_revision_service.update_entry_v2(
        db,
        entry_id,
        body.data or {},
        status=body.status,
        scheduled_publish_at=body.scheduled_publish_at,
        scheduled_unpublish_at=body.scheduled_unpublish_at,
        editor_id=editor_id,
    )
    return {
        "id": str(entry.id),
        "data": entry.data,
        "status": entry.status.value,
        "revision_number": entry.revision_number,
    }


@router.get(
    "/admin/entries/{entry_id}/revisions",
    summary="Entry revision history (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_entry_revisions(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.content.application import entry_revision_service

    revisions = await entry_revision_service.list_revisions(db, entry_id)
    return [
        {
            "id": str(r.id),
            "revision_number": r.revision_number,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in revisions
    ]


@router.post(
    "/admin/entries/{entry_id}/revisions/{revision_number}/restore",
    summary="Restore an entry to an earlier revision (admin)",
    dependencies=[_require_content_write],
)
async def admin_restore_entry_revision(
    entry_id: uuid.UUID,
    revision_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.content.application import entry_revision_service

    await _require_entry_access(entry_id, current_user, db)
    try:
        editor_id: uuid.UUID | None = uuid.UUID(current_user["sub"])
    except Exception:
        editor_id = None
    entry = await entry_revision_service.restore_revision(
        db, entry_id, revision_number, editor_id=editor_id
    )
    return {"id": str(entry.id), "revision_number": entry.revision_number}


@router.delete(
    "/admin/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Trash an entry (soft delete, admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    from app.modules.content.application import entry_revision_service

    await _require_entry_access(entry_id, current_user, db)
    await entry_revision_service.trash_entry(db, entry_id)


@router.post(
    "/admin/entries/{entry_id}/restore",
    summary="Restore a trashed entry (admin)",
    dependencies=[_require_content_write],
)
async def admin_restore_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    from app.modules.content.application import entry_revision_service

    await _require_entry_access(entry_id, current_user, db)
    entry = await entry_revision_service.restore_entry(db, entry_id)
    return {"id": str(entry.id), "status": entry.status.value}


@router.delete(
    "/admin/entries/{entry_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a trashed entry (admin)",
    dependencies=[_require_content_write],
)
async def admin_hard_delete_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    from app.modules.content.application import entry_revision_service

    await _require_entry_access(entry_id, current_user, db)
    await entry_revision_service.hard_delete_entry(db, entry_id)


# ── Plugin/hook registry introspection (Strapi admin parity) ────────────────


@router.get(
    "/admin/plugins",
    summary="List registered plugins and their hook bindings (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_plugins() -> dict[str, Any]:
    from app.shared.plugins.registry import registry

    return registry.describe()


@router.post(
    "/admin/plugins/{plugin_name}/toggle",
    summary="Enable or disable a plugin for this deployment (admin)",
    dependencies=[_require_content_write],
)
async def admin_toggle_plugin(
    plugin_name: str,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Switch a plugin on or off and persist the choice.

    A disabled plugin's hooks are skipped at dispatch time — it stays
    registered and visible, so re-enabling is one call, but it no longer runs.
    The core plugin point cannot be disabled.
    """
    from app.shared.plugins import registry as registry_module
    from app.shared.plugins.registry import registry

    enabled = bool(body.get("enabled", True))
    try:
        state = registry.set_enabled(plugin_name, enabled)
    except ValueError as exc:
        raise ValidationError(
            detail=str(exc), error_code="CORE_PLUGIN_NOT_TOGGLEABLE"
        ) from exc

    await registry_module.persist_disabled_plugins(db)
    await db.commit()
    return {
        "plugin": plugin_name,
        "enabled": state,
        "disabled_plugins": registry.disabled_plugins(),
    }


# ── Single Types (Strapi-style singleton configs) ───────────────────────────


@router.get(
    "/single-types",
    response_model=list[dict[str, str]],
    summary="List registered single-type configs",
)
async def list_single_types() -> list[dict[str, Any]]:
    return single_type_service.list_single_types()


@router.get(
    "/single-types/{key}",
    response_model=SingleTypeResponse,
    summary="Get a single-type config (public storefront config)",
)
async def get_single_type(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SingleTypeResponse:
    value, updated_at = await single_type_service.get_single_type(db, key)
    return SingleTypeResponse(key=key, value=value, updated_at=updated_at)


@router.put(
    "/admin/single-types/{key}",
    response_model=SingleTypeResponse,
    summary="Replace a single-type config (admin)",
    dependencies=[_require_content_write],
)
async def upsert_single_type(
    key: str,
    body: SingleTypeUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SingleTypeResponse:
    value, updated_at = await single_type_service.upsert_single_type(db, key, body.value)
    return SingleTypeResponse(key=key, value=value, updated_at=updated_at)


# ── Admin update/delete for blocks, menus, FAQs (content-manager parity) ────


@router.patch(
    "/admin/blocks/{block_id}",
    response_model=HomepageBlockResponse,
    summary="Update a homepage block (admin)",
    dependencies=[_require_content_write],
)
async def admin_update_block(
    block_id: uuid.UUID,
    body: HomepageBlockUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> HomepageBlockResponse:
    block = await content_service.update_homepage_block(
        db,
        block_id,
        title=body.title,
        config=body.config,
        position=body.position,
        is_active=body.is_active,
    )
    return HomepageBlockResponse.model_validate(block)


@router.delete(
    "/admin/blocks/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a homepage block (admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_block(
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await content_service.delete_homepage_block(db, block_id)


@router.patch(
    "/admin/menus/{item_id}",
    response_model=MenuItemResponse,
    summary="Update a menu item (admin)",
    dependencies=[_require_content_write],
)
async def admin_update_menu_item(
    item_id: uuid.UUID,
    body: MenuItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    item = await content_service.update_menu_item(
        db,
        item_id,
        title=body.title,
        url=body.url,
        position=body.position,
        icon=body.icon,
        is_active=body.is_active,
    )
    return MenuItemResponse.model_validate(item)


@router.delete(
    "/admin/menus/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a menu item (admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_menu_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await content_service.delete_menu_item(db, item_id)


@router.patch(
    "/admin/faqs/{faq_id}",
    response_model=FAQItemResponse,
    summary="Update an FAQ entry (admin)",
    dependencies=[_require_content_write],
)
async def admin_update_faq(
    faq_id: uuid.UUID,
    body: FAQItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> FAQItemResponse:
    faq = await content_service.update_faq(
        db,
        faq_id,
        question=body.question,
        answer_html=body.answer_html,
        category=body.category,
        position=body.position,
        is_active=body.is_active,
    )
    await _invalidate_faq_cache()
    return FAQItemResponse.model_validate(faq)


@router.delete(
    "/admin/faqs/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an FAQ entry (admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_faq(
    faq_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await content_service.delete_faq(db, faq_id)
    await _invalidate_faq_cache()


# ── Reusable blocks (WordPress "synced patterns") ───────────────────────────
#
# Bodies reference these by token — [block slug="promo"] — and the render
# path expands them on read, so editing a block updates every page and post
# that embeds it. See app/shared/content/render.py.


@router.get(
    "/admin/reusable-blocks",
    response_model=list[ReusableBlockResponse],
    summary="List reusable blocks (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_reusable_blocks(
    include_deleted: bool = Query(False, description="Include trashed blocks"),
    db: AsyncSession = Depends(get_db),
) -> list[ReusableBlockResponse]:
    svc = ReusableBlockService(db)
    blocks = await svc.list_blocks(include_deleted=include_deleted)
    return [ReusableBlockResponse.model_validate(b) for b in blocks]


@router.post(
    "/admin/reusable-blocks",
    response_model=ReusableBlockResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reusable block (admin)",
    dependencies=[_require_content_write],
)
async def admin_create_reusable_block(
    body: ReusableBlockCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ReusableBlockResponse:
    svc = ReusableBlockService(db)
    block = await svc.create_block(
        name=body.name,
        body_html=body.body_html,
        slug=body.slug,
        description=body.description,
        status=body.status,
        author_id=_actor_id(current_user),
    )
    await db.commit()
    return ReusableBlockResponse.model_validate(block)


@router.patch(
    "/admin/reusable-blocks/{block_id}",
    response_model=ReusableBlockResponse,
    summary="Update a reusable block (admin) — propagates to every embedding page",
    dependencies=[_require_content_write],
)
async def admin_update_reusable_block(
    block_id: uuid.UUID,
    body: ReusableBlockUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ReusableBlockResponse:
    svc = ReusableBlockService(db)
    block = await svc.update_block(
        block_id, data=body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ReusableBlockResponse.model_validate(block)


@router.delete(
    "/admin/reusable-blocks/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Move a reusable block to trash (admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_reusable_block(
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = ReusableBlockService(db)
    await svc.delete_block(block_id)
    await db.commit()


@router.post(
    "/admin/reusable-blocks/{block_id}/restore",
    response_model=ReusableBlockResponse,
    summary="Restore a reusable block from trash (admin)",
    dependencies=[_require_content_write],
)
async def admin_restore_reusable_block(
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReusableBlockResponse:
    svc = ReusableBlockService(db)
    block = await svc.restore_block(block_id)
    await db.commit()
    return ReusableBlockResponse.model_validate(block)


@router.delete(
    "/admin/reusable-blocks/{block_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a reusable block (admin)",
    dependencies=[_require_content_write],
)
async def admin_hard_delete_reusable_block(
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = ReusableBlockService(db)
    await svc.hard_delete_block(block_id)
    await db.commit()


# ── i18n: CMS page translations (Strapi i18n parity) ─────────────────────
# Pages that are translations of one another share a translation_group UUID.
# A translation is a separate page row with its own slug and locale; these
# endpoints only manage the linkage. All row access is primary-key based.


class TranslationLinkRequest(BaseModel):
    target_page_id: uuid.UUID = Field(..., description="Page to link as a translation")


@router.post(
    "/admin/pages/{page_id}/translations",
    summary="Link two CMS pages as translations of one another (admin)",
    dependencies=[_require_content_write],
)
async def admin_link_page_translation(
    page_id: uuid.UUID,
    body: TranslationLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    from app.modules.content.domain.models import CmsPage

    # A translation link is bidirectional: it merges the two pages into one
    # group, so it changes how *both* are served. Authorising only the page
    # named in the path would let a writer graft their page onto someone
    # else's and thereby take over the other's URL variants.
    await _require_page_access(page_id, current_user, db)
    await _require_page_access(body.target_page_id, current_user, db)

    source = await db.get(CmsPage, page_id)
    target = await db.get(CmsPage, body.target_page_id)
    if source is None or target is None:
        raise ValidationError("صفحه‌ی مبدأ یا مقصد یافت نشد.")
    if source.id == target.id:
        raise ValidationError("یک صفحه نمی‌تواند ترجمه‌ی خودش باشد.")

    group = source.translation_group or target.translation_group or uuid.uuid4()
    source.translation_group = group
    target.translation_group = group
    await db.commit()
    return {"translation_group": str(group)}


@router.delete(
    "/admin/pages/{page_id}/translations/{target_page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink a CMS page translation (admin)",
    dependencies=[_require_content_write],
)
async def admin_unlink_page_translation(
    page_id: uuid.UUID,
    target_page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    from app.modules.content.domain.models import CmsPage

    # Both sides again: unlinking strips the group, which changes routing for
    # the other page as much as for this one.
    await _require_page_access(page_id, current_user, db)
    await _require_page_access(target_page_id, current_user, db)

    source = await db.get(CmsPage, page_id)
    target = await db.get(CmsPage, target_page_id)
    if source is None or target is None:
        raise ValidationError("صفحه‌ی مبدأ یا مقصد یافت نشد.")
    if (
        source.translation_group is not None
        and source.translation_group == target.translation_group
    ):
        target.translation_group = None
        await db.commit()


# ── Custom fields (page meta) ───────────────────────────────────────────────
# Pages had no meta store, so a field could not be attached to a page without a
# schema change. Same access pattern as the blog post meta routes.


class PageMetaUpsert(BaseModel):
    """Body for setting one custom field on a page."""

    meta_key: str = Field(..., min_length=1, max_length=255)
    meta_value: str | None = None


@router.get(
    "/admin/pages/{page_id}/meta",
    summary="List custom fields for a page (admin)",
    dependencies=[_require_content_write],
)
async def admin_list_page_meta(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from app.modules.blog.application.meta_service import PageMetaService

    return await PageMetaService.list(db, page_id)


@router.post(
    "/admin/pages/{page_id}/meta",
    summary="Add or update a custom field on a page (admin)",
    dependencies=[_require_content_write],
)
async def admin_upsert_page_meta(
    page_id: uuid.UUID,
    body: PageMetaUpsert,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.blog.application.meta_service import PageMetaService

    await _require_page_access(page_id, current_user, db)
    return await PageMetaService.upsert(db, page_id, body.meta_key, body.meta_value)


@router.delete(
    "/admin/pages/{page_id}/meta/{meta_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom field from a page (admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_page_meta(
    page_id: uuid.UUID,
    meta_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    from app.modules.blog.application.meta_service import PageMetaService

    await _require_page_access(page_id, current_user, db)
    await PageMetaService.delete(db, page_id, meta_key)


@router.get(
    "/pages/{slug}/alternates",
    summary="Locale alternates for a page (hreflang source)",
)
async def page_alternates(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The page's own locale plus every translation in its group.

    hreflang must be self-referential or a search engine discards the whole
    set, so the current page is always included even if it has no
    translations.
    """
    from sqlalchemy import select

    from app.modules.content.domain.models import CmsPage, PageStatus

    page = (await db.execute(
        select(CmsPage).where(CmsPage.slug == slug)
    )).scalar_one_or_none()
    if page is None:
        raise NotFoundError("CmsPage", f"صفحه با اسلاگ {slug} یافت نشد.")

    alternates: list[dict[str, str]] = [
        {"locale": page.locale, "slug": page.slug, "path": f"/{page.slug}"}
    ]
    if page.translation_group is not None:
        siblings = (await db.execute(
            select(CmsPage).where(
                CmsPage.translation_group == page.translation_group,
                CmsPage.id != page.id,
                CmsPage.status == PageStatus.PUBLISHED,
                CmsPage.deleted_at.is_(None),
            )
        )).scalars().all()
        alternates += [
            {"locale": s.locale, "slug": s.slug, "path": f"/{s.slug}"} for s in siblings
        ]
    return {"self": {"locale": page.locale, "slug": page.slug}, "alternates": alternates}


class MenuReorderRequest(BaseModel):
    """A whole menu's ordering, as a drag-and-drop editor produces it."""

    items: list[dict[str, Any]] = Field(
        ..., description='Each: {"id": "...", "parent_id": null|"...", "position": int}'
    )


@router.put(
    "/admin/menus/{location}/reorder",
    summary="Reorder and re-nest a menu (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def reorder_menu(
    location: str,
    body: MenuReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Persist a drag-and-drop menu edit in one transaction.

    Reordering previously required N PATCH calls with hand-computed positions,
    and a partial failure left the menu in a mixed order. The parent_id in
    each item also re-nests, which is what a tree drag actually changes.
    """
    from app.shared.content.nav_builder import NavBuilderService

    try:
        MenuLocation(location)
    except ValueError as exc:
        raise ValidationError(
            f"مکان منوی نامعتبر: {location}",
            extra={"allowed": [loc.value for loc in MenuLocation]},
        ) from exc

    updated = await NavBuilderService.reorder(db, location, body.items)
    tree = await NavBuilderService.get_menu_tree(db, location)
    return {"updated": updated, "tree": tree}


# ── Sitemap index + per-provider files ──────────────────────────────────────
# The flat /sitemap.xml grows without bound: every request re-serialises every
# URL. An index plus one file per provider caps each response and lets a
# crawler fetch only the section it needs.


@router.get("/sitemap.xml", summary="Sitemap index (public)")
async def sitemap_index(db: AsyncSession = Depends(get_db)) -> Response:
    from app.modules.content.application.sitemap_index_service import build_index
    from app.modules.content.application.sitemap_service import _resolve_base_url

    body = await build_index(db, await _resolve_base_url(db))
    return Response(content=body, media_type="application/xml")


@router.get("/sitemap-{provider}.xml", summary="One provider's sitemap (public)")
async def sitemap_provider(
    provider: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.modules.content.application.sitemap_index_service import build_provider
    from app.modules.content.application.sitemap_service import _resolve_base_url

    body = await build_provider(db, provider, await _resolve_base_url(db))
    if body is None:
        raise NotFoundError(
            "SitemapProvider", f"بخش ناشناختهٔ sitemap: {provider}"
        )
    return Response(content=body, media_type="application/xml")


# ── oEmbed provider ─────────────────────────────────────────────────────────
# The editor already CONSUMES oEmbed; without these routes nothing served the
# other direction, so pasting one of our URLs into another CMS produced
# nothing at all. The discovery link is what a consumer's editor fetches first.


@router.get("/oembed", summary="oEmbed discovery (public)")
async def oembed_discovery(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    from app.modules.content.application.sitemap_service import _resolve_base_url

    base = (await _resolve_base_url(db)).rstrip("/")
    return {
        "version": "1.0",
        "type": "link",
        "provider_name": "فروشگاه",
        "provider_url": base,
        "endpoints": [f"{base}/api/v1/content/oembed/1.0/embed"],
    }


@router.get("/oembed/1.0/embed", summary="oEmbed provider (public)")
async def oembed_embed(
    url: str = Query(..., description="The URL to embed"),
    maxwidth: int = Query(640, ge=200, le=2000),
    maxheight: int = Query(0, ge=0, le=2000),
    db: AsyncSession = Depends(get_db),
) -> Response:
    import json as _json

    from app.modules.content.application.oembed_provider import _resolve
    from app.modules.content.application.sitemap_service import _resolve_base_url

    base = (await _resolve_base_url(db)).rstrip("/")
    payload = await _resolve(db, url, base, maxwidth=maxwidth, maxheight=maxheight)
    if payload is None:
        # oEmbed's contract for "I cannot embed this" is 404, not a payload
        # with empty fields — consumers branch on the status.
        raise NotFoundError("OEmbedResource", "این آدرس قابل جاسازی نیست")
    return Response(
        content=_json.dumps(payload, ensure_ascii=False),
        media_type="application/json",
    )
