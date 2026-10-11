"""Tests for the RSS feed extras (Rank Math Pro parity).

Three additions to ``build_rss_xml``:

- ``before_content`` / ``after_content`` wrap every item body (Rank Math's
  rss_before_content / rss_after_content).
- ``featured_image`` emits the cover as ``<media:content>``; relative stored
  paths must be resolved against the site root or readers get a broken URL.
- The ``media:`` namespace declaration must be present — a media:content in a
  document without its namespace is invalid XML for many parsers.

Also pins the bug this wave fixed: ``generate_term_feed`` never called
``prepare_feed_posts``, so category/tag feeds published raw ``[block]`` tokens.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import app.modules.blog.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.blog.application.feed_service import build_rss_xml
from app.modules.blog.domain.models import BlogPost, BlogPostStatus


def _post(**overrides) -> BlogPost:
    defaults = dict(
        id=uuid.uuid4(),
        title="پست تست",
        slug="test-post",
        content="<p>محتوا</p>",
        excerpt="خلاصه",
        status=BlogPostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        cover_image_url=None,
    )
    defaults.update(overrides)
    return BlogPost(**defaults)


def test_media_namespace_always_declared():
    """media:content without the namespace is invalid; the declaration must
    exist even when no item carries an image."""
    xml = build_rss_xml([_post()])
    assert 'xmlns:media="http://search.yahoo.com/mrss/"' in xml


def test_featured_image_emitted_absolute():
    """A stored path is site-relative; the feed must advertise an absolute URL."""
    xml = build_rss_xml(
        [_post(cover_image_url="/uploads/media/cover.png")],
        base_url="https://shop.example",
    )
    assert '<media:content url="https://shop.example/uploads/media/cover.png" medium="image"/>' in xml


def test_featured_image_absolute_url_passed_through():
    xml = build_rss_xml(
        [_post(cover_image_url="https://cdn.example/img.png")],
        base_url="https://shop.example",
    )
    assert '<media:content url="https://cdn.example/img.png" medium="image"/>' in xml


def test_featured_image_disabled_omits_media():
    xml = build_rss_xml(
        [_post(cover_image_url="/uploads/media/cover.png")],
        featured_image=False,
    )
    assert "<media:content" not in xml


def test_no_cover_no_media_element():
    xml = build_rss_xml([_post(cover_image_url=None)])
    assert "<media:content" not in xml


def test_before_and_after_content_wrap_body():
    xml = build_rss_xml(
        [_post()],
        before_content="<p>امضای اپراتور</p>",
        after_content="<p>پایان</p>",
    )
    assert "<p>امضای اپراتور</p>" in xml
    assert "<p>پایان</p>" in xml
    # Order: before comes before the body, after follows it.
    assert xml.index("امضای اپراتور") < xml.index("محتوا") < xml.index("پایان")


def test_empty_extras_leave_feed_unchanged():
    """With no extras the item body must be exactly the prepared body."""
    xml = build_rss_xml([_post()])
    assert "<p>محتوا</p>" in xml


def test_generate_term_feed_prepares_bodies():
    """Regression: term feeds published raw [block] tokens because
    prepare_feed_posts was never called on that path."""
    import inspect

    from app.modules.blog.application import feed_service

    source = inspect.getsource(feed_service.generate_term_feed)
    assert "prepare_feed_posts" in source, (
        "generate_term_feed must prepare feed bodies — without it, category/tag "
        "feeds publish unresolved [block slug=...] tokens (the exact bug fixed "
        "for the main feed earlier)."
    )
