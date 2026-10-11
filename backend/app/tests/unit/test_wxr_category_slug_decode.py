"""F-01 (SEO audit 2026-10-10): WXR category slugs must be percent-decoded.

WordPress writes `nicename` percent-encoded for non-ASCII names, exactly like
`post_name`. `_decode_slug` existed for posts but was never applied to
categories/tags, so three Persian categories imported as `%d8%aa%d9%84...`
slugs — the sitemap advertised those URLs and every one answered 404.

Negative test: revert `slug = _decode_slug(...)` to `slug = cat.get("nicename")`
and the assertion below fails.
"""

from __future__ import annotations

from app.modules.blog.application.wxr_parser import parse_wxr

WXR = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<wp:wxr_version>1.2</wp:wxr_version>
<item>
  <title>تست</title>
  <content:encoded><![CDATA[<p>x</p>]]></content:encoded>
  <wp:post_name>test</wp:post_name>
  <wp:status>publish</wp:status>
  <wp:post_type>post</wp:post_type>
  <category domain="category" nicename="%d8%aa%d9%84%da%af%d8%b1%d8%a7%d9%85"><![CDATA[تلگرام]]></category>
  <category domain="post_tag" nicename="%d9%be%d8%a7%d8%a8%d8%ac%db%8c"><![CDATA[پابجی]]></category>
</item>
</channel></rss>"""


def test_category_slug_is_decoded():
    """A percent-encoded nicename becomes the Persian slug."""
    parsed = parse_wxr(WXR)
    slugs = [c["slug"] for c in parsed["categories"]]
    assert "تلگرام" in slugs, f"category slug not decoded: {slugs}"
    assert not any("%" in (s or "") for s in slugs), "no percent-encoded slug may survive"


def test_tag_slug_is_decoded():
    """The tag branch shares the same decode (same loop)."""
    parsed = parse_wxr(WXR)
    slugs = [t["slug"] for t in parsed["tags"]]
    assert "پابجی" in slugs, f"tag slug not decoded: {slugs}"
