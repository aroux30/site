"""Render-time Table-of-Contents linking (the "TOC plugin" behavior).

Migrated articles carry their ToC as a plain ``<ol>`` of the section titles.
On the source WordPress site the items were inert — clicking one scrolled
nothing (verified live: scrollY did not move) — and the operator's
expectation is the behavior those plugins provide: click a ToC entry, land
on the section.

Storage keeps the authored HTML untouched (the same rule as wpautop:
rendering happens on read, so a fix here reaches already-published pages).
This pass runs after the text filters and:

* gives every heading the ToC references an ``id`` (``toc-1``, ``toc-2``, …)
  — stable ASCII ids, so the fragment works without URL-encoding;
* wraps each matching ToC ``<li>``'s content in ``<a href="#toc-N">``.

A list only counts as a ToC when at least two of its items textually match a
heading (leading ``1. `` / ``۱.`` numbering ignored, ZWNJ normalised): an
ordinary bullet list that happens to share one phrase with a heading must
not sprout links. Idempotent — an existing ``id`` or ``<a>`` is kept, so a
second render changes nothing and authored anchors are never overwritten.
"""

from __future__ import annotations

import html as _html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_HEADING_RE = re.compile(r"<(h[2-6])(\s[^>]*)?>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL)
_ID_ATTR_RE = re.compile(r'\bid\s*=\s*"([^"]*)"', re.IGNORECASE)
_LIST_RE = re.compile(r"<(ol|ul)(\s[^>]*)?>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL)
_LI_RE = re.compile(r"<li(\s[^>]*)?>(.*?)</li\s*>", re.IGNORECASE | re.DOTALL)
#: Leading section numbering — ASCII and Persian digits, with the separators
#: authors actually type (`.` `-` `)` `–`). The ToC items do not repeat it
#: ("معرفی کلی…" vs the heading "1. معرفی کلی…"), so matching has to ignore it.
_LEAD_NUM_RE = re.compile(r"^[\s‌]*[\d۰-۹]+\s*[\.\-\)–—]\s*")

#: A list is a ToC when this share of its items matches headings…
_MATCH_RATIO = 0.6
#: …and at least this many items match (one accidental phrase is not a ToC).
_MIN_MATCHES = 2


def _norm(text_html: str) -> str:
    """Comparable text: no tags, no entities, no ZWNJ, no leading numbering."""
    text = _html.unescape(_TAG_RE.sub("", text_html))
    text = text.replace("‌", "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return _LEAD_NUM_RE.sub("", text)


def add_toc_links(html: str | None) -> str:
    """Link every ToC entry to its section heading. See module docstring."""
    if not html or "<li" not in html.lower():
        return html or ""

    headings: list[dict] = []
    for m in _HEADING_RE.finditer(html):
        attrs = m.group(2) or ""
        id_m = _ID_ATTR_RE.search(attrs)
        headings.append(
            {
                "start": m.start(),
                "end": m.end(),
                "tag": m.group(1),
                "attrs": attrs,
                "inner": m.group(3),
                "norm": _norm(m.group(3)),
                "id": id_m.group(1) if id_m else None,
                "had_id": id_m is not None,
            }
        )
    if not headings:
        return html

    by_norm: dict[str, dict] = {}
    for h in headings:
        if h["norm"] and h["norm"] not in by_norm:
            by_norm[h["norm"]] = h

    used_ids = {h["id"] for h in headings if h["id"]}
    counter = 0

    def ensure_id(h: dict) -> str:
        nonlocal counter
        if h["id"]:
            return h["id"]
        while True:
            counter += 1
            candidate = f"toc-{counter}"
            if candidate not in used_ids:
                used_ids.add(candidate)
                h["id"] = candidate
                return candidate

    replacements: list[tuple[int, int, str]] = []

    for lm in _LIST_RE.finditer(html):
        items = list(_LI_RE.finditer(lm.group(3)))
        if len(items) < _MIN_MATCHES:
            continue
        matched = [by_norm.get(_norm(li.group(2))) for li in items]
        hits = sum(1 for h in matched if h is not None)
        if hits < _MIN_MATCHES or hits < len(items) * _MATCH_RATIO:
            continue

        # Rebuild the list body right-to-left so earlier spans stay valid.
        # The ids are assigned first, in FORWARD order, so the first section
        # is `toc-1` — numbering that reads backwards in the DOM is a support
        # question waiting to happen.
        pairs = [(li, h) for li, h in zip(items, matched) if h is not None]
        for _li, h in pairs:
            ensure_id(h)
        body = lm.group(3)
        new_body = body
        for li, h in reversed(pairs):
            inner = li.group(2)
            if "<a" in inner.lower():
                # Authored (or already-processed) link: keep it.
                continue
            new_inner = f'<a href="#{h["id"]}">{inner}</a>'
            new_body = new_body[: li.start(2)] + new_inner + new_body[li.end(2) :]
        replacements.append((lm.start(3), lm.end(3), new_body))

    for h in headings:
        if h["id"] and not h["had_id"]:
            replacements.append(
                (
                    h["start"],
                    h["end"],
                    f'<{h["tag"]}{h["attrs"]} id="{h["id"]}">{h["inner"]}</{h["tag"]}>',
                )
            )

    if not replacements:
        return html

    replacements.sort(key=lambda r: r[0])
    out: list[str] = []
    pos = 0
    for start, end, text in replacements:
        if start < pos:  # defensive: overlapping spans would corrupt the HTML
            continue
        out.append(html[pos:start])
        out.append(text)
        pos = end
    out.append(html[pos:])
    return "".join(out)


__all__ = ["add_toc_links"]
