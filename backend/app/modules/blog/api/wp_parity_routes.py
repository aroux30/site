"""WordPress-parity API routes for the Blog module.

Mounted onto the blog module's admin/public routers so the frontend can
reach custom taxonomies, custom post types, the editorial workflow, the
editorial calendar, quick edit, import/export, breadcrumbs, post
relationships and the capability matrix.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions, get_current_user

_require_blog_write = Depends(RequirePermissions("blog:write"))

# Import the routers this module extends. Both are module-level singletons,
# so registering routes on them here is enough — no re-export needed.
from app.modules.blog.api.routes import admin_router, router  # noqa: E402

# Reused rather than re-implemented so the parity routes and the main blog
# router cannot drift: one definition of "may this caller touch this post",
# applied at the same two levels (route guard + method body).
from app.modules.blog.api.routes import _require_post_access  # noqa: E402


async def _require_entry_access(
    entry_id: uuid.UUID,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Gate a custom-post-entry mutation on ownership of that entry.

    Same reasoning as ``routes._require_post_access``: ``_require_blog_write``
    proves the caller may write blog content, not whose content they may
    touch. A custom post entry carries the same nullable ``author_id`` a post
    does, so the identical rule applies.
    """
    from app.core.security.object_capabilities import (
        OBJECT_RULES,
        require_object_capability,
    )
    from app.modules.blog.domain.custom_post_types import CustomPostEntry

    entry = await db.get(CustomPostEntry, entry_id)
    if entry is None:
        raise NotFoundError("CustomPostEntry", f"ورودی {entry_id} یافت نشد")

    await require_object_capability(current_user, entry, OBJECT_RULES["custom_posts"])

# ============================================================================
# Custom taxonomies
# ============================================================================


@admin_router.get("/taxonomies", summary="List custom taxonomies (Admin)")
async def admin_list_taxonomies(
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, Any]]:
    from sqlalchemy import func, select

    from app.modules.blog.domain.taxonomy_models import CustomTaxonomy, CustomTaxonomyTerm

    # Count terms per taxonomy in one grouped query rather than N per row.
    counts = dict(
        (await db.execute(
            select(CustomTaxonomyTerm.taxonomy_id, func.count(CustomTaxonomyTerm.id))
            .group_by(CustomTaxonomyTerm.taxonomy_id)
        )).all()
    )
    rows = (await db.execute(select(CustomTaxonomy).order_by(CustomTaxonomy.name))).scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "description": t.description,
            "hierarchical": t.hierarchical,
            "is_active": t.is_active,
            "term_count": counts.get(t.id, 0),
        }
        for t in rows
    ]


@admin_router.post(
    "/taxonomies",
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom taxonomy (Admin)",
)
async def admin_create_taxonomy(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.domain.taxonomy_models import CustomTaxonomy
    from app.shared.domain.slug import generate_slug

    tax = CustomTaxonomy(
        name=body["name"],
        slug=body.get("slug") or generate_slug(body["name"]),
        description=body.get("description"),
        hierarchical=bool(body.get("hierarchical", False)),
    )
    db.add(tax)
    await db.commit()
    await db.refresh(tax)
    return {"id": str(tax.id), "name": tax.name, "slug": tax.slug}


@admin_router.get("/taxonomies/{taxonomy_id}/terms", summary="List taxonomy terms (Admin)")
async def admin_list_taxonomy_terms(
    taxonomy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, Any]]:
    from sqlalchemy import func, select

    from app.modules.blog.domain.taxonomy_models import BlogPostTerm, CustomTaxonomyTerm

    stmt = (
        select(CustomTaxonomyTerm)
        .where(CustomTaxonomyTerm.taxonomy_id == taxonomy_id)
        .order_by(CustomTaxonomyTerm.position)
    )
    rows = (await db.execute(stmt)).scalars().all()
    # How many posts use each term, so the admin can see before detaching.
    usage = dict(
        (await db.execute(
            select(BlogPostTerm.term_id, func.count(BlogPostTerm.post_id))
            .where(BlogPostTerm.term_id.in_([t.id for t in rows]))
            .group_by(BlogPostTerm.term_id)
        )).all()
    ) if rows else {}
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "description": t.description,
            "position": t.position,
            "parent_id": str(t.parent_id) if t.parent_id else None,
            "post_count": usage.get(t.id, 0),
        }
        for t in rows
    ]


@admin_router.post(
    "/taxonomies/{taxonomy_id}/terms",
    status_code=status.HTTP_201_CREATED,
    summary="Create a taxonomy term (Admin)",
)
async def admin_create_taxonomy_term(
    taxonomy_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.domain.taxonomy_models import CustomTaxonomyTerm
    from app.shared.domain.slug import generate_slug

    term = CustomTaxonomyTerm(
        taxonomy_id=taxonomy_id,
        name=body["name"],
        slug=body.get("slug") or generate_slug(body["name"]),
        description=body.get("description"),
        parent_id=uuid.UUID(body["parent_id"]) if body.get("parent_id") else None,
        position=int(body.get("position", 0)),
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return {"id": str(term.id), "name": term.name, "slug": term.slug}


@admin_router.post("/posts/{post_id}/terms", summary="Attach taxonomy terms to a post (Admin)")
async def admin_attach_post_terms(
    post_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, int]:
    from sqlalchemy import delete

    from app.modules.blog.domain.taxonomy_models import BlogPostTerm

    # This route *replaces* the post's whole term set: the delete below runs
    # before the insert, so an unguarded call could strip a colleague's
    # categories and tags entirely. Destructive, therefore owner-gated.
    await _require_post_access(post_id, current_user, db)

    await db.execute(delete(BlogPostTerm).where(BlogPostTerm.post_id == post_id))
    term_ids = body.get("term_ids", [])
    for term_id in dict.fromkeys(term_ids):
        db.add(BlogPostTerm(post_id=post_id, term_id=uuid.UUID(term_id)))
    await db.commit()
    return {"attached": len(term_ids)}


@admin_router.patch(
    "/taxonomies/{taxonomy_id}", summary="Update a custom taxonomy (Admin)"
)
async def admin_update_taxonomy(
    taxonomy_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.taxonomy_service import TaxonomyService

    return await TaxonomyService.update_taxonomy(db, taxonomy_id, body)


@admin_router.delete(
    "/taxonomies/{taxonomy_id}", summary="Delete a custom taxonomy and its terms (Admin)"
)
async def admin_delete_taxonomy(
    taxonomy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, int]:
    from app.modules.blog.application.taxonomy_service import TaxonomyService

    return await TaxonomyService.delete_taxonomy(db, taxonomy_id)


@admin_router.patch(
    "/taxonomies/{taxonomy_id}/terms/{term_id}",
    summary="Update a taxonomy term (Admin)",
)
async def admin_update_taxonomy_term(
    taxonomy_id: uuid.UUID,
    term_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.taxonomy_service import TaxonomyService

    return await TaxonomyService.update_term(db, term_id, body)


@admin_router.delete(
    "/taxonomies/{taxonomy_id}/terms/{term_id}", summary="Delete a taxonomy term (Admin)"
)
async def admin_delete_taxonomy_term(
    taxonomy_id: uuid.UUID,
    term_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, int]:
    from app.modules.blog.application.taxonomy_service import TaxonomyService

    return await TaxonomyService.delete_term(db, term_id)


# ============================================================================
# Custom post types
# ============================================================================


@admin_router.get("/content-types", summary="List custom post types (Admin)")
async def admin_list_content_types(
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.modules.blog.domain.custom_post_types import CustomPostType

    rows = (await db.execute(select(CustomPostType).order_by(CustomPostType.name))).scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "description": t.description,
            "icon": t.icon,
            "field_schema": t.field_schema,
            "supports_categories": t.supports_categories,
            "supports_comments": t.supports_comments,
            "is_active": t.is_active,
        }
        for t in rows
    ]


@admin_router.post(
    "/content-types",
    status_code=status.HTTP_201_CREATED,
    summary="Register a custom post type (Admin)",
)
async def admin_create_content_type(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.domain.custom_post_types import CustomPostType
    from app.shared.domain.slug import generate_slug

    cpt = CustomPostType(
        name=body["name"],
        slug=body.get("slug") or generate_slug(body["name"]),
        description=body.get("description"),
        icon=body.get("icon"),
        field_schema=body.get("field_schema"),
        supports_categories=bool(body.get("supports_categories", False)),
        supports_comments=bool(body.get("supports_comments", False)),
    )
    db.add(cpt)
    await db.commit()
    await db.refresh(cpt)
    return {"id": str(cpt.id), "name": cpt.name, "slug": cpt.slug}


@admin_router.get("/content-types/{type_id}/entries", summary="List custom post entries (Admin)")
async def admin_list_content_entries(
    type_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.modules.blog.domain.custom_post_types import CustomPostEntry

    stmt = (
        select(CustomPostEntry)
        .where(CustomPostEntry.post_type_id == type_id)
        .order_by(CustomPostEntry.position, CustomPostEntry.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "slug": e.slug,
            # `.value`, not str(): Python 3.11 str() on a str-Enum returns
            # "CustomPostTypeStatus.PUBLISHED", which no client ever compares
            # against. The enum-storage contract is the member NAME.
            "status": e.status.value,
            "fields": e.fields,
            "excerpt": e.excerpt,
        }
        for e in rows
    ]


@admin_router.post(
    "/content-types/{type_id}/entries",
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom post entry (Admin)",
)
async def admin_create_content_entry(
    type_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.domain.custom_post_types import CustomPostEntry
    from app.shared.domain.slug import generate_slug

    try:
        author_id = uuid.UUID(str(current_user.get("sub", "")))
    except (TypeError, ValueError):
        author_id = None

    entry = CustomPostEntry(
        post_type_id=type_id,
        title=body["title"],
        slug=body.get("slug") or generate_slug(body["title"]),
        fields=body.get("fields"),
        excerpt=body.get("excerpt"),
        cover_image_url=body.get("cover_image_url"),
        position=int(body.get("position", 0)),
        # Stamped at creation, like a blog post: the per-object check resolves
        # "is this mine" from author_id, so an entry left null here would be
        # orphaned the moment it is created and its own author could not edit
        # it back.
        author_id=author_id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"id": str(entry.id), "title": entry.title, "slug": entry.slug}


@admin_router.patch(
    "/content-types/{type_id}", summary="Update a custom post type (Admin)"
)
async def admin_update_content_type(
    type_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.taxonomy_service import ContentTypeService

    return await ContentTypeService.update_content_type(db, type_id, body)


@admin_router.delete(
    "/content-types/{type_id}",
    summary="Delete a custom post type and its entries (Admin)",
)
async def admin_delete_content_type(
    type_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, int]:
    from app.modules.blog.application.taxonomy_service import ContentTypeService

    return await ContentTypeService.delete_content_type(db, type_id)


@admin_router.patch(
    "/content-types/{type_id}/entries/{entry_id}",
    summary="Update a custom post entry (Admin)",
)
async def admin_update_content_entry(
    type_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.taxonomy_service import ContentTypeService

    await _require_entry_access(entry_id, current_user, db)
    return await ContentTypeService.update_entry(db, entry_id, body)


@admin_router.delete(
    "/content-types/{type_id}/entries/{entry_id}",
    summary="Delete a custom post entry (Admin)",
)
async def admin_delete_content_entry(
    type_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, int]:
    from app.modules.blog.application.taxonomy_service import ContentTypeService

    await _require_entry_access(entry_id, current_user, db)
    return await ContentTypeService.delete_entry(db, entry_id)


# ── Public reads ────────────────────────────────────────────────────────────
# A custom post type or taxonomy that can only be seen in the admin is write-
# only content: an entry gets created and can never be rendered anywhere. These
# two routes close that loop, and both serve only published/active rows.


@router.get(
    "/content-types/{type_slug}/entries",
    summary="List published entries of a public custom post type",
)
async def public_list_content_entries(
    type_slug: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.modules.blog.domain.custom_post_types import (
        CustomPostEntry,
        CustomPostType,
        CustomPostTypeStatus,
    )

    stmt = (
        select(CustomPostEntry)
        .join(CustomPostType, CustomPostEntry.post_type_id == CustomPostType.id)
        .where(
            CustomPostType.slug == type_slug,
            CustomPostType.is_active.is_(True),
            CustomPostEntry.status == CustomPostTypeStatus.PUBLISHED,
        )
        .order_by(CustomPostEntry.position, CustomPostEntry.published_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(e.id), "title": e.title, "slug": e.slug,
            "excerpt": e.excerpt, "cover_image_url": e.cover_image_url,
            "fields": e.fields, "published_at": e.published_at.isoformat()
            if e.published_at else None,
        }
        for e in rows
    ]


@router.get(
    "/taxonomies/{taxonomy_slug}/terms",
    summary="List terms of a public active custom taxonomy",
)
async def public_list_taxonomy_terms(
    taxonomy_slug: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.modules.blog.domain.taxonomy_models import (
        CustomTaxonomy,
        CustomTaxonomyTerm,
    )

    stmt = (
        select(CustomTaxonomyTerm)
        .join(CustomTaxonomy, CustomTaxonomyTerm.taxonomy_id == CustomTaxonomy.id)
        .where(
            CustomTaxonomy.slug == taxonomy_slug,
            CustomTaxonomy.is_active.is_(True),
        )
        .order_by(CustomTaxonomyTerm.position, CustomTaxonomyTerm.name)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(t.id), "name": t.name, "slug": t.slug,
            "description": t.description,
            "parent_id": str(t.parent_id) if t.parent_id else None,
        }
        for t in rows
    ]


# ============================================================================
# Editorial workflow, calendar, quick edit
# ============================================================================


@admin_router.post("/posts/{post_id}/submit-for-review", summary="Submit a draft for review (Admin)")
async def admin_submit_for_review(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, str]:
    from app.modules.blog.application.editorial_workflow_service import EditorialWorkflowService

    return await EditorialWorkflowService(db, actor_payload=current_user).submit_for_review(post_id)


@admin_router.post("/posts/{post_id}/approve", summary="Approve and publish a submitted post (Admin)")
async def admin_approve_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, str]:
    from app.modules.blog.application.editorial_workflow_service import EditorialWorkflowService

    # The payload is handed to the service, not checked here: the guard belongs
    # in the method body so every caller of `approve_post` is covered, including
    # any future route. Without it a contributor could approve their own draft.
    return await EditorialWorkflowService(db, actor_payload=current_user).approve_post(post_id)


@admin_router.post("/posts/{post_id}/reject", summary="Reject a submitted post to draft (Admin)")
async def admin_reject_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
    body: dict[str, Any] | None = None,
) -> dict[str, str]:
    from app.modules.blog.application.editorial_workflow_service import EditorialWorkflowService

    return await EditorialWorkflowService(db).reject_post(post_id, reason=(body or {}).get("reason", ""))


@admin_router.get("/pending-review", summary="List posts awaiting editorial approval (Admin)")
async def admin_pending_review(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict]:
    from app.modules.blog.application.editorial_workflow_service import EditorialWorkflowService

    return await EditorialWorkflowService(db).get_pending_posts(page=page, page_size=page_size)


@admin_router.get("/editorial-calendar", summary="Editorial calendar for a month (Admin)")
async def admin_editorial_calendar(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.editorial_calendar_service import EditorialCalendarService

    return await EditorialCalendarService.get_month(db, year=year, month=month)


@admin_router.patch("/posts/{post_id}/quick-edit", summary="Quick edit post fields inline (Admin)")
async def admin_quick_edit(
    post_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.quick_edit_service import QuickEditService

    # Quick edit is a full update wearing a smaller form: it wrote title, slug,
    # status and excerpt inline, so it needed the same owner check the regular
    # PATCH has always had. It is a separate route, so the check has to be
    # repeated here — sharing the handler was not an option the parity router
    # had.
    await _require_post_access(post_id, current_user, db)
    return await QuickEditService.quick_edit_post(db, post_id, body)


# ============================================================================
# Import / export
# ============================================================================


@admin_router.get("/export", summary="Export all blog content as JSON (Admin)")
async def admin_export_blog(
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.blog.application.transfer_service import BlogTransferService

    return await BlogTransferService.export_all(db)


@admin_router.post("/import", summary="Import blog content from a JSON export (Admin)")
async def admin_import_blog(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, int]:
    from app.modules.blog.application.transfer_service import BlogTransferService

    try:
        author_id = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    return await BlogTransferService.import_json(
        db, body, author_id=author_id, skip_existing=bool(body.get("skip_existing", True))
    )


# ============================================================================
# Post relationships
# ============================================================================


@admin_router.get("/posts/{post_id}/relationships", summary="List post relationships (Admin)")
async def admin_list_relationships(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, str]]:
    from sqlalchemy import or_, select

    from app.modules.blog.domain.relationship_models import BlogPostRelationship

    stmt = select(BlogPostRelationship).where(
        or_(
            BlogPostRelationship.source_post_id == post_id,
            BlogPostRelationship.target_post_id == post_id,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "source_post_id": str(r.source_post_id),
            "target_post_id": str(r.target_post_id),
            "relationship_type": r.relationship_type,
        }
        for r in rows
    ]


@admin_router.post(
    "/posts/{post_id}/relationships",
    status_code=status.HTTP_201_CREATED,
    summary="Link two posts (Admin)",
)
async def admin_create_relationship(
    post_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, str]:
    from app.modules.blog.domain.relationship_models import BlogPostRelationship

    await _require_post_access(post_id, current_user, db)

    rel = BlogPostRelationship(
        source_post_id=post_id,
        target_post_id=uuid.UUID(body["target_post_id"]),
        relationship_type=body.get("relationship_type", "related"),
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return {"id": str(rel.id), "type": rel.relationship_type}


@admin_router.delete(
    "/posts/{post_id}/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink two posts (Admin) — e.g. remove a translation link",
)
async def admin_delete_relationship(
    post_id: uuid.UUID,
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> None:
    from app.modules.blog.domain.relationship_models import BlogPostRelationship

    rel = await db.get(BlogPostRelationship, relationship_id)
    if rel is None or post_id not in (rel.source_post_id, rel.target_post_id):
        raise NotFoundError("BlogPostRelationship", "رابطه‌ی موردنظر یافت نشد")
    # Both endpoints are checked: a relationship is shared, so authorising only
    # the post named in the path would let the author of the *target* unlink
    # their partner's content. Either side being yours is what makes the link
    # yours to remove.
    await _require_post_access(rel.source_post_id, current_user, db)
    await _require_post_access(rel.target_post_id, current_user, db)
    await db.delete(rel)
    await db.commit()


# ============================================================================
# Breadcrumbs (public) and capabilities (admin)
# ============================================================================


@router.get("/posts/{slug}/breadcrumbs", summary="Breadcrumbs for a blog post")
async def get_post_breadcrumbs(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.modules.blog.domain.models import BlogPost
    from app.shared.content.breadcrumbs import BreadcrumbService

    stmt = select(BlogPost).options(selectinload(BlogPost.category)).where(BlogPost.slug == slug)
    post = (await db.execute(stmt)).scalar_one_or_none()
    if not post:
        raise NotFoundError("BlogPost", f"Post '{slug}' not found")
    crumbs = await BreadcrumbService.for_blog_post(
        db,
        title=post.title,
        slug=post.slug,
        category_name=post.category.name if post.category else None,
        category_slug=post.category.slug if post.category else None,
    )
    return {
        "items": [{"label": c.label, "url": c.url, "is_current": c.is_current} for c in crumbs],
        "json_ld": BreadcrumbService.to_json_ld(crumbs),
    }


@admin_router.get("/capabilities", summary="List content capabilities by role (Admin)")
async def admin_list_capabilities(
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    from app.modules.rbac.application.capability_service import UserCapabilityService

    # Read the roles table rather than the built-in defaults: a role created
    # through /admin/roles must appear here with the capabilities its
    # assigned permissions actually imply.
    return {
        "roles": await UserCapabilityService.describe_roles(db),
        "all": UserCapabilityService.list_all_capabilities(),
    }
