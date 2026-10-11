"""The focus keyword survives storage, the API, and the WXR import.

Before 2026-10-09 the analyzer scored against a focus keyword and the value
had nowhere to live: no column, no schema field, no editor field. An
operator could analyze a keyword and then lose it. This pins the three
places the value now travels:

1. `seo_metadata.focus_keyword` column exists (migration `seokw1`).
2. The create/update/response schemas carry it.
3. The WXR parser reads `rank_math_focus_keyword` / `_yoast_wpseo_focuskw`
   and the importer's upsert writes it.
"""

from __future__ import annotations

import inspect

from app.modules.blog.application.wxr_parser import parse_wxr

WXR = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:wp="http://wordpress.org/export/1.2/" xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<item>
  <title>t</title>
  <content:encoded><![CDATA[<p>x</p>]]></content:encoded>
  <wp:post_name>t</wp:post_name>
  <wp:status>publish</wp:status>
  <wp:post_type>post</wp:post_type>
  <wp:postmeta><wp:meta_key>rank_math_focus_keyword</wp:meta_key><wp:meta_value>پابجی موبایل, PUBG Mobile</wp:meta_value></wp:postmeta>
</item>
</channel></rss>"""


def test_parser_reads_rank_math_focus_keyword():
    """Negative test: empty `_SEO_FOCUS_KEYWORD_KEYS` and `seo` has no
    focus_keyword — the parsed-and-dropped bug this closes."""
    post = parse_wxr(WXR)["posts"][0]
    assert post["seo"]["focus_keyword"] == "پابجی موبایل, PUBG Mobile"


def test_parser_reads_yoast_focus_keyword():
    xml = WXR.replace("rank_math_focus_keyword", "_yoast_wpseo_focuskw")
    post = parse_wxr(xml)["posts"][0]
    assert post["seo"]["focus_keyword"] == "پابجی موبایل, PUBG Mobile"


def test_importer_upsert_allows_focus_keyword():
    """Source check: the upsert's allowlist must include the key, or the
    parser's value is filtered out silently (the "parsed but not stored"
    failure mode)."""
    from app.modules.blog.application import transfer_service

    src = inspect.getsource(transfer_service._upsert_post_seo)
    assert '"focus_keyword"' in src


def test_seo_schemas_carry_focus_keyword():
    from app.modules.seo.schemas.seo import (
        SEOMetadataCreate,
        SEOMetadataResponse,
        SEOMetadataUpdate,
    )

    for schema in (SEOMetadataCreate, SEOMetadataUpdate, SEOMetadataResponse):
        assert "focus_keyword" in schema.model_fields, (
            f"{schema.__name__} must carry focus_keyword"
        )


def test_blog_seo_dict_returns_focus_keyword():
    """`_get_seo_dict` feeds the storefront and the editor; a value stored
    but never returned is lost on the next reopen."""
    from app.modules.blog.application.blog_service import BlogService

    src = inspect.getsource(BlogService._get_seo_dict)
    assert '"focus_keyword"' in src


def test_cms_page_schemas_carry_focus_keyword():
    from app.modules.content.schemas.content import (
        CmsPageCreateRequest,
        CmsPageResponse,
        CmsPageUpdateRequest,
    )

    for schema in (CmsPageCreateRequest, CmsPageUpdateRequest, CmsPageResponse):
        assert "focus_keyword" in schema.model_fields
