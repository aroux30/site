"""WordPress WXR → the same shape `BlogTransferService.import_json` accepts.

WXR is the XML WordPress writes under Tools → Export, and it is the only format
a WordPress site can hand you. Without a parser, migrating from WordPress means
asking somebody to convert the file by hand — which is why the transfer service
documented this as an open gap rather than a missing feature.

Three decisions, each of which a naive parser gets wrong in a way that only
shows up on a real export:

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

The output is deliberately the *same dict* `import_json` already reads, so the
import path stays one implementation rather than two that drift.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)

#: WordPress status → this schema's. `private` and `inherit` are not statuses
#: a post can hold here; `private` becomes a draft because publishing it would
#: expose content the author deliberately hid, and `inherit` is an attachment
#: revision that is not a post at all.
_STATUS_MAP = {
    "publish": "published",
    "draft": "draft",
    "pending": "pending_review",
    "future": "draft",       # a scheduled post; the date is imported with it
    "private": "draft",
    "trash": "archived",
}

#: `wp:post_type` values that are content. An attachment, a revision, a nav
#: menu item and a custom CSS entry all appear in the file and none is a post.
_CONTENT_TYPES = {"post"}

#: The comment statuses WordPress writes. `0` is unapproved, `1` approved.
_COMMENT_STATUS_MAP = {
    "1": "approved",
    "0": "pending",
    "spam": "spam",
    "trash": "trash",
}


def _local(tag: str) -> str:
    """`{http://wordpress.org/export/1.2/}status` → `status`.

    The namespace URI is dropped rather than matched: it carries the WXR
    version, and a file exported by 1.1 or by a plugin using its own prefix
    would otherwise find nothing.
    """
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


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


def parse_wxr(xml_bytes: bytes | str) -> dict[str, Any]:
    """Parse a WXR file into the dict `import_json` accepts.

    Raises ValueError on a file that is not XML at all, because "empty import"
    and "the file was a PDF" are different answers and only one of them should
    look like success.
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"فایل XML معتبر نیست: {exc}") from exc

    channel = _find(root, "channel")
    if channel is None:
        raise ValueError("فایل WXR ساختار channel ندارد")

    categories: dict[str, dict[str, Any]] = {}
    tags: dict[str, dict[str, Any]] = {}
    posts: list[dict[str, Any]] = []
    # Comments arrive inside their post's item, and the parent link between
    # them is by WordPress id — which is not this schema's id. They are
    # collected flat and threaded after every post is known.
    comments: list[dict[str, Any]] = []
    author_slugs: dict[str, str] = {}

    for item in _findall(channel, "item"):
        post_type = _child_text(item, "post_type") or "post"

        # Authors: WXR carries `dc:creator` as a login, and `wp:author` blocks
        # map login → display name. Only the display name is usable here.
        for author in _findall(channel, "author"):
            login = _child_text(author, "author_login")
            display = _child_text(author, "author_display_name")
            if login and display:
                author_slugs[login] = display

        for cat in _findall(item, "category"):
            slug = cat.get("nicename") or cat.get("domain") or ""
            name = (cat.text or "").strip()
            if not name:
                continue
            domain = cat.get("domain") or "category"
            target = tags if domain == "post_tag" else categories
            key = slug or name
            if key not in target:
                target[key] = {"name": name, "slug": slug or None}

        if post_type not in _CONTENT_TYPES:
            continue

        title = _child_text(item, "title")
        slug = _child_text(item, "post_name")
        content = _child_text(item, "encoded")  # content:encoded
        excerpt = _child_text(item, "excerpt")  # excerpt:encoded
        status_raw = (_child_text(item, "status") or "draft").lower()
        status = _STATUS_MAP.get(status_raw, "draft")
        date_gmt = _child_text(item, "post_date_gmt") or _child_text(item, "post_date")
        creator = _child_text(item, "creator")
        wp_post_id = _child_text(item, "post_id")

        if not title and not content:
            continue

        posts.append({
            "title": title or "بدون عنوان",
            "slug": slug or None,
            "content": content,
            "excerpt": excerpt or None,
            "status": status,
            "published_at": _iso_or_none(date_gmt),
            "category_slugs": [k for k in categories],
            # The slug is what this schema keys on; the display name is a
            # courtesy for an author who does not exist here yet.
            "author_name": author_slugs.get(creator, creator) or None,
            "wxr_post_id": wp_post_id or None,
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
                "author": _child_text(comment, "comment_author_email"),
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
                "parent": _child_text(comment, "comment_parent") or "0",
                "comment_post_id": _child_text(comment, "comment_post_id"),
            })

    result = {
        "format": "wxr",
        "version": "1.0",
        "categories": list(categories.values()),
        "tags": list(tags.values()),
        "posts": posts,
        "comments": comments,
        "menus": [],
        "counts": {
            "categories": len(categories),
            "tags": len(tags),
            "posts": len(posts),
            "comments": len(comments),
            "menus": 0,
        },
    }
    logger.info(
        "wxr_parsed",
        posts=len(posts),
        comments=len(comments),
        categories=len(categories),
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
