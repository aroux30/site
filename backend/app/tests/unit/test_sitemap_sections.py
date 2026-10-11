"""Tests for the sitemap section collectors (news, video, route shapes).

Three real bugs motivate these tests:

1. Author archives were advertised as ``/blog/authors/<slug>`` and date
   archives as ``/archive/<year>`` — neither path is served by any route, so
   every one of those sitemap entries was a 404 a crawler kept retrying. The
   real routes are ``/author/<slug>`` and ``/blog/archive/<year>[/<month>]``.
2. The news sitemap must only list posts published inside Google's 48-hour
   window; an older entry is a policy violation that can drop the file.
3. A video entry without a thumbnail is invalid for Google, so posts whose
   cover is missing must be skipped, not emitted broken.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

import app.modules.blog.domain.models  # noqa: F401
import app.modules.catalog.domain.models  # noqa: F401
import app.modules.content.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostFormat
from app.modules.content.application import sitemap_service


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)

    def all(self):
        return self._rows


class _DbStub:
    """Returns pre-baked rows; records the SQL text for shape assertions."""

    def __init__(self, rows):
        self.rows = rows
        self.queries: list[str] = []

    async def execute(self, stmt):
        self.queries.append(str(stmt))
        return _Result(self.rows)


def _post(**overrides) -> BlogPost:
    defaults = dict(
        id=uuid.uuid4(),
        title="تست پست",
        slug="test-post",
        content="محتوا",
        excerpt="خلاصه",
        status=BlogPostStatus.PUBLISHED,
        post_format=PostFormat.STANDARD,
        published_at=datetime.now(UTC) - timedelta(hours=1),
        cover_image_url=None,
    )
    defaults.update(overrides)
    return BlogPost(**defaults)


@pytest.mark.asyncio
async def test_news_collector_includes_fresh_published_post():
    db = _DbStub([_post()])
    rows = await sitemap_service._collect_news(db)
    assert len(rows) == 1
    assert rows[0].loc == "/blog/test-post"
    assert rows[0].title == "تست پست"
    # The query must carry a status filter and the 48-hour window, or a draft
    # or an old post would slip into the news file. The enum value is a bound
    # parameter (not inline text), so assert on the column filters instead.
    sql = db.queries[0]
    assert "blog_posts.status" in sql
    assert "blog_posts.published_at >=" in sql
    assert "blog_posts.deleted_at IS NULL" in sql


@pytest.mark.asyncio
async def test_video_collector_skips_post_without_cover():
    """A coverless video post must not reach the sitemap (invalid entry)."""
    db = _DbStub([_post(post_format=PostFormat.VIDEO, cover_image_url=None)])
    rows = await sitemap_service._collect_videos(db)
    assert rows == []


@pytest.mark.asyncio
async def test_video_collector_emits_full_entry_with_cover():
    db = _DbStub(
        [
            _post(
                post_format=PostFormat.VIDEO,
                cover_image_url="/uploads/media/cover.png",
                excerpt="توضیح ویدئو",
            )
        ]
    )
    rows = await sitemap_service._collect_videos(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.loc == "/blog/test-post"
    assert row.thumbnail_url == "/uploads/media/cover.png"
    # Description must be non-empty — an empty one invalidates the entry.
    assert row.description


@pytest.mark.asyncio
async def test_video_description_falls_back_to_title():
    db = _DbStub(
        [
            _post(
                post_format=PostFormat.VIDEO,
                cover_image_url="/uploads/media/cover.png",
                excerpt=None,
            )
        ]
    )
    rows = await sitemap_service._collect_videos(db)
    assert rows[0].description == "تست پست"


@pytest.mark.asyncio
async def test_author_archive_locs_use_the_real_route():
    """Regression: /blog/authors/<slug> was a 404; the route is /author/<slug>."""

    class _AuthorRow:
        def __init__(self, slug):
            self.author_slug = slug
            self._count = 1

    class _AuthorDb:
        async def execute(self, stmt):
            class _R:
                def all(self):
                    return [("author-x", 3)]

            return _R()

    rows = await sitemap_service._collect_authors(_AuthorDb())
    assert rows[0].loc == "/author/author-x"


@pytest.mark.asyncio
async def test_date_archive_locs_use_the_real_route():
    """Regression: /archive/<year> was a 404; the route is /blog/archive/..."""

    class _ArchiveDb:
        async def execute(self, stmt):
            class _R:
                def all(self):
                    return [(2025, 9), (2025, 10), (2026, 1)]

            return _R()

    rows = await sitemap_service._collect_date_archives(_ArchiveDb())
    locs = [r.loc for r in rows]
    assert locs == [
        "/blog/archive/2025",
        "/blog/archive/2025/9",
        "/blog/archive/2025/10",
        "/blog/archive/2026",
        "/blog/archive/2026/1",
    ]
    # Every loc must be a real route shape — no bare /archive/.
    assert all(loc.startswith("/blog/archive/") for loc in locs)


def test_news_window_is_google_compliant():
    """The window constant must stay at Google's 48-hour maximum."""
    assert sitemap_service.NEWS_WINDOW_HOURS == 48


def test_news_cap_within_google_limit():
    """Google rejects news sitemaps over 1,000 URLs."""
    assert sitemap_service.NEWS_MAX_URLS <= 1000
