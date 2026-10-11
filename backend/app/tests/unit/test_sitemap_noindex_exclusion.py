"""Tests: noindex resources must not appear in the sitemap.

A sitemap that advertises a noindexed URL contradicts itself — Search Console
reports "Submitted URL marked noindex" and crawlers discount the whole file.
The Advanced tab's robots_noindex column is the source; the exclusion is
tri-state-aware: only explicit True excludes (NULL and False are both
"indexable").
"""

from __future__ import annotations

import inspect

from app.modules.content.application import sitemap_service


def test_noindex_lookup_filters_on_explicit_true():
    """Only robots_noindex IS TRUE excludes — NULL/False stay indexable."""
    source = inspect.getsource(sitemap_service._noindex_resource_ids)
    assert "robots_noindex.is_(True)" in source, (
        "The exclusion must test IS TRUE: a NULL (no operator choice) or "
        "False (explicitly indexable) must not exclude the URL."
    )


def test_noindex_lookup_fails_open():
    """A lookup failure must not empty the sitemap."""
    source = inspect.getsource(sitemap_service._noindex_resource_ids)
    assert "except Exception" in source
    assert "return set()" in source


def test_products_collector_applies_noindex():
    source = inspect.getsource(sitemap_service._collect_products)
    assert "_collect_noindex_product_ids" in source
    assert "noindex_ids" in source


def test_collect_noindex_slugs_covers_both_kinds():
    source = inspect.getsource(sitemap_service.collect_noindex_slugs)
    assert "blog_posts" in source
    assert "products" in source


def test_sitemap_ts_filters_blog_and_products():
    """The storefront sitemap must consume the exclusion list for both kinds."""
    import pathlib

    sitemap_ts = pathlib.Path(__file__).resolve().parents[4] / "frontend" / "app" / "sitemap.ts"
    if not sitemap_ts.exists():
        return  # backend-only checkout
    source = sitemap_ts.read_text(encoding="utf-8")
    assert "fetchNoindexSlugs" in source
    assert "noindexBlog.has" in source
    assert "noindexProducts.has" in source
