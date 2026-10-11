"""WordPress-parity API routes for the Blog module.

Mounted onto the blog module's admin/public routers so the frontend can
reach custom taxonomies, custom post types, the editorial workflow, the
editorial calendar, quick edit, import/export, breadcrumbs, post
relationships and the capability matrix.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, File, HTTPException, Query, UploadFile, status
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
            # Which content types this taxonomy applies to. The picker filters on
            # it, so it has to be on the list: a taxonomy list that omits it
            # makes the picker either offer a taxonomy that cannot be attached,
            # or hide one that can.
            "object_types": list(t.object_types or []),
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
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, Any]]:
    from sqlalchemy import func, or_, select

    from app.modules.blog.domain.taxonomy_models import BlogPostTerm, CustomTaxonomyTerm

    stmt = select(CustomTaxonomyTerm).where(
        CustomTaxonomyTerm.taxonomy_id == taxonomy_id
    )
    # Search is a server-side filter, not a client-side narrowing of the page
    # already fetched: with more terms than fit on one screen, filtering the
    # received slice reports "no match" for a term that exists. Matching both
    # name and description because an operator searching for a colour knows the
    # name but often only half-remembers the description.
    needle = (search or "").strip()
    if needle:
        like = f"%{needle}%"
        stmt = stmt.where(
            or_(
                CustomTaxonomyTerm.name.ilike(like),
                CustomTaxonomyTerm.slug.ilike(like),
                CustomTaxonomyTerm.description.ilike(like),
            )
        )
    # Sort in Python by position after the fact would be simpler, but the
    # position column is the operator's ordering and the tree walk depends on a
    # stable order within each level.
    stmt = stmt.order_by(CustomTaxonomyTerm.position, CustomTaxonomyTerm.name)
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


@admin_router.get("/pages/{page_id}/terms", summary="List a page's custom terms (Admin)")
async def admin_list_page_terms(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = _require_blog_write,
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.modules.blog.domain.taxonomy_models import CmsPageTerm

    rows = (
        await db.execute(
            select(CmsPageTerm).where(CmsPageTerm.page_id == page_id)
        )
    ).scalars().all()
    return [{"term_id": str(r.term_id)} for r in rows]


@admin_router.post("/pages/{page_id}/terms", summary="Attach custom terms to a page (Admin)")
async def admin_attach_page_terms(
    page_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    """Replace a page's whole custom-term set, the same contract as posts.

    Two checks the post-side route does not need, because pages are the case
    this table was added for:

    * the page has to exist — the post route's guard covers ownership, and
      there is no ownership question for a page, but a missing page would
      otherwise accept terms and store links to nothing;
    * every term's taxonomy must actually include ``cms_page`` in its
      ``object_types``. Without that, a "posts only" taxonomy could be attached
      to a page by id alone, and the term would then be invisible to every page
      that reads it — stored, and unreadable.
    """
    from sqlalchemy import delete, select

    from app.core.exceptions.handlers import NotFoundError, ValidationError
    from app.modules.content.domain.models import CmsPage
    from app.modules.blog.domain.taxonomy_models import (
        BlogPostTerm, CmsPageTerm, CustomTaxonomy, CustomTaxonomyTerm,
    )

    page = await db.get(CmsPage, page_id)
    if page is None:
        raise NotFoundError("CmsPage", f"صفحه {page_id} یافت نشد")

    raw_ids = body.get("term_ids") or []
    if not isinstance(raw_ids, list):
        raise ValidationError(detail="term_ids باید فهرست باشد")
    term_ids = list(dict.fromkeys(str(t) for t in raw_ids if str(t).strip()))

    if term_ids:
        uuids = []
        for t in term_ids:
            try:
                uuids.append(uuid.UUID(t))
            except ValueError as exc:
                raise ValidationError(detail=f"شناسه ترم نامعتبر: {t}") from exc
        found = (
            await db.execute(
                select(CustomTaxonomyTerm.id).where(CustomTaxonomyTerm.id.in_(uuids))
            )
        ).scalars().all()
        missing = sorted(set(uuids) - set(found))
        if missing:
            raise ValidationError(detail=f"ترم یافت نشد: {[str(m) for m in missing]}")

        # Every term's taxonomy must apply to pages.
        rows = (
            await db.execute(
                select(CustomTaxonomyTerm.id, CustomTaxonomy.object_types)
                .join(CustomTaxonomy, CustomTaxonomy.id == CustomTaxonomyTerm.taxonomy_id)
                .where(CustomTaxonomyTerm.id.in_(uuids))
            )
        ).all()
        wrong = sorted(
            str(tid) for tid, types in rows if "cms_page" not in (types or [])
        )
        if wrong:
            raise ValidationError(
                detail=f"تاکسونومی این ترم‌ها برای برگه فعال نیست: {wrong}"
            )

    await db.execute(delete(CmsPageTerm).where(CmsPageTerm.page_id == page_id))
    for term_id in uuids if term_ids else []:
        db.add(CmsPageTerm(page_id=page_id, term_id=term_id))
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
# Custom post types removed 2026-10-09
#
# Custom post types (WP-parity: `/admin/blog/content-types*` and
# `/content-types/{type_slug}/entries`) were removed on 2026-10-09 per owner
# decision: the store is an e-commerce platform; standard blog posts, categories,
# tags, and custom taxonomies suffice.
# Archive: `_archived/content-types-removal-2026-10-09/`.
# ============================================================================


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


@router.get(
    "/taxonomies/{taxonomy_slug}/terms/{term_slug}/posts",
    summary="Published posts in one term of a public custom taxonomy",
)
async def public_list_taxonomy_term_posts(
    taxonomy_slug: str,
    term_slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The posts carrying one custom term.

    Without this the archive can list terms but not what is in them, and the
    only way to fill a term page is to render the blog's most recent posts under
    a heading that has nothing to do with them — a page that looks right and
    is not. Filtering server-side also keeps a term's archive from breaking as
    the blog grows: paging the whole blog and filtering in the page is correct
    only until there are more posts than fit in the first few hundred.

    Published only, and only inside an active taxonomy — the same two gates the
    term list applies, because a term of a retired taxonomy should not be
    reachable by guessing its slug.
    """
    import math

    from sqlalchemy import func, select

    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.blog.domain.taxonomy_models import (
        BlogPostTerm,
        CustomTaxonomy,
        CustomTaxonomyTerm,
    )

    term_stmt = (
        select(CustomTaxonomyTerm)
        .join(CustomTaxonomy, CustomTaxonomyTerm.taxonomy_id == CustomTaxonomy.id)
        .where(
            CustomTaxonomy.slug == taxonomy_slug,
            CustomTaxonomy.is_active.is_(True),
            CustomTaxonomyTerm.slug == term_slug,
        )
    )
    term = (await db.execute(term_stmt)).scalars().first()
    if term is None:
        raise HTTPException(status_code=404, detail="Term not found")

    base = (
        select(BlogPost)
        .join(BlogPostTerm, BlogPostTerm.post_id == BlogPost.id)
        .where(
            BlogPostTerm.term_id == term.id,
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
        )
    )
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    rows = (await db.execute(
        base.order_by(BlogPost.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "term": {"id": str(term.id), "name": term.name, "slug": term.slug,
                 "description": term.description},
        "items": [
            {
                "id": str(p.id), "slug": p.slug, "title": p.title,
                "excerpt": p.excerpt, "content": p.content,
                "cover_image_url": p.cover_image_url,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)) if total else 0,
    }


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


@admin_router.post(
    "/import/wxr",
    summary="Import a WordPress WXR (XML) export (Admin)",
)
async def admin_import_wxr(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
    _: Any = _require_blog_write,
) -> dict[str, Any]:
    """Import the only format a WordPress site can hand you.

    The JSON route above could not serve this: it takes a parsed dict, and XML
    cannot be one. The service documented that as an open gap, which meant
    migrating from WordPress meant converting the file by hand first.

    Runs the same orchestrator the data-exchange route runs
    (``blog.application.wxr_import``), so posts, pages and comments land the
    same way whichever page the operator uploads from. Pages route to the
    content module's importer; posts/comments to `import_json`.
    """
    from app.modules.blog.application.wxr_import import import_wxr as run_wxr_import
    from app.modules.blog.application.wxr_parser import parse_wxr

    raw = await file.read()
    try:
        parsed = parse_wxr(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"فایل WXR خوانده نشد: {exc}"
        ) from exc

    try:
        author_id = uuid.UUID(current_user["sub"])
    except Exception:
        author_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    # The parsed counts travel with the result so an operator can see what the
    # file held versus what landed — a WXR with fifty posts that imports three
    # should say so rather than look like a clean run.
    return await run_wxr_import(
        db, parsed, author_id=author_id, skip_existing=True
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
    summary="Unlink two posts (Admin)",
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
