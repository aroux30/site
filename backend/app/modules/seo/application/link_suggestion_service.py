"""Internal-link suggestions (Rank Math Pro's "Link Genius" engine).

Given a source post, rank the other published posts by how relevant they are as
internal-link targets. The ranking is TF-IDF cosine similarity over each post's
document — SEO title + description + excerpt + headings + body text — computed
on demand. Nothing is cached to a table: a suggestion recomputed from the live
bodies can never be stale, and at this scale (a shop blog, thousands of posts)
one scan is cheap.

The candidate pool follows Rank Math's shape: posts sharing the source's
category or tags, plus the most recent posts as a fallback, capped so the
similarity pass stays bounded. The document text is deliberately the same
material a reader would see — a post that shares vocabulary with the source in
its *title and headings* is a far better link target than one that merely
mentions the same word deep in the body.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.seo.application import link_text

#: How many candidates to pull before ranking. Rank Math uses 100; the
#: similarity pass is O(candidates × terms), so a few hundred is still trivial
#: while keeping the pool broad enough to surface a non-obvious match.
_POOL_LIMIT = 200

#: How many suggestions to return to the UI by default.
DEFAULT_SUGGESTION_LIMIT = 20


async def build_document(post: Any) -> str:
    """The text a candidate is scored on: title + excerpt + headings + body.

    Headings are pulled out of the body HTML so a post whose section titles
    share the source's topic ranks above one that only mentions a term in a
    passing sentence. The body itself is included in full — the analyzer's
    20k truncation is not applied here, because a link target's relevance is
    often decided by the part of the body the analyzer would drop.
    """
    from app.modules.seo.application.link_text import normalize_text

    parts: list[str] = []
    if getattr(post, "title", None):
        parts.append(str(post.title))
    if getattr(post, "excerpt", None):
        parts.append(str(post.excerpt))
    content = getattr(post, "content", None) or ""
    if content:
        # Headings carry the topical outline; body carries the detail. Both go
        # in, but the heading text is repeated so it weights a little higher.
        headings = re.findall(
            r"<h[1-6][^>]*>(.*?)</h[1-6]>", content, re.IGNORECASE | re.DOTALL
        )
        for heading in headings:
            cleaned = normalize_text(heading)
            if cleaned:
                parts.append(cleaned)
                parts.append(cleaned)
        parts.append(content)
    return " ".join(parts)


async def _candidate_posts(db: AsyncSession, source: Any) -> list[Any]:
    """Published posts that could be linked to from ``source``.

    Pool = posts sharing the source's category or tags, unioned with the most
    recent posts (so a new post with no taxonomy overlap is still reachable).
    The source itself is always excluded.
    """
    from app.modules.blog.domain.models import (
        BlogPost,
        BlogPostStatus,
        BlogPostTag,
    )

    conditions = []
    if getattr(source, "category_id", None):
        conditions.append(BlogPost.category_id == source.category_id)

    # Shared tags require the source's tag ids; fetch them, then match.
    source_tag_ids = (
        await db.execute(select(BlogPostTag.tag_id).where(BlogPostTag.post_id == source.id))
    ).scalars().all()
    if source_tag_ids:
        related_post_ids = (
            await db.execute(
                select(BlogPostTag.post_id).where(
                    BlogPostTag.tag_id.in_(source_tag_ids),
                    BlogPostTag.post_id != source.id,
                )
            )
        ).scalars().all()
        if related_post_ids:
            conditions.append(BlogPost.id.in_(related_post_ids))

    base = (
        select(BlogPost)
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            BlogPost.id != source.id,
        )
        .order_by(BlogPost.published_at.desc().nullslast())
        .limit(_POOL_LIMIT)
    )
    if conditions:
        base = base.where(or_(*conditions))

    pool = list((await db.execute(base)).scalars().all())
    if len(pool) >= DEFAULT_SUGGESTION_LIMIT:
        return pool

    # Fallback: fill with recent posts when the taxonomy pool is thin.
    recent = (
        await db.execute(
            select(BlogPost)
            .where(
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
                BlogPost.id != source.id,
            )
            .order_by(BlogPost.published_at.desc().nullslast())
            .limit(_POOL_LIMIT)
        )
    ).scalars().all()
    seen = {p.id for p in pool}
    for post in recent:
        if post.id not in seen:
            pool.append(post)
            seen.add(post.id)
    return pool


async def suggest_links(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    limit: int = DEFAULT_SUGGESTION_LIMIT,
    exclude_linked: bool = True,
) -> list[dict[str, Any]]:
    """Rank candidate posts as link targets for ``post_id``.

    ``exclude_linked`` drops posts the source already links to (from the
    indexed link table) — suggesting a link that already exists is the fastest
    way to make the feature feel broken.
    """
    from app.modules.blog.domain.models import BlogPost

    source = (
        await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    ).scalar_one_or_none()
    if source is None:
        return []

    candidates = await _candidate_posts(db, source)

    already_linked: set[uuid.UUID] = set()
    if exclude_linked:
        from app.modules.seo.domain.link_models import SeoInternalLink

        linked = (
            await db.execute(
                select(SeoInternalLink.target_post_id).where(
                    SeoInternalLink.post_id == post_id,
                    SeoInternalLink.target_post_id.is_not(None),
                )
            )
        ).scalars().all()
        already_linked = {tid for tid in linked if tid is not None}

    target_doc = await build_document(source)
    target_tokens = link_text.tokenize(target_doc)

    candidate_tokens: dict[str, list[str]] = {}
    by_id: dict[str, Any] = {}
    for post in candidates:
        if post.id in already_linked:
            continue
        key = str(post.id)
        candidate_tokens[key] = link_text.tokenize(await build_document(post))
        by_id[key] = post

    ranked = link_text.cosine_tfidf(target_tokens, candidate_tokens, top_n=limit)

    out: list[dict[str, Any]] = []
    for candidate_id, score in ranked:
        post = by_id[candidate_id]
        out.append(
            {
                "post_id": post.id,
                "title": post.title,
                "slug": post.slug,
                # Relative storefront path the editor inserts as the href.
                "url": f"/blog/{post.slug}",
                "score": round(score, 4),
                "excerpt": (post.excerpt or "")[:200],
            }
        )
    return out


async def related_posts(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Related posts for the storefront's "read next" strip.

    Same ranking as :func:`suggest_links`; kept as a named function so the
    public-facing "related" list and the editor's suggestion list share one
    implementation (two rankings would drift, and the reader would see a
    different "related" set than the editor was shown).
    """
    return await suggest_links(db, post_id=post_id, limit=limit, exclude_linked=False)
