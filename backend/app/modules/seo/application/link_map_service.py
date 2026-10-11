"""Keyword-map auto-linking (Rank Math Pro's "Keyword Maps").

A keyword map links every mention of a phrase to a target URL. Running it on
publish means a writer never hand-links the same product in every article.

The insertion is done on the parsed HTML, not by string-splicing raw HTML:
a plain regex replace over the body would happily wrap a keyword that already
sits inside an ``<a>``, inside a heading's ``id`` attribute, or inside a
``<script>`` — producing nested anchors, which browsers rewrite unpredictably.
The walker below skips text inside an existing anchor and inside non-prose
tags, and inserts at most ``max_links_per_post`` times.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from app.modules.seo.application.link_text import normalize_text

#: Tags whose text content must never receive an auto-link: an anchor (would
#: nest), and anything that is not reader-facing prose.
_SKIP_TAGS = frozenset(
    {"a", "code", "pre", "script", "style", "textarea", "h1", "h2", "h3", "h4", "h5", "h6"}
)


class _AutoLinker(HTMLParser):
    """Insert anchor tags around keyword matches in text nodes.

    ``handle_data`` receives already-unescaped text (``convert_charrefs=True``),
    so a match can be made on the visible words. The inserted anchor re-escapes
    nothing — the surrounding text is passed through with ``html.escape`` only
    for the parts that are spliced out, because ``HTMLParser`` gives us the
    decoded form and ``get_starttag_text`` the raw form.
    """

    def __init__(
        self,
        *,
        patterns: list[re.Pattern[str]],
        target_url: str,
        remaining: int,
    ) -> None:
        super().__init__(convert_charrefs=False)
        # One combined alternation, longest keyword first, so the most specific
        # phrase wins the anchor text within a single scan.
        self._combined = (
            re.compile(
                "|".join(p.pattern for p in patterns),
                patterns[0].flags if patterns else 0,
            )
            if patterns
            else None
        )
        self._target_url = target_url
        self._remaining = remaining
        self._skip_depth = 0
        self._out: list[str] = []

    @property
    def result(self) -> str:
        return "".join(self._out)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth += 1
        self._out.append(self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._out.append(self.get_starttag_text() or f"<{tag}/>")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0 or self._remaining <= 0:
            self._out.append(data)
            return
        self._out.append(self._linkify(data))

    def handle_entityref(self, name: str) -> None:
        self._out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._out.append(f"&#{name};")

    def _linkify(self, text: str) -> str:
        """Wrap every keyword occurrence in this text node, up to the budget.

        Wrapping all matches (not just the first) matters: a paragraph that
        says the keyword three times should produce up to three links when the
        cap allows, not one. The budget is shared across the whole document, so
        a later text node may get fewer (or zero).
        """
        if self._combined is None or self._remaining <= 0:
            return text
        out: list[str] = []
        last = 0
        for match in self._combined.finditer(text):
            if self._remaining <= 0:
                break
            out.append(text[last : match.start()])
            out.append(f'<a href="{self._target_url}">{match.group(0)}</a>')
            last = match.end()
            self._remaining -= 1
        out.append(text[last:])
        return "".join(out)


def _build_patterns(keywords: list[str], *, case_sensitive: bool) -> list[re.Pattern[str]]:
    """One alternation pattern per keyword, longest first.

    Longest-first ordering means «پابجی موبایل» matches before «پابجی», so the
    more specific phrase wins the anchor text. Boundaries are a manual
    lookaround on the token class (``\\b`` is unreliable around Persian).
    """
    ordered = sorted({k.strip() for k in keywords if k.strip()}, key=len, reverse=True)
    flags = 0 if case_sensitive else re.IGNORECASE
    patterns: list[re.Pattern[str]] = []
    for keyword in ordered:
        needle = keyword if case_sensitive else normalize_text(keyword)
        patterns.append(
            re.compile(
                r"(?<![\w؀-ۿ])" + re.escape(needle) + r"(?![\w؀-ۿ])",
                flags,
            )
        )
    return patterns


def count_existing_links(content: str, target_url: str) -> int:
    """How many anchors already point at ``target_url`` (normalized)."""
    from app.modules.seo.application.link_extraction_service import (
        extract_anchors,
        normalize_url,
    )

    want = normalize_url(target_url)
    count = 0
    for href, _text, _nf, _tb in extract_anchors(content or ""):
        if normalize_url(href) == want:
            count += 1
    return count


def apply_keyword_map(
    content: str,
    *,
    keywords: list[str],
    target_url: str,
    max_links_per_post: int = 3,
    case_sensitive: bool = False,
) -> tuple[str, int]:
    """Insert auto-links for one map. Returns ``(new_content, inserted_count)``.

    ``max_links_per_post`` is the total cap *including* links that already
    exist to the same target, so a post that already links the target twice
    under a 3-cap gets at most one more.
    """
    if not content or not keywords or not target_url:
        return content, 0

    existing = count_existing_links(content, target_url)
    remaining = max(0, max_links_per_post - existing)
    if remaining <= 0:
        return content, 0

    patterns = _build_patterns(keywords, case_sensitive=case_sensitive)
    linker = _AutoLinker(
        patterns=patterns,
        target_url=target_url,
        remaining=remaining,
    )
    try:
        linker.feed(content)
        linker.close()
    except Exception:
        # A malformed body is left untouched rather than half-linked.
        return content, 0
    inserted = remaining - linker._remaining
    return linker.result, inserted
