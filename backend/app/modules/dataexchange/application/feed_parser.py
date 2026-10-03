"""RSS 2.0 and Atom → the same shape `BlogTransferService.import_json` accepts.

The same decision `wxr_parser.py` makes, for the same reason: one import path.
That service already reads `{"categories": [...], "tags": [...], "posts":
[...]}`, so a feed is turned into that dict rather than into a second format
with its own importer — two importers drift, and the drift shows up as content
that imports differently depending on which file it came from.

Only RSS and Atom, deliberately. Movable Type, Tumblr and Blogger are three more
parsers to keep current against feeds nobody exports any more, and the WordPress
path is already covered by WXR, which is what those three produce.

What each format actually gives, and what is dropped:

* **RSS 2.0** — `channel/category` is the feed's category list, not per-item
  taxonomy, so items are filed under the channel categories and per-item ones
  are ignored. `content:encoded` is preferred over `description` because the
  latter is plain text in every real feed, and importing a blog as stripped
  plain text loses every link and paragraph.
* **Atom** — `<entry>` not `<item>`, `<content type="html">` instead of
  `<description>`, and the author is `dc:creator` or `<author><name>`. Atom has
  no channel-level category at all, so Atom feeds land untagged.

Both are namespace-heavy and both get the prefix rebound between publishers, so
every lookup matches on the **local name**, never on a bound namespace. A parser
that matches `{http://www.w3.org/2005/Atom}title` finds nothing in an RSS file
and reports "no entries found" rather than an error — the failure reads like
empty content, not like a wrong parser.

Entries with no title are dropped rather than imported as untitled slugs: a
feed row whose title is a newline produces a slug of nothing, and the import
would collide with the next one.
"""

from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

#: Feeds are documents fetched from elsewhere; a 40MB XML file is either a
#: mistake or an attack, and `ET.fromstring` will hold all of it in memory.
MAX_FEED_BYTES = 5 * 1024 * 1024

#: Enough for a blog's back catalogue without letting a runaway feed spend the
#: import budget on entries that will be skipped as duplicates anyway.
MAX_ENTRIES = 2000


def _local(tag: Any) -> str:
    """The part of an XML tag after any namespace: ``{uri}title`` → ``title``.

    Both feeds below bind their prefixes to different URIs per publisher and
    sometimes not at all, and a lookup that includes the namespace matches
    nothing when the publisher's differs. That failure is silent, so it is
    removed here rather than handled at each call site.
    """
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].strip().lower()


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if _local(child.tag) == name]


def _child(node: ET.Element, name: str) -> ET.Element | None:
    for child in node:
        if _local(child.tag) == name:
            return child
    return None


def _text(node: ET.Element | None) -> str:
    """The element's full text, markup included.

    `itertext()` rather than `.text`: `.text` stops at the first child element,
    so an entry whose description is `<p>a <b>b</b> c</p>` yields only `"a "`
    and the rest of the sentence is silently dropped. The WXR parser hit this
    for the same reason.
    """
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _strip_tags(raw: str) -> str:
    """Flatten an HTML description to plain text for a summary.

    Feeds that carry no `content:encoded` put an HTML fragment in
    `<description>`, and importing that fragment verbatim would store escaped
    markup as visible text. `bleach` is the project's sanitiser, but a *summary*
    should not be markup at all, so this strips rather than cleans — a `<script>`
    body is text here, which is the point.
    """
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", without_tags).strip()


def _escape_attr(value: str) -> str:
    """Escape for an HTML attribute value.

    The link comes from a feed this store has never seen, and it is written
    into the post body as an anchor. Unescaped, a feed whose `<link>` is
    `x" onmouseover="…` closes the attribute and adds an event handler to every
    imported post — a stored XSS delivered by subscribing someone to a hostile
    feed. `html.escape` with `quote=True` covers `"`, `'` and `<`.
    """
    return html.escape(value, quote=True)


def _escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def _parse_date(raw: str) -> str | None:
    """An RFC 822 (RSS) or RFC 3339 (Atom) date as an ISO string.

    Returns None rather than guessing when neither parser fits: an unparsed
    date leaves the post undated, which is a visible gap, whereas a wrong date
    silently reorders the archive.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def parse_feed(xml_bytes: bytes | str) -> dict[str, Any]:
    """Parse an RSS 2.0 or Atom document into `import_json`'s dict.

    Raises ValueError when the document is not XML, or is XML but not a feed:
    "no entries in this feed" and "this file is a spreadsheet" are different
    answers and only one of them should look like a successful empty import.
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")

    if len(xml_bytes) > MAX_FEED_BYTES:
        raise ValueError("حجم فید بیش از حد مجاز است (۵ مگابایت)")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"فایل XML معتبر نیست: {exc}") from exc

    if _local(root.tag) not in ("rss", "feed"):
        raise ValueError("این فایل یک فید RSS یا Atom نیست")

    atom = _local(root.tag) == "feed"

    # RSS puts everything under <channel>; Atom keeps <entry> at the top level.
    channel = _child(root, "channel") if not atom else root
    if channel is None:
        raise ValueError("ساختار فید نامعتبر است: channel یافت نشد")

    categories: dict[str, dict[str, Any]] = {}
    tags: dict[str, dict[str, Any]] = {}
    posts: list[dict[str, Any]] = []

    if not atom:
        # RSS's channel-level <category> is the feed's own category list. It is
        # not per-item taxonomy, so it is recorded as the default for entries
        # rather than applied to any one of them.
        feed_categories = [
            (cat.get("term") or _text(cat)).strip()
            for cat in _children(channel, "category")
        ]
        feed_categories = [c for c in feed_categories if c]

    entries = _children(channel, "entry" if atom else "item")
    if len(entries) > MAX_ENTRIES:
        logger.info(
            "feed_entry_cap_applied", offered=len(entries), cap=MAX_ENTRIES
        )
        entries = entries[:MAX_ENTRIES]

    for entry in entries:
        title = _text(_child(entry, "title"))
        if not title:
            # An untitled entry imports as a slug of nothing, and two of them
            # collide on the second. Skipping is visible; a silent collision is
            # not.
            logger.info("feed_entry_skipped", reason="no title")
            continue

        link = ""
        if atom:
            for candidate in _children(entry, "link"):
                href = candidate.get("href") or ""
                rel = (candidate.get("rel") or "alternate").lower()
                if href and rel == "alternate":
                    link = href.strip()
                    break
            if not link:
                link = _text(_child(entry, "id"))
        else:
            link = _text(_child(entry, "link"))

        # `content:encoded` and Atom's <content> carry the full post; the
        # description/summary is a plain-text teaser in every real feed.
        content = _text(_child(entry, "encoded"))
        if not content:
            content_node = _child(entry, "content")
            if content_node is not None:
                content = _text(content_node)
        if not content:
            content = _text(_child(entry, "description"))
        if not content:
            content = _text(_child(entry, "summary"))

        # The summary element for the format. Asked for by name rather than
        # with `or`: in RSS `<description>` is the only one, and in Atom
        # `<summary>` is — but the two are alternative spellings of one field,
        # so taking whichever element is present keeps a feed that uses both
        # (very common: WordPress emits a summary *and* a description) from
        # silently losing its excerpt.
        excerpt = ""
        for name in ("description", "summary"):
            found = _text(_child(entry, name))
            if found:
                excerpt = found
                break
        excerpt = _strip_tags(excerpt) or None

        published = _parse_date(
            _text(_child(entry, "pubdate"))
            or _text(_child(entry, "published"))
            or _text(_child(entry, "updated"))
        )

        creator = _text(_child(entry, "creator"))
        if not creator and atom:
            author = _child(entry, "author")
            if author is not None:
                creator = _text(_child(author, "name"))

        # The keys `import_json` actually reads, not the ones a feed names.
        # It reads `category_slug` / `tag_slugs` / `status` / `locale`; a feed
        # gives a per-item category list and no status at all. Emitting the
        # feed's own vocabulary here would produce a dict that looks right and
        # imports untagged — every post would land uncategorised, silently.
        entry_categories: list[str] = []
        entry_tags: list[str] = []
        if not atom:
            for cat in _children(entry, "category"):
                term = (cat.get("term") or _text(cat)).strip()
                if not term:
                    continue
                if cat.get("domain") == "post_tag":
                    entry_tags.append(term)
                    tags.setdefault(term, {"name": term})
                else:
                    entry_categories.append(term)
                    categories.setdefault(term, {"name": term})
        if not entry_categories:
            entry_categories = list(feed_categories) if not atom else []

        post: dict[str, Any] = {
            "title": title,
            "content": content or title,
            "excerpt": excerpt,
            # Every imported entry is a draft. A feed publishes by definition,
            # and importing a stranger's entire archive as live posts would put
            # unreviewed content on the storefront.
            "status": "draft",
            "category_slug": entry_categories[0] if entry_categories else None,
            "tag_slugs": entry_tags,
        }
        if published:
            post["published_at"] = published
        if link:
            # `BlogPost` has no source-URL column, so the feed's own link goes
            # into the body as a provenance line rather than being dropped. On
            # a migration the reader needs to know where a post came from, and
            # the alternative — losing it — is unrecoverable afterwards.
            post["content"] = (
                f'{post["content"]}\n\n'
                f'<p><small>منبع: <a href="{_escape_attr(link)}" '
                f'rel="nofollow noopener">{_escape_text(link)}</a></small></p>'
            )
        posts.append(post)

    for term in (feed_categories if not atom else []):
        categories.setdefault(term, {"name": term})

    return {
        "categories": list(categories.values()),
        "tags": list(tags.values()),
        "posts": posts,
    }