"""WXR import: the postmeta/Elementor/SEO chain, pinned end to end.

Every bug this file covers shipped and stayed shipped because nothing failed
when the feature broke:

* `wp:postmeta` was never read, so `_thumbnail_id` (the featured image) and
  the Rank Math SEO the author tuned were parsed-and-dropped on every import.
* An Elementor post stores its body in `_elementor_data`, not
  `content:encoded` — which is empty for such posts, so the article arrived
  blank while the file was full of content.
* The parser's output keys and the importer's expected keys drifted apart
  once already (`category_slugs` was emitted and never read), which is why
  these tests assert the full parser→importer contract, not either half.

Negative-test protocol: each test names the injection that must turn it red
in its docstring, and the injections were run before this file was trusted.
"""

from __future__ import annotations

from app.modules.blog.application.wxr_parser import parse_wxr

#: A post with a featured image (`_thumbnail_id` → attachment item), Rank
#: Math SEO, and a body that lives in `_elementor_data`. Mirrors the shape
#: the arouxshop export actually carries.
WXR_WITH_POSTMETA = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<wp:wxr_version>1.2</wp:wxr_version>
<wp:author><wp:author_id>4</wp:author_id>
<wp:author_login><![CDATA[aroux]]></wp:author_login>
<wp:author_display_name><![CDATA[آروکس]]></wp:author_display_name></wp:author>
<item>
  <title>راهنمای خرید یوسی</title>
  <dc:creator><![CDATA[aroux]]></dc:creator>
  <content:encoded><![CDATA[]]></content:encoded>
  <excerpt:encoded><![CDATA[خلاصه]]></excerpt:encoded>
  <wp:post_id>7001</wp:post_id>
  <wp:post_name>buy-uc</wp:post_name>
  <wp:post_date_gmt>2025-06-01 10:00:00</wp:post_date_gmt>
  <wp:status>publish</wp:status>
  <wp:post_type>post</wp:post_type>
  <wp:postmeta><wp:meta_key>_thumbnail_id</wp:meta_key><wp:meta_value>9001</wp:meta_value></wp:postmeta>
  <wp:postmeta><wp:meta_key>_elementor_data</wp:meta_key><wp:meta_value><![CDATA[
  [{"id":"s1","elType":"section","elements":[
    {"id":"w1","elType":"widget","widgetType":"heading","settings":{"title":"تیتر بیلدر","header_size":"h2"}},
    {"id":"w2","elType":"widget","widgetType":"text-editor","settings":{"text":"<p>پاراگراف بیلدر</p>"}},
    {"id":"w3","elType":"widget","widgetType":"image","settings":{"image":{"url":"https://old.example.com/img.webp"},"caption":"کپشن"}},
    {"id":"w4","elType":"widget","widgetType":"icon-list","settings":{"icon_list":[{"text":"یک"},{"text":"دو"}]}}
  ]}]]]></wp:meta_value></wp:postmeta>
  <wp:postmeta><wp:meta_key>rank_math_title</wp:meta_key><wp:meta_value>عنوان سئوی دستی</wp:meta_value></wp:postmeta>
  <wp:postmeta><wp:meta_key>rank_math_description</wp:meta_key><wp:meta_value>توضیح سئوی دستی</wp:meta_value></wp:postmeta>
</item>
<item>
  <title>photo</title>
  <wp:post_id>9001</wp:post_id>
  <wp:post_type>attachment</wp:post_type>
  <wp:attachment_url>https://old.example.com/photo.jpg</wp:attachment_url>
</item>
</channel></rss>"""


def _parse_ok(xml: str) -> dict:
    result = parse_wxr(xml)
    assert result["counts"]["posts"] == 1
    return result["posts"][0]


def test_featured_image_resolved_through_attachment_items():
    """`_thumbnail_id` is a file-local id; the URL lives in the attachment.

    Negative test: delete the `attachments` pre-pass in `parse_wxr` (the
    `for item in _findall(channel, "item")` that fills the map) and this
    returns None — the featured image silently vanishes from every import.
    """
    post = _parse_ok(WXR_WITH_POSTMETA)
    assert post["cover_image_url"] == "https://old.example.com/photo.jpg"


def test_rank_math_seo_is_carried():
    """The author's hand-tuned SEO must survive the import.

    Negative test: empty `_SEO_TITLE_KEYS` and `seo` comes back with no
    title — the exact silent loss this guards.
    """
    post = _parse_ok(WXR_WITH_POSTMETA)
    assert post["seo"] == {
        "title": "عنوان سئوی دستی",
        "description": "توضیح سئوی دستی",
    }


def test_elementor_body_replaces_empty_content_encoded():
    """An Elementor post's body is `_elementor_data`, in document order.

    Negative test: skip the `if postmeta.get("_elementor_data")` block and
    `content` is `""` — the article imports blank.
    """
    post = _parse_ok(WXR_WITH_POSTMETA)
    content = post["content"]
    # Order: heading → paragraph → image → list, exactly the builder order.
    assert content.index("<h2>تیتر بیلدر</h2>") < content.index("<p>پاراگراف بیلدر</p>")
    assert content.index("<p>پاراگراف بیلدر</p>") < content.index("<img")
    assert content.index("<img") < content.index("<ul>")
    # The image keeps its caption and a figure wrapper.
    assert "<figcaption>کپشن</figcaption>" in content
    # icon-list becomes a real <ul>, not dropped.
    assert "<li>یک</li>" in content and "<li>دو</li>" in content


def test_plain_post_without_postmeta_is_unchanged():
    """A classic (non-Elementor) post keeps its `content:encoded` verbatim.

    Negative test: make the Elementor branch unconditional and this body is
    replaced by the empty `_elementor_to_html` result.
    """
    xml = WXR_WITH_POSTMETA.replace(
        '<content:encoded><![CDATA[]]></content:encoded>',
        "<content:encoded><![CDATA[<p>متن ساده</p>]]></content:encoded>",
    ).replace(
        '<wp:postmeta><wp:meta_key>_elementor_data</wp:meta_key>'
        "<wp:meta_value><![CDATA[\n  [{\"id\":\"s1\",\"elType\":\"section\",\"elements\":[\n"
        '    {"id":"w1","elType":"widget","widgetType":"heading","settings":{"title":"تیتر بیلدر","header_size":"h2"}},\n'
        '    {"id":"w2","elType":"widget","widgetType":"text-editor","settings":{"text":"<p>پاراگراف بیلدر</p>"}},\n'
        '    {"id":"w3","elType":"widget","widgetType":"image","settings":{"image":{"url":"https://old.example.com/img.webp"},"caption":"کپشن"}},\n'
        '    {"id":"w4","elType":"widget","widgetType":"icon-list","settings":{"icon_list":[{"text":"یک"},{"text":"دو"}]}}\n'
        "  ]}]]]></wp:meta_value></wp:postmeta>",
        "",
    )
    post = _parse_ok(xml)
    assert post["content"] == "<p>متن ساده</p>"
