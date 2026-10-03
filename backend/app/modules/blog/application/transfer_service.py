"""Blog content import/export service.

Export: Generates a JSON export of blog posts, categories and tags. Comments
are NOT included — ``export_all`` has no comment writer.

Import: Accepts a JSON file in our own export format. There is no WordPress
WXR/XML path: the import routes take ``body: dict``, so XML cannot even be
supplied, and no WXR parser exists in this project. Migrating a WordPress
install means converting the WXR to JSON first, which is an open gap.

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
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.blog.domain.models import (
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
                "locale": p.locale,
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
                # The WXR author field: WordPress writes an author email here
                # and a display name alongside it. Exporting the email is what
                # lets an import attribute the comment to the same person
                # instead of dropping it in a bucket.
                "author": c.author_email or "",
                "author_name": c.author_name or c.author_email or "",
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
        """Import blog content from a JSON export.

        Returns counts of created items. Existing slugs are skipped when
        skip_existing is True.
        """
        from app.shared.domain.slug import generate_slug

        stats = {"categories": 0, "tags": 0, "posts": 0, "skipped": 0}

        # Import categories
        cat_slug_map: dict[str, uuid.UUID] = {}
        for cat_data in data.get("categories", []):
            slug = cat_data.get("slug") or generate_slug(cat_data["name"])
            existing = (await db.execute(
                select(BlogCategory).where(BlogCategory.slug == slug)
            )).scalar_one_or_none()
            if existing:
                cat_slug_map[slug] = existing.id
                if skip_existing:
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
                if skip_existing:
                    continue
            tag = BlogTag(name=tag_data["name"], slug=slug)
            db.add(tag)
            await db.flush()
            tag_slug_map[slug] = tag.id
            stats["tags"] += 1

        # Import posts
        for post_data in data.get("posts", []):
            slug = post_data.get("slug") or generate_slug(post_data["title"])
            existing = (await db.execute(
                select(BlogPost).where(BlogPost.slug == slug)
            )).scalar_one_or_none()
            if existing and skip_existing:
                stats["skipped"] += 1
                continue

            category_id = None
            if post_data.get("category_slug"):
                category_id = cat_slug_map.get(post_data["category_slug"])

            published_at = None
            if post_data.get("published_at"):
                try:
                    published_at = datetime.fromisoformat(post_data["published_at"])
                except (ValueError, TypeError):
                    pass

            status_str = post_data.get("status", "draft").upper()
            try:
                post_status = BlogPostStatus(post_data.get("status", "draft"))
            except ValueError:
                post_status = BlogPostStatus.DRAFT

            post = BlogPost(
                author_id=author_id,
                title=post_data["title"],
                slug=slug,
                content=post_data.get("content", ""),
                excerpt=post_data.get("excerpt"),
                cover_image_url=post_data.get("cover_image_url"),
                status=post_status,
                locale=post_data.get("locale", "fa"),
                published_at=published_at,
                category_id=category_id,
            )
            db.add(post)
            await db.flush()

            # Attach tags
            for tag_slug in post_data.get("tag_slugs", []):
                tag_id = tag_slug_map.get(tag_slug)
                if tag_id:
                    db.add(BlogPostTag(post_id=post.id, tag_id=tag_id))

            stats["posts"] += 1

        await db.commit()
        logger.info("blog_imported", **stats)
        return stats
