"""WordPress WXR → the same shape `BlogTransferService.import_json` accepts.

WXR is the XML WordPress writes under Tools → Export, and it is the only format
a WordPress site can hand you. Without a parser, migrating from WordPress means
asking somebody to convert the file by hand — which is why the transfer service
documented this as an open gap rather than a missing feature.

Decisions, each of which a naive parser gets wrong in a way that only shows up
on a real export:

* **Namespaces are matched by suffix, not by prefix.** WordPress writes
  `wp:post_type` with the `wp` prefix bound to
  `http://wordpress.org/export/1.2/`, but the version in that URI changed
  between 1.0 and 1.2 and third-party exporters emit either. Matching on the
  literal `{uri}local` string breaks on the file that uses the other one, and
  the failure is "no posts found" rather than an error.
* **CDATA and entities both appear.** `content:encoded` is CDATA in WordPress's
  own output and escaped text in some others; `ElementTree` handles both, but
  only if the text is read with `itertext()` rather than `.text`, which stops at
  the first child element and silently truncates an entry containing markup.
* **A draft is not published content.** Every post in the file carries a
  `<wp:status>`; importing them all as published turns an author's unpublished
  drafts into live pages. Statuses map to this schema's own, and anything
  unrecognised becomes a draft rather than being guessed at.
* **`content:encoded` and `excerpt:encoded` share a local name.** Both elements
  end in `encoded`; the excerpt's namespace URI contains `excerpt` and the
  content's does not. Matching on the local name alone makes the excerpt read
  back as empty forever, which is how this parser shipped once already.
* **Pages are content too.** A store migration carries pages (about, contact,
  terms) as `post_type=page`, and their parent link is a WordPress id that only
  means something inside the file — it is resolved to the parent's slug here,
  because a slug is what survives into the importing install.

The output is deliberately the *same dict* `import_json` already reads (plus a
`pages` list the CMS import reads), so the import path stays one
implementation rather than two that drift.
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from html import escape as _escape_html
from typing import Any

from defusedxml.common import DefusedXmlException

# The parse call goes through defusedxml: a WXR file is untrusted input (an
# operator uploads whatever their old host handed them), and a billion-laughs
# entity expansion would otherwise OOM the API. The Element type and
# ParseError stay stdlib — defusedxml's are the same objects.
from defusedxml.ElementTree import fromstring as _safe_fromstring

logger = logging.getLogger(__name__)

#: WordPress status → this schema's. `private` and `inherit` are not statuses
#: a post can hold here; `private` becomes a draft because publishing it would
#: expose content the author deliberately hid, and `inherit` is an attachment
#: revision that is not a post at all. The same mapping serves pages: their
#: status vocabulary (draft/pending_review/published/archived) is identical.
_STATUS_MAP = {
    "publish": "published",
    "draft": "draft",
    "pending": "pending_review",
    "future": "draft",       # a scheduled post; the date is imported with it
    "private": "draft",
    "trash": "archived",
}

#: `wp:post_type` values that are content. An attachment, a revision, a nav
#: menu item and a custom CSS entry all appear in the file and none is content.
_CONTENT_TYPES = {"post", "page"}

#: The comment statuses WordPress writes. `0` is unapproved, `1` approved.
_COMMENT_STATUS_MAP = {
    "1": "approved",
    "0": "pending",
    "spam": "spam",
    "trash": "trash",
}

#: WXR files carry a whole site's content, so the cap is far above the feed
#: parser's 5MB — but not unbounded: `ET.fromstring` holds the whole document
#: in memory, and a 500MB "export" is a mistake or an attack either way.
MAX_WXR_BYTES = 50 * 1024 * 1024


def _local(tag: str) -> str:
    """`{http://wordpress.org/export/1.2/}status` → `status`.

    The namespace URI is dropped rather than matched: it carries the WXR
    version, and a file exported by 1.1 or by a plugin using its own prefix
    would otherwise find nothing.
    """
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _namespace(tag: str) -> str:
    return tag.split("}", 1)[0].lower() if "}" in tag else ""


def _text(element: ET.Element | None) -> str:
    """All the text inside an element, including inside child markup.

    `.text` alone stops at the first child, so `<content:encoded>` holding an
    `<img>` would come back truncated at the image and the rest of the post
    would be silently lost.
    """
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _find(parent: ET.Element, *names: str) -> ET.Element | None:
    """The first child whose local name matches, whatever its namespace."""
    wanted = set(names)
    for child in parent:
        if _local(child.tag) in wanted:
            return child
    return None


def _findall(parent: ET.Element, *names: str) -> list[ET.Element]:
    wanted = set(names)
    return [child for child in parent if _local(child.tag) in wanted]


def _child_text(parent: ET.Element, *names: str) -> str:
    return _text(_find(parent, *names))


def _decode_slug(raw: str) -> str:
    """Percent-decode a WXR `post_name`.

    WordPress stores the slug of a non-ASCII title percent-encoded
    (`%db%8c%d9%88%d8%b3%db%8c-...` for a Persian title), and importing it
    verbatim produces a page URL nobody can read or type. Decoding restores
    the Persian slug the admin UI shows; an ASCII slug is unchanged by it.
    A malformed escape sequence is left as-is rather than raising — the
    import must not fail on one odd slug.
    """
    if "%" not in raw:
        return raw
    try:
        from urllib.parse import unquote

        return unquote(raw, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return raw


#: Meta keys the common SEO plugins use for the search-result title.
#: Rank Math (what the arouxshop export carries) first, then Yoast's
#: spelling of the same idea. Ordered: the first non-empty wins.
_SEO_TITLE_KEYS = ("rank_math_title", "_yoast_wpseo_title")
_SEO_DESC_KEYS = ("rank_math_description", "_yoast_wpseo_metadesc")
_SEO_CANONICAL_KEYS = ("rank_math_canonical_url", "_yoast_wpseo_canonical")
#: The focus keyword — the keyphrase the article targets. Rank Math and Yoast
#: both write it; the arouxshop export carries `پابجی موبایل, PUBG Mobile`.
#: It was parsed-and-dropped before, so an imported article arrived with no
#: keyword to score against.
_SEO_FOCUS_KEYWORD_KEYS = ("rank_math_focus_keyword", "_yoast_wpseo_focuskw")
_SEO_OG_TITLE_KEYS = ("rank_math_facebook_title", "_yoast_wpseo_opengraph-title")
_SEO_OG_DESC_KEYS = ("rank_math_facebook_description", "_yoast_wpseo_opengraph-description")
_SEO_OG_IMAGE_KEYS = ("rank_math_facebook_image", "_yoast_wpseo_opengraph-image")

#: Rank Math stores the schema graph it renders as a JSON string. It is
#: carried through so the imported post keeps the author's structured data;
#: a malformed value is dropped rather than failing the whole import.
_SEO_SCHEMA_KEYS = ("rank_math_schema_Article", "rank_math_schema_WebPage")


def _first_meta(postmeta: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = (postmeta.get(key) or "").strip()
        if value:
            return value
    return None


def _postmeta_image_url(postmeta: dict[str, str], attachments: dict[str, str]) -> str | None:
    """The featured image URL: `_thumbnail_id` resolved through attachments.

    WordPress stores the *id* of the attachment item, not a URL, so a parser
    that reads only the id has an integer that means nothing to the importing
    install. The pre-pass built the id → URL map; this resolves through it and
    falls back to an explicitly stored URL key some plugins write.
    """
    thumbnail_id = (postmeta.get("_thumbnail_id") or "").strip()
    if thumbnail_id and thumbnail_id in attachments:
        return attachments[thumbnail_id]
    for key in ("_thumbnail_url", "rank_math_facebook_image", "_yoast_wpseo_opengraph-image"):
        value = (postmeta.get(key) or "").strip()
        if value.startswith(("http://", "https://", "/")):
            return value
    return None


def _postmeta_seo(postmeta: dict[str, str]) -> dict[str, Any] | None:
    """SEO fields from Rank Math / Yoast meta keys, or None when absent.

    Returns only the keys that actually had a value: an all-empty dict would
    look like "the file carried SEO" to a consumer that checks for the key.
    """
    seo: dict[str, Any] = {}
    title = _first_meta(postmeta, _SEO_TITLE_KEYS)
    if title:
        seo["title"] = title
    description = _first_meta(postmeta, _SEO_DESC_KEYS)
    if description:
        seo["description"] = description
    canonical = _first_meta(postmeta, _SEO_CANONICAL_KEYS)
    if canonical:
        seo["canonical_url"] = canonical
    og_title = _first_meta(postmeta, _SEO_OG_TITLE_KEYS)
    if og_title:
        seo["og_title"] = og_title
    og_description = _first_meta(postmeta, _SEO_OG_DESC_KEYS)
    if og_description:
        seo["og_description"] = og_description
    og_image = _first_meta(postmeta, _SEO_OG_IMAGE_KEYS)
    if og_image:
        seo["og_image"] = og_image
    focus_keyword = _first_meta(postmeta, _SEO_FOCUS_KEYWORD_KEYS)
    if focus_keyword:
        seo["focus_keyword"] = focus_keyword
    for key in _SEO_SCHEMA_KEYS:
        raw = (postmeta.get(key) or "").strip()
        if raw:
            try:
                seo["schema_markup"] = json.loads(raw)
            except (ValueError, TypeError):
                # A schema blob this parser cannot read must not lose the
                # rest of the SEO fields or fail the import.
                logger.warning("wxr_seo_schema_unparsable key=%s", key)
            break
    return seo or None


#: Elementor widget types whose settings carry text we can render. Keys
#: within `settings` differ per widget; each is (type, title_key, text_key).
_ELEMENTOR_TEXT_WIDGETS = {
    "text-editor": ("text",),
    "heading": ("title",),
    "icon-list": (),  # list items live in a different shape; handled below
}


def _elementor_to_html(raw: str) -> str:
    """Rebuild article HTML from an Elementor `_elementor_data` blob.

    Elementor stores the page as a JSON tree of elements, each with a
    `widgetType` and a `settings` object; the rendered page a visitor sees is
    that tree walked in order. Importing the raw JSON would put a wall of
    braces into the post, and importing `content:encoded` alone loses the
    body entirely (for an Elementor site it is empty or a shortcode stub).
    So the tree is walked and the text-bearing widgets are emitted as HTML,
    in document order — headings as `<h2>`/`<h3>`, text editors as-is, and
    images as `<figure><img>` with their caption.

    Deliberately not rendered: styling, columns, backgrounds and everything
    else that is presentation. The storefront applies its own theme; the
    import's job is the content. A widget type this walker does not know is
    skipped rather than guessed at — but unknown *text* widgets are the
    failure mode that matters, so the list above is the ones Elementor sites
    actually use for prose.
    """
    try:
        tree = json.loads(raw)
    except (ValueError, TypeError):
        return ""
    if not isinstance(tree, list):
        return ""

    parts: list[str] = []

    def _text_of(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _image_url(value: Any) -> str:
        if isinstance(value, dict):
            url = value.get("url")
            return url if isinstance(url, str) else ""
        return value if isinstance(value, str) else ""

    def _image_block(settings: dict, *, key: str = "image") -> None:
        url = _image_url(settings.get(key))
        if not url:
            return
        caption = _text_of(settings.get("caption"))
        alt = _text_of(settings.get("alt")) or caption
        img = f'<img src="{_escape_html(url, quote=True)}" alt="{_escape_html(alt, quote=True)}" />'
        if caption:
            parts.append(f"<figure>{img}<figcaption>{caption}</figcaption></figure>")
        else:
            parts.append(f"<figure>{img}</figure>")

    def _link_block(settings: dict) -> str | None:
        """An `<a>` around inner content from a link-shaped settings object."""
        link = settings.get("link")
        if not isinstance(link, dict):
            return None
        url = link.get("url")
        if not isinstance(url, str) or not url:
            return None
        attrs = f'href="{_escape_html(url, quote=True)}"'
        if link.get("is_external"):
            attrs += ' target="_blank" rel="noopener"'
        if link.get("nofollow"):
            attrs += ' rel="nofollow"' if "rel=" not in attrs else ""
        return attrs

    def walk(elements: list[Any]) -> None:
        for element in elements:
            if not isinstance(element, dict):
                continue
            widget_type = element.get("widgetType")
            settings = element.get("settings") or {}
            if isinstance(settings, dict):
                if widget_type == "text-editor":
                    text = settings.get("text") or ""
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif widget_type == "heading":
                    title = _text_of(settings.get("title"))
                    if title:
                        # Elementor's heading widget carries its own level in
                        # `header_size`; h2 is the site's convention for
                        # in-article section headings.
                        level = settings.get("header_size") or "h2"
                        tag = level if level in ("h1", "h2", "h3", "h4", "h5", "h6") else "h2"
                        parts.append(f"<{tag}>{title}</{tag}>")
                elif widget_type == "image":
                    _image_block(settings)
                elif widget_type in ("video", "youtube"):
                    # The video widget stores either an uploaded file
                    # (`hosted_url`) or a provider URL (`youtube_url`). Both
                    # render as a real <video> or an allowlisted iframe; a
                    # provider URL the embed policy does not know is emitted
                    # as a plain link so the content is not lost.
                    hosted = _text_of(settings.get("hosted_url"))
                    remote = _text_of(settings.get("youtube_url"))
                    if hosted:
                        poster = _text_of(settings.get("poster_url"))
                        poster_attr = f' poster="{_escape_html(poster, quote=True)}"' if poster else ""
                        parts.append(
                            f'<video src="{_escape_html(hosted, quote=True)}" controls{poster_attr}></video>'
                        )
                    elif remote:
                        safe = _escape_html(remote, quote=True)
                        parts.append(
                            f'<figure><a href="{safe}" target="_blank" rel="noopener">{safe}</a></figure>'
                        )
                elif widget_type == "icon-list":
                    items = settings.get("icon_list")
                    if isinstance(items, list):
                        lis = []
                        for entry in items:
                            if isinstance(entry, dict):
                                t = _text_of(entry.get("text"))
                                if t:
                                    lis.append(f"<li>{t}</li>")
                        if lis:
                            parts.append("<ul>" + "".join(lis) + "</ul>")
                elif widget_type == "button":
                    label = _text_of(settings.get("text"))
                    attrs = _link_block(settings)
                    if label and attrs:
                        parts.append(f'<p><a {attrs}>{label}</a></p>')
                    elif label:
                        parts.append(f"<p>{label}</p>")
                elif widget_type == "divider":
                    parts.append("<hr />")
                elif widget_type == "spacer":
                    # Pure layout; dropped on purpose (the storefront themes
                    # its own rhythm). Named here so the skip is deliberate.
                    pass
                elif widget_type in ("icon-box", "icon", "image-box"):
                    title = _text_of(settings.get("title_text")) or _text_of(settings.get("title"))
                    desc = _text_of(settings.get("description_text")) or _text_of(
                        settings.get("description")
                    )
                    if title:
                        parts.append(f"<h3>{title}</h3>")
                    if desc:
                        parts.append(f"<p>{desc}</p>")
                elif widget_type == "star-rating":
                    rating = settings.get("rating")
                    scale = settings.get("rating_scale") or 5
                    if isinstance(rating, (int, float)):
                        parts.append(
                            f'<p>امتیاز: {_escape_html(str(rating))} از {_escape_html(str(scale))}</p>'
                        )
                elif widget_type == "counter":
                    end = settings.get("ending_number")
                    suffix = _text_of(settings.get("suffix"))
                    label = _text_of(settings.get("title")) or _text_of(
                        settings.get("counter_title")
                    )
                    if end not in (None, ""):
                        line = f"{_escape_html(str(end))}{_escape_html(suffix)}"
                        parts.append(f"<p>{f'{label}: ' if label else ''}{line}</p>")
                elif widget_type == "progress":
                    title = _text_of(settings.get("title")) or _text_of(
                        settings.get("progress_title")
                    )
                    percent = settings.get("percent")
                    if title or percent is not None:
                        parts.append(
                            f"<p>{_escape_html(title)}"
                            + (f" — {_escape_html(str(percent))}٪" if percent is not None else "")
                            + "</p>"
                        )
                elif widget_type == "testimonial":
                    content = _text_of(settings.get("testimonial_content"))
                    name = _text_of(settings.get("testimonial_name"))
                    job = _text_of(settings.get("testimonial_job"))
                    if content:
                        cite = " — ".join(x for x in (name, job) if x)
                        blockquote = f"<blockquote><p>{content}</p>"
                        if cite:
                            blockquote += f"<cite>{_escape_html(cite)}</cite>"
                        blockquote += "</blockquote>"
                        parts.append(blockquote)
                elif widget_type == "accordion":
                    items = settings.get("tabs")
                    if isinstance(items, list):
                        for entry in items:
                            if not isinstance(entry, dict):
                                continue
                            tab_title = _text_of(entry.get("tab_title"))
                            tab_content = _text_of(entry.get("tab_content"))
                            if tab_title:
                                parts.append(f"<h3>{tab_title}</h3>")
                            if tab_content:
                                parts.append(f"<p>{tab_content}</p>")
                elif widget_type == "tabs":
                    items = settings.get("tabs")
                    if isinstance(items, list):
                        for entry in items:
                            if not isinstance(entry, dict):
                                continue
                            tab_title = _text_of(entry.get("tab_title"))
                            tab_content = _text_of(entry.get("tab_content"))
                            if tab_title:
                                parts.append(f"<h3>{tab_title}</h3>")
                            if tab_content:
                                parts.append(f"<p>{tab_content}</p>")
                elif widget_type == "toggle":
                    items = settings.get("tabs")
                    if isinstance(items, list):
                        for entry in items:
                            if not isinstance(entry, dict):
                                continue
                            tab_title = _text_of(entry.get("tab_title"))
                            tab_content = _text_of(entry.get("tab_content"))
                            if tab_title:
                                parts.append(f"<h3>{tab_title}</h3>")
                            if tab_content:
                                parts.append(f"<p>{tab_content}</p>")
                elif widget_type == "gallery":
                    gallery = settings.get("wp_gallery")
                    if isinstance(gallery, list):
                        for entry in gallery:
                            if isinstance(entry, dict):
                                _image_block(entry, key="url")
                elif widget_type == "html":
                    # A raw-HTML widget is the author's own markup; it goes
                    # through the same server-side sanitizer every body does
                    # (the import route sanitizes on write), so emitting it
                    # here is no more trust than the editor gets.
                    raw_html = settings.get("html") or ""
                    if isinstance(raw_html, str) and raw_html.strip():
                        parts.append(raw_html.strip())
            # Containers: `elements` is the child list on section/column/
            # container nodes. Walked after the widget's own output so the
            # document order of the rendered page is preserved.
            children = element.get("elements")
            if isinstance(children, list):
                walk(children)

    walk(tree)
    return "\n".join(parts)


def _encoded_text(item: ET.Element, *, want_excerpt: bool) -> str:
    """The `encoded` element that is *content* or *excerpt*.

    `content:encoded` and `excerpt:encoded` both have the local name `encoded`,
    so a lookup by local name alone returns whichever came first — which made
    the excerpt read as empty (and would silently swap content and excerpt if
    an exporter wrote them in the other order). The two are told apart by their
    namespace URI: only the excerpt's mentions `excerpt`.
    """
    for child in item:
        if _local(child.tag) != "encoded":
            continue
        is_excerpt = "excerpt" in _namespace(child.tag)
        if is_excerpt == want_excerpt:
            return _text(child)
    return ""


def parse_wxr(xml_bytes: bytes | str) -> dict[str, Any]:
    """Parse a WXR file into the dict `import_json` accepts.

    Raises ValueError on a file that is not XML at all, because "empty import"
    and "the file was a PDF" are different answers and only one of them should
    look like success.
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")

    if len(xml_bytes) > MAX_WXR_BYTES:
        raise ValueError(
            f"حجم فایل WXR بیش از حد مجاز است "
            f"({len(xml_bytes) // (1024 * 1024)} مگابایت؛ سقف "
            f"{MAX_WXR_BYTES // (1024 * 1024)} مگابایت)"
        )

    try:
        root = _safe_fromstring(xml_bytes)
    except DefusedXmlException as exc:
        # A DOCTYPE with entity expansion (billion laughs) or an external
        # entity: rejected by defusedxml before any memory is committed. The
        # message is an operator-facing "this file is not safe to parse".
        raise ValueError("این فایل XML شامل ساختار غیرمجاز (DOCTYPE/entity) است") from exc
    except ET.ParseError as exc:
        raise ValueError(f"فایل XML معتبر نیست: {exc}") from exc

    channel = _find(root, "channel")
    if channel is None:
        raise ValueError("فایل WXR ساختار channel ندارد")

    categories: dict[str, dict[str, Any]] = {}
    tags: dict[str, dict[str, Any]] = {}
    posts: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    # Comments arrive inside their post's item, and the parent link between
    # them is by WordPress id — which is not this schema's id. They are
    # collected flat and threaded after every post is known. Each comment
    # carries its post's slug so the import can re-attach it.
    comments: list[dict[str, Any]] = []
    author_slugs: dict[str, str] = {}

    # Authors: WXR carries `dc:creator` as a login, and `wp:author` blocks map
    # login → display name. Only the display name is usable here. Collected
    # once, before the item loop, because the blocks live on the channel.
    for author in _findall(channel, "author"):
        login = _child_text(author, "author_login")
        display = _child_text(author, "author_display_name")
        if login and display:
            author_slugs[login] = display

    # Attachments, before the content loop: `_thumbnail_id` is a WordPress id
    # that only means something inside this file, and the URL for it lives in
    # the attachment item — which WordPress writes *after* the post that
    # references it. One pre-pass maps id → URL so the featured image can be
    # resolved in the main loop.
    attachments: dict[str, str] = {}
    for item in _findall(channel, "item"):
        if _child_text(item, "post_type") == "attachment":
            attachment_id = _child_text(item, "post_id")
            url = _child_text(item, "attachment_url")
            if attachment_id and url:
                attachments[attachment_id] = url

    #: Comments attached to pages are counted but not imported: page comments
    #: are a separate moderation surface here and silently losing them would
    #: read as "the file had none".
    comments_on_pages_skipped = 0

    for item in _findall(channel, "item"):
        post_type = _child_text(item, "post_type") or "post"

        # The item's OWN taxonomy assignments. The old parser reported every
        # category seen so far globally, which linked every post to every
        # category — and the importer could not read the key at all.
        item_category_slugs: list[str] = []
        item_tag_slugs: list[str] = []
        for cat in _findall(item, "category"):
            # `nicename` is percent-encoded for non-ASCII names, exactly like
            # `post_name` — and `_decode_slug` exists for that reason. It was
            # only applied to posts, so three Persian categories imported as
            # `%d8%aa%d9%84...` slugs; the sitemap advertised those URLs and
            # every one answered 404 (found in the 2026-10-10 SEO audit).
            slug = _decode_slug(cat.get("nicename") or "")
            name = (cat.text or "").strip()
            if not name:
                continue
            domain = cat.get("domain") or "category"
            key = slug or name
            if domain == "post_tag":
                item_tag_slugs.append(key)
                if key not in tags:
                    tags[key] = {"name": name, "slug": slug or None}
            else:
                item_category_slugs.append(key)
                if key not in categories:
                    categories[key] = {"name": name, "slug": slug or None}

        if post_type not in _CONTENT_TYPES:
            continue

        title = _child_text(item, "title")
        slug = _decode_slug(_child_text(item, "post_name"))
        content = _encoded_text(item, want_excerpt=False) or _child_text(
            item, "description"
        )
        excerpt = _encoded_text(item, want_excerpt=True)
        status_raw = (_child_text(item, "status") or "draft").lower()
        status = _STATUS_MAP.get(status_raw, "draft")
        date_gmt = _child_text(item, "post_date_gmt") or _child_text(item, "post_date")
        creator = _child_text(item, "creator")
        wp_post_id = _child_text(item, "post_id")

        # `wp:postmeta` rows. The interesting keys are the ones WordPress
        # itself and the common SEO plugins write: `_thumbnail_id` (the
        # featured image — without it every imported post lost its cover),
        # `_elementor_data` (page-builder bodies — for an Elementor site
        # `content:encoded` is nearly empty and the whole article lives
        # here), and the Rank Math / Yoast SEO columns. They are collected
        # as a flat dict; the extraction decisions happen below so this
        # block stays a pure read.
        postmeta: dict[str, str] = {}
        for meta in _findall(item, "postmeta"):
            key = _child_text(meta, "meta_key")
            if key:
                postmeta[key] = _child_text(meta, "meta_value")

        # Elementor bodies: when `_elementor_data` exists and carries text,
        # it is the article. `content:encoded` for an Elementor post holds
        # only the shortcode `[vc_row]`-style noise (or nothing), so keeping
        # it would import an empty post. The rendered HTML is rebuilt from
        # the builder tree below.
        if postmeta.get("_elementor_data"):
            elementor_html = _elementor_to_html(postmeta["_elementor_data"])
            if elementor_html:
                content = elementor_html

        if not title and not content:
            continue

        if post_type == "page":
            pages.append({
                "title": title or "بدون عنوان",
                "slug": slug or None,
                "content": content,
                "excerpt": excerpt or None,
                "status": status,
                "published_at": _iso_or_none(date_gmt),
                # The parent is a WordPress id that means nothing outside the
                # file; it is resolved to a slug after every page is known.
                "parent_wxr_id": _child_text(item, "post_parent") or None,
                "wxr_post_id": wp_post_id or None,
                "cover_image_url": _postmeta_image_url(postmeta, attachments),
                "seo": _postmeta_seo(postmeta),
            })
            # Page comments exist in WXR; they are not imported (see the
            # counter's comment) but they must not look like "no comments".
            comments_on_pages_skipped += len(_findall(item, "comment"))
            continue

        posts.append({
            "title": title or "بدون عنوان",
            "slug": slug or None,
            "content": content,
            "excerpt": excerpt or None,
            "status": status,
            "published_at": _iso_or_none(date_gmt),
            "category_slugs": item_category_slugs,
            "tag_slugs": item_tag_slugs,
            # The slug is what this schema keys on; the display name is a
            # courtesy for an author who does not exist here yet.
            "author_name": author_slugs.get(creator, creator) or None,
            "wxr_post_id": wp_post_id or None,
            # The featured image, resolved from `_thumbnail_id` through the
            # attachment items of the same file. Without this the cover the
            # author chose was silently dropped on every import.
            "cover_image_url": _postmeta_image_url(postmeta, attachments),
            # Rank Math / Yoast write their title and description into
            # `rank_math_*` / `_yoast_wpseo_*` meta keys. They are the SEO
            # the author actually tuned, so an import that ignored them
            # replaced hand-written titles with generated ones.
            "seo": _postmeta_seo(postmeta),
            "meta": {
                # `comment_status` is the per-post switch the post dialog
                # exposes. Reading it from the file is what makes an imported
                # post behave like the original.
                "allow_comments": (_child_text(item, "comment_status") or "open") == "open",
            },
        })

        for comment in _findall(item, "comment"):
            if (_child_text(comment, "comment_type") or "comment") != "comment":
                # pingback and trackback are not comments a person wrote.
                continue
            comments.append({
                # The WXR `comment_author_email` field is deliberately not
                # parsed: the importer's column was dropped on 2026-10-07 with
                # the rest of the email feature, so there is nowhere to put it.
                "author_name": _child_text(comment, "comment_author"),
                "author_url": _child_text(comment, "comment_author_url") or None,
                "author_ip": _child_text(comment, "comment_author_IP") or None,
                "date_gmt": _iso_or_none(
                    _child_text(comment, "comment_date_gmt")
                    or _child_text(comment, "comment_date")
                ),
                "content": _child_text(comment, "comment_content"),
                "status": _COMMENT_STATUS_MAP.get(
                    (_child_text(comment, "comment_approved") or "0").lower(),
                    "pending",
                ),
                # WordPress ids, resolvable only inside this file.
                "wxr_comment_id": _child_text(comment, "comment_id") or None,
                "parent": _child_text(comment, "comment_parent") or "0",
                "comment_post_id": _child_text(comment, "comment_post_id"),
                # The enclosing post's slug: the one identifier that survives
                # into the importing install.
                "post_slug": slug or None,
            })

    # Second pass: page parents, by WordPress id → slug. A parent that is not
    # a page in this file (or has no slug) is left unresolved — the page
    # imports as a root rather than being dropped.
    page_id_to_slug = {
        p["wxr_post_id"]: p["slug"]
        for p in pages
        if p.get("wxr_post_id") and p.get("slug")
    }
    for page in pages:
        parent_id = page.pop("parent_wxr_id", None)
        if parent_id and parent_id != "0":
            page["parent_slug"] = page_id_to_slug.get(parent_id)
        else:
            page["parent_slug"] = None

    result = {
        "format": "wxr",
        # 1.1: pages, per-item taxonomy links and comment post-slug linkage.
        # 1.2: the channel's author blocks, so the importer can adopt the
        # original author's display name instead of showing the phone-tail
        # fallback ("کاربر 0000") on every migrated article.
        "version": "1.2",
        "categories": list(categories.values()),
        "tags": list(tags.values()),
        "posts": posts,
        "pages": pages,
        "comments": comments,
        # Login → display name, in file order. `author_slugs` already has the
        # map; the list keeps the file's own order so "first author wins" is
        # deterministic.
        "authors": [
            {"login": login, "name": author_slugs[login]}
            for login in author_slugs
        ],
        "menus": [],
        "counts": {
            "categories": len(categories),
            "tags": len(tags),
            "posts": len(posts),
            "pages": len(pages),
            "comments": len(comments),
            "comments_on_pages_skipped": comments_on_pages_skipped,
            "menus": 0,
        },
    }
    # stdlib logging, not structlog: keyword arguments raise TypeError here
    # (`Logger._log() got an unexpected keyword argument`), and under a
    # configured server that turned every WXR import into a 500 — invisible in
    # bare unit tests, where INFO is disabled and the call is skipped.
    logger.info(
        "wxr_parsed posts=%d pages=%d comments=%d categories=%d",
        len(posts),
        len(pages),
        len(comments),
        len(categories),
    )
    return result


#: `2026-10-01 12:30:00` — WXR writes UTC without a zone marker, and
#: `fromisoformat` refuses the space in older Python versions.
_DATE_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})"
)


def _iso_or_none(value: str) -> str | None:
    """Normalise a WXR date to ISO-8601, or None when it is not a date.

    WXR writes `0000-00-00 00:00:00` for an unscheduled post, which is not a
    date any parser accepts — and importing it as one would either raise or,
    worse, land on year zero.
    """
    m = _DATE_RE.match((value or "").strip())
    if not m:
        return None
    year, month, day, hour, minute, second = m.groups()
    if year == "0000" or month == "00" or day == "00":
        return None
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}+00:00"
