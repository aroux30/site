"""Re-import (`skip_existing=false`) must update, not crash.

Found live on 2026-10-08 while testing the WXR update flow: the second import
of the same file 500'd with a UNIQUE violation, twice over.

* The category and tag loops treated `skip_existing=false` as "insert a new
  row even though one with this slug exists" — an instant
  `uq_blog_categories_slug` / `uq_blog_tags_slug` violation. `skip_existing`
  decides whether POSTS are skipped or updated; the taxonomy slug is the
  identity and must be reused either way.
* The tag-attach loop added `blog_post_tags` rows on top of the existing set,
  hitting `UNIQUE(post_id, tag_id)` on the post update path.

So "import again to update the post" — the flow the import button's own
`skip_existing` query parameter exists for — had never worked.

These drive the real service against the local test database, cleaning up
their rows before and after; each test opens its own session inside its own
event loop so no loop crosses a test boundary.
"""

from __future__ import annotations

import uuid

AUTHOR_ID = uuid.UUID("5ae8aeaa-715e-459b-995a-0a91fdb1deff")


def _doc(*, title: str, slug: str, cat: str, tag: str) -> dict:
    return {
        "format": "wxr",
        "version": "1.1",
        "categories": [{"name": "دسته تست", "slug": cat}],
        "tags": [{"name": "برچسب تست", "slug": tag}],
        "posts": [
            {
                "title": title,
                "slug": slug,
                "content": "<p>متن</p>",
                "excerpt": None,
                "status": "draft",
                "published_at": None,
                "category_slugs": [cat],
                "tag_slugs": [tag],
                "author_name": None,
                "wxr_post_id": "91001",
                "meta": {},
                "seo": None,
                "cover_image_url": None,
            }
        ],
        "comments": [],
    }


async def _cleanup(db, slug: str, cat: str, tag: str) -> None:
    from sqlalchemy import delete

    from app.modules.blog.domain.models import BlogCategory, BlogPost, BlogTag

    await db.execute(delete(BlogPost).where(BlogPost.slug == slug))
    await db.execute(delete(BlogCategory).where(BlogCategory.slug == cat))
    await db.execute(delete(BlogTag).where(BlogTag.slug == tag))
    await db.commit()


async def _dispose_engine() -> None:
    """Return the shared engine's connections to the pool before the loop dies.

    pytest-asyncio gives every test its own event loop; the app's engine is
    module-global, so a connection pooled during test one is attached to a
    loop that is closed by test two — the second test then dies with
    "Event loop is closed" inside asyncpg's cancellation. Disposing the pool
    at each test's end releases the connections while their loop is still
    alive.
    """
    from app.core.database.session import engine

    await engine.dispose()


async def test_second_import_with_update_does_not_raise():
    """The exact 500: import twice with `skip_existing=False`.

    Negative test: revert the `if existing: continue` in the category/tag
    loops to the old `if skip_existing: continue` and this raises
    IntegrityError — reproduced live before the fix.
    """
    from sqlalchemy import func, select

    from app.core.database.session import async_session_factory
    from app.modules.blog.application.transfer_service import BlogTransferService
    from app.modules.blog.domain.models import BlogCategory, BlogPost, BlogTag

    slug, cat, tag = "pytest-reimport-post", "pytest-reimport-cat", "pytest-reimport-tag"
    async with async_session_factory() as db:
        await _cleanup(db, slug, cat, tag)
        try:
            first = await BlogTransferService.import_json(
                db, _doc(title="نسخه یک", slug=slug, cat=cat, tag=tag),
                author_id=AUTHOR_ID, skip_existing=True,
            )
            assert first["posts"] == 1
            assert first["categories"] == 1 and first["tags"] == 1

            # Update pass: same slugs, new title. Must not raise.
            second = await BlogTransferService.import_json(
                db, _doc(title="نسخه دو", slug=slug, cat=cat, tag=tag),
                author_id=AUTHOR_ID, skip_existing=False,
            )
            # No new taxonomy rows: the slug is the identity.
            assert second["categories"] == 0 and second["tags"] == 0
            assert second["skipped"] == 0  # updated, not skipped

            title = (
                await db.execute(select(BlogPost.title).where(BlogPost.slug == slug))
            ).scalar_one()
            assert title == "نسخه دو"
            cat_count = (
                await db.execute(
                    select(func.count())
                    .select_from(BlogCategory)
                    .where(BlogCategory.slug == cat)
                )
            ).scalar_one()
            tag_count = (
                await db.execute(
                    select(func.count()).select_from(BlogTag).where(BlogTag.slug == tag)
                )
            ).scalar_one()
            assert cat_count == 1 and tag_count == 1
        finally:
            await _cleanup(db, slug, cat, tag)
            await _dispose_engine()


async def test_tag_rows_are_replaced_not_stacked():
    """A re-import must leave exactly one tag link, not raise on the unique.

    Negative test: remove the `delete(BlogPostTag)` in the update branch and
    the second import raises UNIQUE(post_id, tag_id).
    """
    from sqlalchemy import func, select

    from app.core.database.session import async_session_factory
    from app.modules.blog.application.transfer_service import BlogTransferService
    from app.modules.blog.domain.models import BlogPost, BlogPostTag

    slug, cat, tag = "pytest-tagstack-post", "pytest-tagstack-cat", "pytest-tagstack-tag"
    async with async_session_factory() as db:
        await _cleanup(db, slug, cat, tag)
        try:
            await BlogTransferService.import_json(
                db, _doc(title="v1", slug=slug, cat=cat, tag=tag),
                author_id=AUTHOR_ID, skip_existing=True,
            )
            await BlogTransferService.import_json(
                db, _doc(title="v2", slug=slug, cat=cat, tag=tag),
                author_id=AUTHOR_ID, skip_existing=False,
            )
            post_id = (
                await db.execute(select(BlogPost.id).where(BlogPost.slug == slug))
            ).scalar_one()
            link_count = (
                await db.execute(
                    select(func.count())
                    .select_from(BlogPostTag)
                    .where(BlogPostTag.post_id == post_id)
                )
            ).scalar_one()
            assert link_count == 1
        finally:
            await _cleanup(db, slug, cat, tag)
            await _dispose_engine()
