"""REST API for Link Genius: internal-link suggestions + keyword maps.

Composed into the SEO module's existing routers by ``api/__init__.py``: the
admin routes attach under the SEO admin router (so they inherit
``/admin/seo``), and the public related-posts route attaches under the
customer router (``/seo``). This keeps the already-large ``routes.py`` from
growing another few hundred lines without inventing a second mount point.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions
from app.modules.seo.application import (
    link_extraction_service,
    link_map_service,
    link_suggestion_service,
)
from app.modules.seo.domain.link_models import (
    SeoInternalLink,
    SeoLinkMap,
    SeoLinkMapVariation,
)
from app.modules.seo.schemas.link_genius import (
    IncomingLink,
    IncomingLinksResponse,
    InternalLinkItem,
    LinkAuditItem,
    LinkAuditListResponse,
    LinkAuditMarkSafeRequest,
    LinkAuditRunResponse,
    LinkMapApplyRequest,
    LinkMapApplyResponse,
    LinkMapCreate,
    LinkMapListResponse,
    LinkMapOut,
    LinkMapPreviewRequest,
    LinkMapPreviewResponse,
    LinkMapUpdate,
    LinkSuggestion,
    LinkSuggestionResponse,
    RelatedPostsResponse,
    RelatedPost,
)

admin_router = APIRouter(prefix="/admin/seo", tags=["admin-seo-link-genius"])

_require_seo_write = Depends(RequirePermissions("seo:write"))


async def _site_hosts(db: AsyncSession) -> tuple[set[str], str | None]:
    """The hosts that count as internal + the site base URL, from site options."""
    from app.modules.settings.application.site_options_service import public_base_url
    from app.modules.seo.application.link_counter_service import site_hosts_from

    base = await public_base_url(db)
    return site_hosts_from(base), base


async def _load_post(db: AsyncSession, post_id: uuid.UUID):
    from app.modules.blog.domain.models import BlogPost

    post = (
        await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("BlogPost", f"Blog post '{post_id}' not found")
    return post


# ── Suggestions ─────────────────────────────────────────────────────────────


@admin_router.get(
    "/posts/{post_id}/link-suggestions",
    response_model=LinkSuggestionResponse,
    summary="Rank internal-link targets for a post (admin)",
    dependencies=[_require_seo_write],
)
async def admin_link_suggestions(
    post_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> LinkSuggestionResponse:
    """TF-IDF ranked suggestions, computed live from the posts."""
    await _load_post(db, post_id)
    suggestions = await link_suggestion_service.suggest_links(
        db, post_id=post_id, limit=limit
    )
    return LinkSuggestionResponse(
        source_post_id=post_id,
        suggestions=[LinkSuggestion(**s) for s in suggestions],
        total=len(suggestions),
    )


@admin_router.get(
    "/posts/{post_id}/incoming-links",
    response_model=IncomingLinksResponse,
    summary="Posts that link to this one (admin)",
    dependencies=[_require_seo_write],
)
async def admin_incoming_links(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IncomingLinksResponse:
    """Reverse-link edges from the indexed link table."""
    from app.modules.blog.domain.models import BlogPost

    await _load_post(db, post_id)
    rows = (
        await db.execute(
            select(SeoInternalLink, BlogPost)
            .join(BlogPost, BlogPost.id == SeoInternalLink.post_id)
            .where(SeoInternalLink.target_post_id == post_id)
        )
    ).all()
    incoming = [
        IncomingLink(
            post_id=link.post_id,
            title=post.title,
            slug=post.slug,
            url=f"/blog/{post.slug}",
            anchor_text=link.anchor_text,
        )
        for link, post in rows
    ]
    return IncomingLinksResponse(post_id=post_id, incoming=incoming, total=len(incoming))


@admin_router.post(
    "/posts/{post_id}/reindex-links",
    summary="Re-scan a post body and refresh its link index (admin)",
    dependencies=[_require_seo_write],
)
async def admin_reindex_post_links(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Force a rescan for one post (the save hook normally does this)."""
    post = await _load_post(db, post_id)
    hosts, base = await _site_hosts(db)
    count = await link_extraction_service.index_post_links(
        db, post_id=post_id, content=post.content or "", site_hosts=hosts, base_url=base
    )
    return {"indexed": count}


@admin_router.get(
    "/posts/{post_id}/links",
    response_model=list[InternalLinkItem],
    summary="The managed links indexed for a post (admin)",
    dependencies=[_require_seo_write],
)
async def admin_post_links(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[InternalLinkItem]:
    await _load_post(db, post_id)
    rows = (
        await db.execute(
            select(SeoInternalLink)
            .where(SeoInternalLink.post_id == post_id)
            .order_by(SeoInternalLink.link_type, SeoInternalLink.url)
        )
    ).scalars().all()
    return [InternalLinkItem.model_validate(r) for r in rows]


# ── Keyword maps ────────────────────────────────────────────────────────────


async def _serialize_map(link_map: SeoLinkMap) -> LinkMapOut:
    return LinkMapOut(
        id=link_map.id,
        name=link_map.name,
        target_url=link_map.target_url,
        target_post_id=link_map.target_post_id,
        max_links_per_post=link_map.max_links_per_post,
        auto_link_on_publish=link_map.auto_link_on_publish,
        case_sensitive=link_map.case_sensitive,
        is_active=link_map.is_active,
        variations=[
            {"id": v.id, "keyword": v.keyword, "kind": v.kind}
            for v in link_map.variations
        ],
    )


@admin_router.get(
    "/link-maps",
    response_model=LinkMapListResponse,
    summary="List keyword maps (admin)",
    dependencies=[_require_seo_write],
)
async def admin_list_link_maps(
    db: AsyncSession = Depends(get_db),
) -> LinkMapListResponse:
    rows = (
        await db.execute(select(SeoLinkMap).order_by(SeoLinkMap.name))
    ).scalars().all()
    items = [await _serialize_map(m) for m in rows]
    return LinkMapListResponse(items=items, total=len(items))


@admin_router.post(
    "/link-maps",
    response_model=LinkMapOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a keyword map (admin)",
    dependencies=[_require_seo_write],
)
async def admin_create_link_map(
    body: LinkMapCreate,
    db: AsyncSession = Depends(get_db),
) -> LinkMapOut:
    link_map = SeoLinkMap(
        name=body.name,
        target_url=body.target_url,
        max_links_per_post=body.max_links_per_post,
        auto_link_on_publish=body.auto_link_on_publish,
        case_sensitive=body.case_sensitive,
        is_active=body.is_active,
    )
    db.add(link_map)
    await db.flush()
    for variation in body.variations:
        db.add(
            SeoLinkMapVariation(
                map_id=link_map.id, keyword=variation.keyword, kind=variation.kind
            )
        )
    await db.commit()
    await db.refresh(link_map)
    return await _serialize_map(link_map)


@admin_router.patch(
    "/link-maps/{map_id}",
    response_model=LinkMapOut,
    summary="Update a keyword map (admin)",
    dependencies=[_require_seo_write],
)
async def admin_update_link_map(
    map_id: uuid.UUID,
    body: LinkMapUpdate,
    db: AsyncSession = Depends(get_db),
) -> LinkMapOut:
    link_map = (
        await db.execute(select(SeoLinkMap).where(SeoLinkMap.id == map_id))
    ).scalar_one_or_none()
    if link_map is None:
        raise NotFoundError("SeoLinkMap", f"Link map '{map_id}' not found")

    for field in (
        "name",
        "target_url",
        "max_links_per_post",
        "auto_link_on_publish",
        "case_sensitive",
        "is_active",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(link_map, field, value)

    if body.variations is not None:
        # Replace wholesale: a variation the operator deleted must disappear,
        # and an upsert would leave the removed keyword matching forever.
        await db.execute(
            delete(SeoLinkMapVariation).where(SeoLinkMapVariation.map_id == map_id)
        )
        for variation in body.variations:
            db.add(
                SeoLinkMapVariation(
                    map_id=map_id, keyword=variation.keyword, kind=variation.kind
                )
            )

    await db.commit()
    await db.refresh(link_map)
    return await _serialize_map(link_map)


@admin_router.delete(
    "/link-maps/{map_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a keyword map (admin)",
    dependencies=[_require_seo_write],
)
async def admin_delete_link_map(
    map_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    link_map = (
        await db.execute(select(SeoLinkMap).where(SeoLinkMap.id == map_id))
    ).scalar_one_or_none()
    if link_map is None:
        raise NotFoundError("SeoLinkMap", f"Link map '{map_id}' not found")
    await db.delete(link_map)
    await db.commit()


@admin_router.post(
    "/link-maps/preview",
    response_model=LinkMapPreviewResponse,
    summary="Preview a keyword map against a post body (admin)",
    dependencies=[_require_seo_write],
)
async def admin_preview_link_map(
    body: LinkMapPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> LinkMapPreviewResponse:
    """Dry-run: how many links the map would insert, and which keywords hit.

    Reads the post body and computes without writing — the operator sees the
    effect before trusting the map.
    """
    post = await _load_post(db, body.post_id)
    content = post.content or ""
    new_content, inserted = link_map_service.apply_keyword_map(
        content,
        keywords=body.keywords,
        target_url=body.target_url,
        max_links_per_post=body.max_links_per_post,
        case_sensitive=body.case_sensitive,
    )
    # Report which keywords actually matched (by comparing the linked form).
    matches = [
        k
        for k in body.keywords
        if f'href="{body.target_url}"' in new_content
        and link_map_service.count_existing_links(new_content, body.target_url)
        > link_map_service.count_existing_links(content, body.target_url)
        and _keyword_present_in_new(content, new_content, k)
    ]
    return LinkMapPreviewResponse(inserted=inserted, matches=matches)


def _keyword_present_in_new(old: str, new: str, keyword: str) -> bool:
    """Whether ``keyword`` is newly wrapped as an anchor in ``new`` vs ``old``."""
    marker = f">{keyword}</a>"
    return marker in new and marker not in old


@admin_router.post(
    "/link-maps/apply",
    response_model=LinkMapApplyResponse,
    summary="Apply a keyword map to one post or all posts (admin)",
    dependencies=[_require_seo_write],
)
async def admin_apply_link_map(
    body: LinkMapApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> LinkMapApplyResponse:
    """Write the auto-links into the post bodies.

    Applying to all posts is the operator's "run this map across the blog"
    action; it is deliberately explicit (never automatic) because it edits
    published content.
    """
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

    link_map = (
        await db.execute(select(SeoLinkMap).where(SeoLinkMap.id == body.map_id))
    ).scalar_one_or_none()
    if link_map is None:
        raise NotFoundError("SeoLinkMap", f"Link map '{body.map_id}' not found")

    keywords = [v.keyword for v in link_map.variations]
    if not keywords:
        raise ValidationError(
            "نقشهٔ کلیدواژه هیچ عبارت فعالی ندارد", error_code="EMPTY_LINK_MAP"
        )

    if body.all_posts:
        posts = list(
            (
                await db.execute(
                    select(BlogPost).where(
                        BlogPost.status == BlogPostStatus.PUBLISHED,
                        BlogPost.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        )
    elif body.post_id is not None:
        posts = [await _load_post(db, body.post_id)]
    else:
        raise ValidationError(
            "یکی از post_id یا all_posts الزامی است", error_code="TARGET_REQUIRED"
        )

    posts_updated = 0
    links_inserted = 0
    hosts, base = await _site_hosts(db)
    for post in posts:
        new_content, inserted = link_map_service.apply_keyword_map(
            post.content or "",
            keywords=keywords,
            target_url=link_map.target_url,
            max_links_per_post=link_map.max_links_per_post,
            case_sensitive=link_map.case_sensitive,
        )
        if inserted > 0:
            post.content = new_content
            posts_updated += 1
            links_inserted += inserted
            # Keep the link index in step with the body we just rewrote.
            await link_extraction_service.index_post_links(
                db,
                post_id=post.id,
                content=new_content,
                site_hosts=hosts,
                base_url=base,
            )

    await db.commit()
    return LinkMapApplyResponse(posts_updated=posts_updated, links_inserted=links_inserted)


# ── Broken-link crawler ─────────────────────────────────────────────────────


@admin_router.get(
    "/link-audit",
    response_model=LinkAuditListResponse,
    summary="Broken-link audit results (admin)",
    dependencies=[_require_seo_write],
)
async def admin_list_link_audit(
    category: str | None = Query(None, description="ok|broken|redirect|timeout|error|blocked"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    hide_safe: bool = Query(True, description="Hide URLs marked safe"),
    db: AsyncSession = Depends(get_db),
) -> LinkAuditListResponse:
    from app.modules.seo.application.link_audit_service import list_results

    rows, total, counts = await list_results(
        db, category=category, page=page, page_size=page_size, hide_safe=hide_safe
    )
    return LinkAuditListResponse(
        items=[LinkAuditItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        counts=counts,
    )


@admin_router.post(
    "/link-audit/run",
    response_model=LinkAuditRunResponse,
    summary="Run the broken-link crawler now (admin)",
    dependencies=[_require_seo_write],
)
async def admin_run_link_audit(
    force: bool = Query(False, description="Ignore the 24h re-check window"),
    batch_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> LinkAuditRunResponse:
    """The admin's "check now" button — same service the scheduled task uses.

    A synchronous run on purpose: the operator pressed a button and wants the
    result, and a bounded batch (≤200) keeps the request inside a normal
    timeout. The nightly task handles the long tail.
    """
    from app.modules.seo.application.link_audit_service import run_audit

    summary = await run_audit(db, batch_size=batch_size, force=force)
    return LinkAuditRunResponse(
        checked=int(summary["checked"]),
        broken=int(summary["broken"]),
        redirect=int(summary["redirect"]),
        total=int(summary["total"]),
        timeout=int(summary.get("timeout", 0)),
        error=int(summary.get("error", 0)),
        blocked=int(summary.get("blocked", 0)),
    )


@admin_router.patch(
    "/link-audit/{audit_id}/safe",
    summary="Mark an audited URL as known-safe (admin)",
    dependencies=[_require_seo_write],
)
async def admin_mark_link_safe(
    audit_id: uuid.UUID,
    body: LinkAuditMarkSafeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Silence a URL that blocks bots but works in a browser (403/paywall)."""
    from app.modules.seo.application.link_audit_service import mark_safe

    ok = await mark_safe(db, audit_id, body.safe)
    if not ok:
        raise NotFoundError("SeoLinkAudit", f"Audit row '{audit_id}' not found")
    return {"safe": body.safe}


@admin_router.delete(
    "/link-audit",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all broken-link audit results (admin)",
    dependencies=[_require_seo_write],
)
async def admin_clear_link_audit(db: AsyncSession = Depends(get_db)) -> None:
    from app.modules.seo.application.link_audit_service import clear_results

    await clear_results(db)


# ── Public: related posts for the storefront ────────────────────────────────


public_router = APIRouter(tags=["seo-link-genius"])


@public_router.get(
    "/blog/{slug}/related",
    response_model=RelatedPostsResponse,
    summary="Related posts for a blog post (public)",
)
async def public_related_posts(
    slug: str,
    limit: int = Query(5, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
) -> RelatedPostsResponse:
    """Same ranking the editor sees, served to the storefront's read-next strip."""
    from app.modules.blog.domain.models import BlogPost

    post = (
        await db.execute(select(BlogPost).where(BlogPost.slug == slug))
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("BlogPost", f"Blog post '{slug}' not found")
    items = await link_suggestion_service.related_posts(
        db, post_id=post.id, limit=limit
    )
    return RelatedPostsResponse(
        items=[
            RelatedPost(
                post_id=i["post_id"],
                title=i["title"],
                slug=i["slug"],
                url=i["url"],
                score=i["score"],
            )
            for i in items
        ]
    )
