"""Content API routes: Homepage Blocks, Tree Menus, FAQs, and CMS pages (Karta Phase 7/9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import distinct, select
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


def _client_ip(request: Request) -> str | None:
    """Client IP for the audit row, respecting the trusted-proxy convention.

    Same extraction as the auth routes: rightmost trusted hop of
    X-Forwarded-For, then the socket peer. Kept local rather than imported
    from rate_limiter to avoid a circular import at module load.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _client_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


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
#
# Declaration order matters: `/menus/locations` is literal and must come
# before `/menus/{location}`, or the parameterized route swallows it and the
# literal is parsed as a location named "locations".


@router.get(
    "/menus/locations",
    summary="List every menu location: the built-ins plus any in use (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_menu_locations(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The built-in locations and any operator-created ones already in use.

    WordPress registers menu locations from the theme, so the admin picks from
    a fixed list. This store lets an operator add a location from the panel —
    a campaign bar, a landing-page nav — so the list has to include what is
    actually in the table, not only the seed values, or a location an operator
    created would vanish from the picker that created it.
    """
    from app.modules.content.domain.models import SiteMenu

    builtin = [loc.value for loc in MenuLocation]
    rows = (
        await db.execute(select(distinct(SiteMenu.location)))
    ).scalars().all()
    in_use = sorted({r for r in rows if r})
    return {
        "builtin": builtin,
        "custom": [loc for loc in in_use if loc not in builtin],
        "all": sorted(set(builtin) | set(in_use)),
    }


@router.get(
    "/menus/{location}",
    response_model=list[TreeMenuItemNode],
    summary="Get hierarchical navigation tree for a location (header, footer, mobile)",
)
async def get_tree_menu(
    location: str,
    db: AsyncSession = Depends(get_db),
) -> list[TreeMenuItemNode]:
    """The tree for one location. `str`, not the enum, so an operator-defined
    location is readable — the enum covered only the five seeded values, which
    made a custom location a 422 on read even after it was written."""
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
    # The location becomes a CSS selector and a layout slot name, so it is
    # validated as a slug — a location with a space or a slash would be a
    # value no layout could ever render.
    from app.modules.content.schemas.content import validate_menu_location

    try:
        location = validate_menu_location(body.location)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    item = await content_service.create_menu_item(
        db,
        location=location,
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
    db: AsyncSession = Depends(get_db),
) -> PublicPageSummaryList:
    """Every published page's slug, for sitemap and navigation discovery.

    Unauthenticated by design — the sitemap generator has no session. It is
    therefore deliberately narrower than the admin list: no ``body_html``, no
    SEO overrides, no author, and trashed or draft pages are excluded. Keep it
    that way; widening the projection here would publish unpublished content.
    """
    pages = await cms_page_service.list_published_page_summaries(db)
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
    "/sitemap-noindex",
    summary="Slugs the operator marked noindex (storefront sitemap exclusion)",
)
async def get_sitemap_noindex(db: AsyncSession = Depends(get_db)) -> dict[str, list[str]]:
    """Slugs excluded from the sitemap by an explicit robots_noindex choice.

    The main sitemap builds blog URLs from the paginated blog API, which does
    not carry SEO metadata — so the storefront fetches this small list and
    filters. Unauthenticated like the other sitemap sources: a crawler-facing
    exclusion list is not sensitive, and it must be readable by the same
    session-less generator.
    """
    from app.modules.content.application import sitemap_service

    return await sitemap_service.collect_noindex_slugs(db)


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
    """Expand reusable blocks and shortcodes in a page body for display."""
    from app.shared.content.render import render_body

    body = await render_body(db, page.body_html)

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
    "/admin/pages/slug-check",
    summary="Is this page slug free? (admin)",
    dependencies=[_require_content_write],
)
async def admin_check_page_slug(
    slug: str = Query(..., min_length=1, max_length=220, description="Candidate slug"),
    page_id: uuid.UUID | None = Query(
        None, description="Page being edited; its own slug does not count as taken"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Live slug availability for the editor.

    Gated on the same permission as writing pages: it reports which slugs exist,
    which is the shape of a small existence oracle, and an unauthenticated
    caller could use it to enumerate the store's URL structure.
    """
    from app.modules.content.application.cms_page_service import check_slug_available

    return await check_slug_available(db, slug, exclude_id=page_id)


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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    author_id: uuid.UUID | None = None
    try:
        author_id = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = None
    return await cms_page_service.create_page(
        db, body, author_id=author_id,
        ip_address=_client_ip(request), user_agent=_client_ua(request),
    )


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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    await _require_page_access(page_id, current_user, db)
    editor_id: uuid.UUID | None = _actor_id(current_user)
    return await cms_page_service.update_page(
        db, page_id, body, editor_id=editor_id,
        ip_address=_client_ip(request), user_agent=_client_ua(request),
    )


@router.delete(
    "/admin/pages/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Trash a CMS page (soft delete, admin)",
    dependencies=[_require_content_write],
)
async def admin_delete_page(
    page_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    await _require_page_access(page_id, current_user, db)
    await cms_page_service.delete_page(
        db, page_id, actor_id=_actor_id(current_user),
        ip_address=_client_ip(request), user_agent=_client_ua(request),
    )


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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CmsPageResponse:
    await _require_page_access(page_id, current_user, db)
    return await cms_page_service.restore_page(
        db, page_id, actor_id=_actor_id(current_user),
        ip_address=_client_ip(request), user_agent=_client_ua(request),
    )


@router.delete(
    "/admin/pages/{page_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a trashed CMS page (admin)",
    dependencies=[_require_content_write],
)
async def admin_hard_delete_page(
    page_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    # Irreversible: there is no trash to restore from, so this is the route
    # where an over-broad guard does the most damage if it is missing.
    await _require_page_access(page_id, current_user, db)
    await cms_page_service.hard_delete_page(
        db, page_id, actor_id=_actor_id(current_user),
        ip_address=_client_ip(request), user_agent=_client_ua(request),
    )


class EmptyPageTrashRequest(BaseModel):
    """How far back the trash reaches.

    Omitted means "everything currently in the trash". A scheduled job should
    always send a number: purging everything nightly would make "empty
    trash" a lie the moment an editor restored something they had not meant
    to remove yet.
    """

    older_than_days: int | None = Field(
        None,
        ge=1,
        le=3650,
        description="Only purge pages trashed more than this many days ago",
    )


@router.post(
    "/admin/pages/empty-trash",
    summary="Permanently delete trashed CMS pages (admin)",
    dependencies=[_require_content_write],
)
async def admin_empty_page_trash(
    body: EmptyPageTrashRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Purge the page trash.

    Separate from the bulk route on purpose: "empty trash" is about a *state*
    rather than a selection, so it takes no ids and reports what it removed
    by id.
    """
    return await cms_page_service.empty_page_trash(
        db,
        older_than_days=body.older_than_days,
        actor_id=_actor_id(current_user),
        ip_address=_client_ip(request),
        user_agent=_client_ua(request),
    )


@router.post(
    "/admin/pages/bulk/{action}",
    response_model=BulkActionResult,
    summary="Bulk publish/unpublish/trash/restore CMS pages (admin)",
    dependencies=[_require_content_write],
)
async def admin_bulk_pages(
    action: str,
    body: BulkActionRequest,
    request: Request,
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
        db, body.ids, action, actor_id=actor_id, actor_payload=current_user,
        ip_address=_client_ip(request), user_agent=_client_ua(request),
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
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.content.application import embed_service

    # `db` so the operator's cache window and host allowlist are honoured;
    # without it the module defaults apply, which is what the options were
    # added to override.
    return await embed_service.resolve_embed(url, db=db)


# ── Content import/export routes removed 2026-10-07 ─────────────────────────
#
# `GET/POST /admin/content/export|import` served the «انتقال محتوا» admin page
# (JSON dump of CMS pages + FAQs). The owner removed that page: the
# «ورود و خروج داده» screen (dataexchange module) covers the same two entities
# plus five more, with CSV/XLSX and the WordPress WXR import, and the JSON
# file format was explicitly not wanted. `transfer_service.import_content`
# stays — the WXR import path (`blog.application.wxr_import`) still calls it
# for pages. Archive: `_archived/content-transfer-removal-2026-10-07/`.


# Dynamic content-type builder (Strapi parity: `/admin/content-types`,
# `/content-types`, `/admin/entries`) was removed on 2026-10-09 per owner
# decision: the store is an e-commerce platform, not a news portal; standard
# blog posts, categories, tags, and fixed CMS pages suffice.
# Archive: `_archived/content-types-removal-2026-10-09/`.


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
    from app.modules.content.schemas.content import validate_menu_location
    from app.shared.content.nav_builder import NavBuilderService

    # A slug check, not the enum: an operator-defined location is valid, and
    # the enum only covers the five seeded ones — which would make a custom
    # location impossible to reorder.
    try:
        location = validate_menu_location(location)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    updated = await NavBuilderService.reorder(db, location, body.items)
    tree = await NavBuilderService.get_menu_tree(db, location)
    return {"updated": updated, "tree": tree}


# ── Sitemap: one canonical surface ──────────────────────────────────────────
# P1 "فید: دو مسیر موازی سایت‌مپ". Two sitemaps shipped: this backend index (and
# its per-provider files) and the Next.js app/sitemap.ts. Crawlers were told
# about exactly one of them — robots.txt advertises /sitemap.xml, which the
# storefront serves — so the backend index was a second, unreachable copy that
# could still drift from the canonical one.
#
# The storefront sitemap won because it is what robots.txt names and what
# /content/sitemap-entries feeds. This route is kept only as a redirect so a
# stale link to the API sitemap follows through instead of 404ing; the
# per-provider files it used to list are gone with it.


@router.get("/sitemap.xml", summary="Redirect to the canonical sitemap (public)")
async def sitemap_index(db: AsyncSession = Depends(get_db)) -> Response:
    from fastapi.responses import RedirectResponse

    from app.modules.settings.application.site_options_service import public_base_url

    # public_base_url (not sitemap_service._resolve_base_url) because that one
    # falls back to the placeholder https://example.com — redirecting a crawler
    # to example.com is worse than the 404 this replaces. public_base_url falls
    # back to the deployment's own STOREFRONT_BASE_URL.
    base = (await public_base_url(db)).rstrip("/")
    if not base:
        # No origin resolvable at all: 404 rather than a placeholder redirect.
        raise NotFoundError("Sitemap", "سایت‌مپ در این مسیر سرو نمی‌شود")
    # 301: the canonical location is permanent, so a crawler moves on rather
    # than re-checking this path forever.
    return RedirectResponse(url=f"{base}/sitemap.xml", status_code=301)


# ── oEmbed provider ─────────────────────────────────────────────────────────
# The editor already CONSUMES oEmbed; without these routes nothing served the
# other direction, so pasting one of our URLs into another CMS produced
# nothing at all. The discovery link is what a consumer's editor fetches first.


@router.get("/oembed", summary="oEmbed discovery (public)")
async def oembed_discovery(
    url: str | None = Query(
        None,
        description="Absolute URL of the page being embedded. Supplied by the "
                    "per-page discovery link.",
    ),
    format: str | None = Query(
        None, description="`json` is the only format oEmbed discovery defines"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The discovery document a consumer reads to embed a page.

    ``url`` and ``format`` are the parameters the oEmbed spec sends and every
    consumer includes. They are accepted and reflected rather than ignored, so
    a client following the per-page `<link>` gets a document naming the page it
    asked about — the root layout's bare `/oembed` link had no way to say
    which page, and a post shared into a chat client had nothing to attach.
    """
    from app.modules.content.application.sitemap_service import _resolve_base_url

    base = (await _resolve_base_url(db)).rstrip("/")
    return {
        "version": "1.0",
        "type": "link",
        "provider_name": "فروشگاه",
        "provider_url": base,
        "endpoints": [f"{base}/api/v1/content/oembed/1.0/embed"],
        # Echoed so a consumer can tell which page it fetched the document
        # for, and so an unsupported format has somewhere to be reported rather
        # than being silently accepted.
        "url": url,
        "format": format or "json",
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
