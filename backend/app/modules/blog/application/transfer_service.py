"""Blog content import/export service.

Export: Generates a JSON export of blog posts, categories, tags, comments
and menus (version 1.1).

Import: Accepts our own JSON export shape AND the dict the WXR parser
produces (``wxr_parser.parse_wxr``) — both spellings of the category key are
read (``category_slug`` singular from our export, ``category_slugs`` list from
WXR), comments import with a fingerprint-based skip on re-import, and a
slug collision with ``skip_existing=False`` updates in place instead of
creating a duplicate. Pages are NOT handled here: WXR pages route to the
content module's importer via ``blog.application.wxr_import``.

Usage:
    data = await BlogTransferService.export_all(db)
    stats = await BlogTransferService.import_json(db, data, author_id=...)
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.modules.blog.domain.models import (
    COMMENT_RESOURCE_BLOG_POST,
    COMMENT_TYPE_COMMENT,
    BlogCategory,
    BlogComment,
    BlogPost,
    BlogPostStatus,
    BlogPostTag,
    BlogTag,
    CommentStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _upsert_post_seo(
    db: "AsyncSession", post_id: uuid.UUID, seo: dict[str, Any]
) -> None:
    """Write a post's SEO fields, creating the row when it does not exist.

    The importer is the second half of the WXR SEO fix: the parser reads
    ``rank_math_*`` / ``_yoast_wpseo_*`` meta into a dict, and without this
    the dict was parsed and dropped — the author's hand-written search title
    and description silently replaced by generated defaults. Fields the file
    did not carry are left alone on an existing row rather than nulled, so a
    re-import of a partial file cannot erase SEO a person typed here.
    """
    from app.modules.seo.domain.models import SEOMetadata

    allowed = {
        "title", "description", "canonical_url",
        "og_title", "og_description", "og_image", "schema_markup",
        "focus_keyword",
    }
    values = {k: v for k, v in seo.items() if k in allowed and v}
    if not values:
        return
    record = (
        await db.execute(
            select(SEOMetadata).where(
                SEOMetadata.resource_type == "blog_post",
                SEOMetadata.resource_id == post_id,
            )
        )
    ).scalar_one_or_none()
    if record is None:
        record = SEOMetadata(
            resource_type="blog_post", resource_id=post_id, **values
        )
        db.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
    await db.flush()


class BlogTransferService:
    """Import/export blog content."""

    @staticmethod
    async def export_all(db: "AsyncSession") -> dict[str, Any]:
        """Export all blog content as a JSON-serializable dict."""
        # Categories
        cats = (await db.execute(select(BlogCategory))).scalars().all()
        categories_data = [
            {"name": c.name, "slug": c.slug, "id": str(c.id)}
            for c in cats
        ]

        # Tags
        tags = (await db.execute(select(BlogTag))).scalars().all()
        tags_data = [
            {"name": t.name, "slug": t.slug, "id": str(t.id)}
            for t in tags
        ]

        # Posts with tags
        stmt = (
            select(BlogPost)
            .options(selectinload(BlogPost.post_tags), selectinload(BlogPost.category))
            .where(BlogPost.deleted_at.is_(None))
            .order_by(BlogPost.created_at.asc())
        )
        posts = (await db.execute(stmt)).scalars().all()
        posts_data = []
        for p in posts:
            tag_slugs = [
                pt.tag.slug for pt in p.post_tags
                if pt.tag is not None
            ] if p.post_tags else []
            posts_data.append({
                "title": p.title,
                "slug": p.slug,
                "content": p.content,
                "excerpt": p.excerpt,
                "cover_image_url": p.cover_image_url,
                "status": p.status.value if isinstance(p.status, BlogPostStatus) else str(p.status),
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "category_slug": p.category.slug if p.category else None,
                "tag_slugs": tag_slugs,
                # WordPress's meta carried the interesting per-post fields, and
                # dropping them is what made an export lossy in a way nobody
                # noticed until an import came back with them empty.
                "meta": {
                    "allow_comments": bool(p.allow_comments),
                    "is_featured": bool(p.is_featured),
                    "post_format": p.post_format,
                    "visibility": (p.visibility.value
                                   if hasattr(p.visibility, "value")
                                   else p.visibility),
                    # `menu_order` is a page field, not a post one. Writing it
                    # here would have been a key the importer reads and never
                    # finds, which is how a "complete" export loses a field
                    # quietly.
                    "author_id": str(p.author_id) if p.author_id else None,
                },
            })

        # Comments. A blog export without them is not a blog: the discussion is
        # half the content, and an import that silently dropped every comment
        # would lose it without saying so.
        comments = (await db.execute(
            select(BlogComment)
            .where(BlogComment.comment_type == COMMENT_TYPE_COMMENT)
            .order_by(BlogComment.created_at.asc())
        )).scalars().all()
        comments_data = [
            {
                # The WXR author field carried an email address; the column
                # was dropped on 2026-10-07 with the rest of the email feature
                # (migration `rmemail1`), so the name is the only attribution
                # that travels now.
                "author": "",
                "author_name": c.author_name or "",
                "author_url": c.author_url,
                "author_ip": c.author_ip,
                "date_gmt": c.created_at.isoformat() if c.created_at else None,
                "content": c.content,
                "status": c.status.value if isinstance(c.status, CommentStatus) else str(c.status),
                "parent": 0,  # filled below, once every comment has an index
                "comment_post_id": str(c.post_id) if c.post_id else None,
            }
            for c in comments
        ]
        # Threading, by post. The flat list above carries `parent: 0` because a
        # comment's own id is not known until it is assigned; WordPress readers
        # reject a reply that points at nothing, so an export that loses the
        # tree is a downgrade even though every comment is present.
        by_id = {c.id: c for c in comments}
        for entry, comment in zip(comments_data, comments):
            parent = getattr(comment, "parent_id", None)
            if parent is not None and parent in by_id:
                entry["parent"] = str(parent)

        # Menu items, so a migration brings the navigation with it.
        # Grouped by location because that is how the site renders them — one
        # table with a `location` column, not a menu row with children — and
        # an export that flattened the grouping would produce a nav the importer
        # cannot place back.
        menus_data: list[dict[str, Any]] = []
        try:
            from app.modules.content.domain.models import SiteMenu

            rows = (await db.execute(
                select(SiteMenu).order_by(SiteMenu.location, SiteMenu.position)
            )).scalars().all()
            by_location: dict[str, list[dict[str, Any]]] = {}
            for item in rows:
                by_location.setdefault(item.location or "", []).append({
                    "title": item.title,
                    "url": item.url,
                    "parent_id": str(item.parent_id) if item.parent_id else None,
                    "position": item.position,
                })
            menus_data = [
                {"location": loc, "items": items}
                for loc, items in sorted(by_location.items())
            ]
        except Exception as exc:  # noqa: BLE001
            # A missing menu module must not lose the blog export. WordPress's
            # own exporter treats navigation as separate from content for the
            # same reason.
            logger.info("blog_export_menus_skipped", error=str(exc))

        export = {
            "format": "itrip-blog-export",
            # 1.1: comments, navigation and per-post meta joined the payload.
            # A consumer that reads `version` should refuse 1.0 rather than
            # import a partial site and believe it imported everything.
            "version": "1.1",
            "exported_at": datetime.now(UTC).isoformat(),
            "categories": categories_data,
            "tags": tags_data,
            "posts": posts_data,
            "comments": comments_data,
            "menus": menus_data,
            "counts": {
                "categories": len(categories_data),
                "tags": len(tags_data),
                "posts": len(posts_data),
                "comments": len(comments_data),
                "menus": len(menus_data),
            },
        }
        logger.info(
            "blog_exported",
            categories=len(categories_data),
            tags=len(tags_data),
            posts=len(posts_data),
            comments=len(comments_data),
        )
        return export

    @staticmethod
    async def import_json(
        db: "AsyncSession",
        data: dict[str, Any],
        *,
        author_id: uuid.UUID,
        skip_existing: bool = True,
    ) -> dict[str, int]:
        """Import blog content from a JSON export or a parsed WXR file.

        Reads both of our own export shape (``category_slug`` singular, comments
        carrying UUIDs) and the WXR parser's shape (``category_slugs`` list,
        ``tag_slugs`` list, comments carrying WordPress ids plus a
        ``post_slug``). The two shapes drifted once — the parser emitted
        plural category keys the importer never read, so every WXR-imported
        post landed with no category and no tag while the category rows
        themselves were created. The import path is one implementation that
        accepts both spellings rather than two that drift again.

        Returns counts of created items. Existing slugs are skipped when
        skip_existing is True.
        """
        from app.shared.domain.slug import generate_slug

        stats = {
            "categories": 0,
            "tags": 0,
            "posts": 0,
            "skipped": 0,
            "comments": 0,
            "comments_skipped": 0,
        }

        # Import categories. WXR carries real names and (sometimes) slugs;
        # a slug-less row gets one generated from the name, which is what
        # WordPress itself does.
        cat_slug_map: dict[str, uuid.UUID] = {}
        for cat_data in data.get("categories", []):
            slug = cat_data.get("slug") or generate_slug(cat_data["name"])
            existing = (await db.execute(
                select(BlogCategory).where(BlogCategory.slug == slug)
            )).scalar_one_or_none()
            if existing:
                cat_slug_map[slug] = existing.id
                # An existing slug is reused whatever `skip_existing` says:
                # the slug is the identity here, and inserting a second row
                # with it violates the unique constraint. `skip_existing`
                # decides whether POSTS are skipped or updated — it was
                # never meant to mean "duplicate the taxonomy", and reading
                # it that way made every re-import a 500.
                continue
            cat = BlogCategory(name=cat_data["name"], slug=slug)
            db.add(cat)
            await db.flush()
            cat_slug_map[slug] = cat.id
            stats["categories"] += 1

        # Import tags
        tag_slug_map: dict[str, uuid.UUID] = {}
        for tag_data in data.get("tags", []):
            slug = tag_data.get("slug") or generate_slug(tag_data["name"])
            existing = (await db.execute(
                select(BlogTag).where(BlogTag.slug == slug)
            )).scalar_one_or_none()
            if existing:
                tag_slug_map[slug] = existing.id
                # Same rule as categories: reuse, never duplicate.
                continue
            tag = BlogTag(name=tag_data["name"], slug=slug)
            db.add(tag)
            await db.flush()
            tag_slug_map[slug] = tag.id
            stats["tags"] += 1

        # Import posts
        slug_to_post: dict[str, BlogPost] = {}
        wxr_id_to_slug: dict[str, str] = {}
        for post_data in data.get("posts", []):
            slug = post_data.get("slug") or generate_slug(post_data["title"])
            existing = (await db.execute(
                select(BlogPost).where(BlogPost.slug == slug)
            )).scalar_one_or_none()
            if existing and skip_existing:
                stats["skipped"] += 1
                slug_to_post[slug] = existing
                if post_data.get("wxr_post_id"):
                    wxr_id_to_slug[str(post_data["wxr_post_id"])] = slug
                continue

            # Both spellings: our export writes `category_slug` (singular);
            # the WXR parser writes `category_slugs` (list, the item's own).
            # The list wins when present; the schema keeps a single primary
            # category and the first listed is it.
            category_slug = post_data.get("category_slug")
            category_slugs = post_data.get("category_slugs")
            if not category_slug and isinstance(category_slugs, list) and category_slugs:
                category_slug = category_slugs[0]

            category_id = None
            if category_slug:
                category_id = cat_slug_map.get(category_slug)

            published_at = None
            if post_data.get("published_at"):
                try:
                    published_at = datetime.fromisoformat(post_data["published_at"])
                except (ValueError, TypeError):
                    pass

            try:
                post_status = BlogPostStatus(post_data.get("status", "draft"))
            except ValueError:
                post_status = BlogPostStatus.DRAFT

            if existing is not None:
                # skip_existing=False: update the existing post in place
                # instead of creating a slug-duplicate.
                existing.title = post_data["title"]
                existing.content = post_data.get("content", "")
                existing.excerpt = post_data.get("excerpt")
                # A file with no featured image (`_thumbnail_id` absent or
                # unresolvable) must not wipe the cover the post already has:
                # the parser emits the key with `None` for every such post,
                # and assigning it unconditionally erased covers on re-import.
                if post_data.get("cover_image_url"):
                    existing.cover_image_url = post_data["cover_image_url"]
                existing.status = post_status
                existing.published_at = published_at
                if category_id is not None:
                    existing.category_id = category_id
                await db.flush()
                post = existing
            else:
                post = BlogPost(
                    author_id=author_id,
                    title=post_data["title"],
                    slug=slug,
                    content=post_data.get("content", ""),
                    excerpt=post_data.get("excerpt"),
                    cover_image_url=post_data.get("cover_image_url"),
                    status=post_status,
                    published_at=published_at,
                    category_id=category_id,
                )
                db.add(post)
                await db.flush()
                stats["posts"] += 1

            slug_to_post[slug] = post
            if post_data.get("wxr_post_id"):
                wxr_id_to_slug[str(post_data["wxr_post_id"])] = slug

            # Attach tags. The WXR parser emits `tag_slugs` (list); our own
            # export does the same. A string is accepted for older payloads.
            raw_tags = post_data.get("tag_slugs") or []
            if isinstance(raw_tags, str):
                raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            if existing is not None:
                # The update path: replace the post's tag set. Adding on top
                # of the existing rows hit the UNIQUE(post_id, tag_id)
                # constraint and turned every re-import into a 500 — the
                # "import again to update" flow never worked at all.
                await db.execute(
                    delete(BlogPostTag).where(BlogPostTag.post_id == post.id)
                )
            for tag_slug in raw_tags:
                tag_id = tag_slug_map.get(tag_slug)
                if tag_id:
                    db.add(BlogPostTag(post_id=post.id, tag_id=tag_id))

            # `allow_comments` from WXR meta: the per-post switch the post
            # dialog exposes. Our own export keeps it in meta too.
            meta = post_data.get("meta")
            if isinstance(meta, dict) and "allow_comments" in meta:
                post.allow_comments = bool(meta["allow_comments"])

            # SEO from the file's Rank Math / Yoast meta. Parsed and never
            # imported would mean the author's hand-tuned title and
            # description were replaced by generated defaults on every
            # import — the SEO half of "the import wrecked the article".
            seo = post_data.get("seo")
            if isinstance(seo, dict) and seo:
                await _upsert_post_seo(db, post.id, seo)

        # Import comments. They were parsed and exported but never imported —
        # an export declaring "comments joined the payload" whose import
        # silently dropped them. Each comment resolves its post by slug
        # (WXR) or by UUID (our own export), and threads by the same file's
        # ids where possible; an unresolvable parent imports as a root
        # comment rather than being dropped.
        comments_data = data.get("comments") or []
        if comments_data:
            # Existing comments per post, for the re-import fingerprint.
            existing_fingerprints: dict[uuid.UUID, set[tuple]] = {}
            if skip_existing:
                posts_seen = {p.id for p in slug_to_post.values()}
                if posts_seen:
                    rows = (await db.execute(
                        select(BlogComment).where(
                            BlogComment.resource_id.in_(posts_seen)
                        )
                    )).scalars().all()
                    for c in rows:
                        existing_fingerprints.setdefault(c.resource_id, set()).add(
                            (c.author_name or "", (c.content or "")[:300])
                        )

            wxr_comment_id_map: dict[str, uuid.UUID] = {}
            for comment_data in comments_data:
                # Resolve the target post: slug first (WXR), then UUID
                # (our own export's `comment_post_id`).
                target_slug = comment_data.get("post_slug")
                post_obj = slug_to_post.get(target_slug) if target_slug else None
                if post_obj is None:
                    raw_post_id = comment_data.get("comment_post_id")
                    if raw_post_id:
                        try:
                            post_uuid = uuid.UUID(str(raw_post_id))
                            post_obj = await db.get(BlogPost, post_uuid)
                        except (ValueError, TypeError):
                            # A WordPress id: map through the posts imported
                            # above.
                            mapped_slug = wxr_id_to_slug.get(str(raw_post_id))
                            post_obj = slug_to_post.get(mapped_slug) if mapped_slug else None
                if post_obj is None:
                    stats["comments_skipped"] += 1
                    continue

                # Fingerprint on the NAME: since the email column was dropped
                # (migration `rmemail1`) every incoming comment carries
                # `author: ""`, while the existing set below is keyed by
                # `author_name`. Fingerprinting the always-empty `author`
                # would make every re-import see every comment as new and
                # duplicate the whole thread.
                fingerprint = (
                    comment_data.get("author_name") or "",
                    (comment_data.get("content") or "")[:300],
                )
                if (
                    skip_existing
                    and fingerprint in existing_fingerprints.get(post_obj.id, set())
                ):
                    stats["comments_skipped"] += 1
                    continue

                try:
                    comment_status = CommentStatus(
                        comment_data.get("status", "pending")
                    )
                except ValueError:
                    comment_status = CommentStatus.PENDING

                created_at = None
                if comment_data.get("date_gmt"):
                    try:
                        created_at = datetime.fromisoformat(comment_data["date_gmt"])
                    except (ValueError, TypeError):
                        pass

                comment = BlogComment(
                    post_id=post_obj.id,
                    resource_type=COMMENT_RESOURCE_BLOG_POST,
                    resource_id=post_obj.id,
                    author_name=comment_data.get("author_name") or None,
                    author_url=comment_data.get("author_url") or None,
                    author_ip=comment_data.get("author_ip") or None,
                    content=comment_data.get("content") or "",
                    status=comment_status,
                )
                if created_at is not None:
                    comment.created_at = created_at
                db.add(comment)
                await db.flush()
                stats["comments"] += 1
                if comment_data.get("wxr_comment_id"):
                    wxr_comment_id_map[str(comment_data["wxr_comment_id"])] = comment.id

            # Second pass: thread replies now that every comment has an id.
            for comment_data in comments_data:
                parent_ref = str(comment_data.get("parent") or "0")
                if parent_ref in ("0", ""):
                    continue
                new_parent_id = wxr_comment_id_map.get(parent_ref)
                if new_parent_id is None:
                    continue
                child_id = wxr_comment_id_map.get(
                    str(comment_data.get("wxr_comment_id") or "")
                )
                if child_id is None or child_id == new_parent_id:
                    continue
                child = await db.get(BlogComment, child_id)
                if child is not None and child.parent_id is None:
                    child.parent_id = new_parent_id

        await db.commit()
        logger.info("blog_imported", **stats)
        return stats
