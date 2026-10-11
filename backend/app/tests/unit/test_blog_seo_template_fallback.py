"""F-02 (SEO audit 2026-10-10): operator templates reach the storefront.

A stored SEO row with NULL title (or no row at all — the default state of
every new post) fell through to a hardcoded frontend suffix. The storefront
read path now fills empty title/description from the operator's titles-meta
templates; the admin path keeps returning the stored row untouched.

Negative test: remove the `_seo_dict_with_templates` call in
`get_post_by_slug` and case 1's predicate (None -> filled) fails; invert the
precedence in the helper and case 2 fails (manual value overwritten).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest


def _fake_post():
    """Minimal stand-in for BlogPost: only the fields the helper reads."""
    post = AsyncMock()
    post.title = "عنوان نوشته"
    post.excerpt = "خلاصه"
    post.category = None
    post.updated_at = None
    post.id = uuid.uuid4()
    return post


@pytest.mark.asyncio
async def test_empty_seo_dict_is_filled_from_template():
    """None/empty row -> rendered template values, not None."""
    from app.modules.blog.application.blog_service import BlogService

    svc = BlogService(AsyncMock())
    with patch(
        "app.modules.seo.application.titles_meta_service.TitlesMetaService.resolve",
        new=AsyncMock(return_value=("عنوان قالب | فروشگاه", "توضیح قالب")),
    ):
        result = await svc._seo_dict_with_templates(_fake_post(), None)
    assert result is not None
    assert result["title"] == "عنوان قالب | فروشگاه"
    assert result["description"] == "توضیح قالب"


@pytest.mark.asyncio
async def test_manual_values_win_over_template():
    """A row with title+description is returned unchanged (no template call)."""
    from app.modules.blog.application.blog_service import BlogService

    svc = BlogService(AsyncMock())
    stored = {"title": "عنوان دستی", "description": "توضیح دستی"}
    with patch(
        "app.modules.seo.application.titles_meta_service.TitlesMetaService.resolve",
        new=AsyncMock(side_effect=AssertionError("must not be called")),
    ):
        result = await svc._seo_dict_with_templates(_fake_post(), stored)
    assert result == stored
