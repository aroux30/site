"""Author archive: eager loads for `_post_to_response` (500 fix).

`AuthorService.get_archive` built its post query with no `.options(...)`,
but `BlogService._post_to_response` reads `post.category` and `pt.tag` for
every row. In async SQLAlchemy each unloaded relationship is a lazy load →
MissingGreenlet → the endpoint answered 500 for every author with a tagged
post (found live 2026-10-09 with a full traceback by the monitoring
session).

Negative test: remove the `.options(...)` block and this test fails — the
predicate is "the query source contains the two selectinload calls", which
is exactly what the fix added.
"""

from __future__ import annotations

import inspect


def test_archive_query_eager_loads_what_the_mapper_reads():
    from app.modules.blog.application import author_service

    src = inspect.getsource(author_service.AuthorService.get_archive)
    assert "selectinload(BlogPost.category)" in src
    assert "selectinload(BlogPost.post_tags)" in src
    # The nested tag load is the one that 500'd: `pt.tag` inside the loop.
    assert "selectinload(BlogPostTag.tag)" in src


async def test_real_author_archive_returns_200_data():
    """Live DB: an author WITH a published post must answer, not raise.

    The author is chosen by joining published posts — not "the first user
    with a slug". The first version picked the first slugged user, who had
    zero published posts, so the response loop never ran `_post_to_response`
    and the MissingGreenlet the test exists for could never fire: green with
    the bug present (caught in review). No qualifying author in the DB is a
    loud failure, not a silent pass.
    """
    from sqlalchemy import select

    from app.core.database.session import async_session_factory, engine
    from app.modules.blog.application.author_service import AuthorService
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.users.domain.models import User

    async with async_session_factory() as db:
        user = (
            await db.execute(
                select(User)
                .join(BlogPost, BlogPost.author_id == User.id)
                .where(
                    User.author_slug.isnot(None),
                    BlogPost.status == BlogPostStatus.PUBLISHED,
                    BlogPost.deleted_at.is_(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        assert user is not None, (
            "no author with a published post in the database — this test "
            "cannot exercise the MissingGreenlet path"
        )
        archive = await AuthorService(db).get_archive(
            slug=user.author_slug, page=1, page_size=10, public_only=True
        )
        # The loop actually ran: at least one post went through
        # `_post_to_response`, which is where the lazy load used to raise.
        assert archive is not None
        assert archive.posts.total >= 1, "the chosen author has no published posts"
    await engine.dispose()
