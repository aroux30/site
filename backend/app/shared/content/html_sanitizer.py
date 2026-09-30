"""Server-side HTML allowlist for operator-authored rich text.

Why this exists: content bodies are stored as raw HTML. Until now the only
sanitiser in the system was DOMPurify in the browser
(``frontend/lib/editor/markdown.ts``), which protects an editor using the UI and
nobody else. The API accepts the same fields directly, and the body is rendered
with ``dangerouslySetInnerHTML``, so any account with content-write access could
persist ``<script>`` or an ``onerror=`` handler that runs for every visitor.

This is the server-side half that was missing — the equivalent of WordPress'
``kses``. It runs on write, not on render, so a payload never reaches the
database at all.

Policy: an allowlist, not a denylist. Anything not named is stripped, so a new
``<script>`` technique does not need a new rule here. ``style`` attributes and
``class`` are permitted because product descriptions and landing pages rely on
them; ``style`` on untrusted input is a defacement risk, not a script-execution
one, and this content is authored by staff, not by anonymous visitors.
"""

from __future__ import annotations

import re

import bleach
import tinycss2
from bleach.css_sanitizer import CSSSanitizer

# Tags an editor legitimately produces. Deliberately excludes script, object,
# embed, form, input, and the event-handler attributes below. ``iframe`` is added
# separately by ``_EMBED_ALLOWED_TAGS`` because an iframe is only acceptable
# from a video host, and that has to be checked per-element rather than by tag.
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # structure
        "p", "br", "hr", "div", "span", "section", "article", "header",
        "footer", "main", "aside", "nav", "figure", "figcaption",
        # headings
        "h1", "h2", "h3", "h4", "h5", "h6",
        # text
        "strong", "b", "em", "i", "u", "s", "strike", "del", "ins", "sub",
        "sup", "small", "mark", "abbr", "cite", "q", "code", "kbd", "samp",
        "pre", "var", "time", "bdi", "bdo", "wbr", "ruby", "rt", "rp",
        # lists
        "ul", "ol", "li", "dl", "dt", "dd",
        # tables
        "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
        "colgroup", "col",
        # links and media
        "a", "img", "picture", "source", "video", "audio", "track",
        # blocks an editor emits
        "blockquote", "details", "summary", "address",
    }
)

# `target` and `rel` are kept because product links open in a new tab; `rel` is
# forced to include noopener so an editor-authored link cannot reach back into
# the opener window.
ALLOWED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "*": frozenset({"class", "id", "title", "dir", "lang", "style", "role"}),
    "a": frozenset({"href", "target", "rel", "name"}),
    "img": frozenset(
        {"src", "alt", "width", "height", "loading", "decoding", "srcset", "sizes"}
    ),
    "source": frozenset({"src", "srcset", "type", "media", "sizes"}),
    "video": frozenset({"src", "controls", "poster", "width", "height", "preload"}),
    "audio": frozenset({"src", "controls", "preload"}),
    "track": frozenset({"src", "kind", "srclang", "label", "default"}),
    "td": frozenset({"colspan", "rowspan", "headers", "scope"}),
    "th": frozenset({"colspan", "rowspan", "headers", "scope", "abbr"}),
    "ol": frozenset({"start", "reversed", "type"}),
    "li": frozenset({"value"}),
    "col": frozenset({"span"}),
    "colgroup": frozenset({"span"}),
    "time": frozenset({"datetime"}),
    "details": frozenset({"open"}),
}

# URLs restricted to these schemes; anything else (javascript:, data:) is
# dropped by bleach before it reaches the database.
ALLOWED_PROTOCOLS: frozenset[str] = frozenset({"http", "https", "mailto", "tel"})

# Layout properties an editor uses on landing pages and product descriptions.
# Restricted to properties rather than left open, so a `style` attribute cannot
# smuggle in a url(...) pointing at a remote origin.
ALLOWED_CSS_PROPERTIES: frozenset[str] = frozenset(
    {
        "color", "background-color", "background", "font-size", "font-weight",
        "font-style", "font-family", "text-align", "text-decoration",
        "line-height", "letter-spacing", "margin", "margin-top",
        "margin-bottom", "margin-left", "margin-right", "padding",
        "padding-top", "padding-bottom", "padding-left", "padding-right",
        "border", "border-top", "border-bottom", "border-left", "border-right",
        "border-radius", "border-color", "border-width", "border-style",
        "width", "height", "max-width", "max-height", "min-width",
        "min-height", "display", "gap", "grid-template-columns",
        "flex-direction", "justify-content", "align-items", "opacity",
        "box-shadow", "overflow", "vertical-align", "white-space",
    }
)

_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)

# ── Embeds ───────────────────────────────────────────────────────────────────
# The editor's oEmbed button fetches a provider snippet, and every provider
# returns an <iframe>. The client allowlist permitted iframes from these hosts
# while the server allowlist had no `iframe` at all, so the write path deleted
# what the editor had just inserted: an editor embedded a video, saved, and it
# vanished with no error. The fix is to permit the tag *and* filter by host, so
# an arbitrary third-party frame still cannot be injected. These are the same
# hosts the client enforces (EMBED_HOST_RE in lib/editor/markdown.ts and
# lib/sanitize-html.ts) — the two lists must stay in step.
_EMBED_HOSTS: tuple[str, ...] = (
    r"(?:www\.)?youtube\.com/embed",
    r"(?:www\.)?youtube-nocookie\.com/embed",
    r"(?:www\.)?aparat\.com/video",
    r"(?:www\.)?twitch\.tv/embed",
    r"(?:www\.)?instagram\.com/embed",
)
_EMBED_SRC_RE = re.compile(
    r"^https://(?:" + "|".join(_EMBED_HOSTS) + r")", re.IGNORECASE
)
# iframe with nothing but these. `allow`/`allowfullscreen` matter: without
# allowfullscreen the provider's own fullscreen button does nothing.
_EMBED_ALLOWED_TAGS: frozenset[str] = ALLOWED_TAGS | {"iframe"}
_EMBED_ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    **ALLOWED_ATTRIBUTES,
    "iframe": [
        "src", "width", "height", "title",
        "frameborder", "loading", "allow", "allowfullscreen",
    ],
}
_IFRAME_RE = re.compile(r"<iframe\b[^>]*>(?:.*?</iframe\s*>)?", re.IGNORECASE | re.DOTALL)
_SRC_ATTR_RE = re.compile(r'\ssrc\s*=\s*"([^"]*)"', re.IGNORECASE)

#: Tags whose *contents* are code, not prose, so bleach's ``strip=True`` is
#: exactly wrong for them: it removes the tags and leaves the text behind.
#: ``<script>alert(1)</script>`` was stored and rendered as the literal string
#: "alert(1)". They are deleted whole, content included, before cleaning.
_DROP_WITH_CONTENT_RE = re.compile(
    r"<(script|style|noscript|template)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

# bleach serialises attributes with double quotes and leaves the value in
# declaration order, so matching the whole `style="..."` attribute is enough.
_STYLE_ATTR_RE = re.compile(r'\sstyle="([^"]*)"', re.IGNORECASE)

# A property allowlist is not enough on its own: `background: url(//evil/x)`
# passes the property check and still phones home, and `expression(...)` is a
# script-execution vector in legacy engines. Neither is needed to lay out a
# product description, so any declaration containing them is dropped whole.
_CSS_VALUE_FORBIDDEN = re.compile(
    r"(?:expression\s*\(|url\s*\(|javascript\s*:|vbscript\s*:|@import|behavior\s*:|-moz-binding)",
    re.IGNORECASE,
)


def _clean_style_attribute(value: str | None) -> str | None:
    """Drop any declaration in a ``style`` value that reaches outside the page.

    ``bleach`` filters the property names; this filters the values. Parsed
    rather than regexed in one pass over the whole string so a declaration
    containing a safe property is not lost because a later one was dangerous.
    """
    if not value:
        return value
    kept: list[str] = []
    for node in tinycss2.parse_declaration_list(value, skip_whitespace=True):
        if node.type != "declaration":
            continue
        serialized = tinycss2.serialize(node.value)
        if _CSS_VALUE_FORBIDDEN.search(serialized):
            continue
        kept.append(f"{node.lower_name}:{serialized.strip()}")
    return ";".join(kept) if kept else None


def _strip_foreign_iframes(html: str) -> str:
    """Remove every iframe whose ``src`` is not a known video provider.

    Runs before bleach so a disallowed frame is deleted whole rather than
    unwrapped — leaving its inner text behind would leak provider markup into
    the body.
    """
    def _replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_match = _SRC_ATTR_RE.search(tag)
        if src_match is None or not _EMBED_SRC_RE.match(src_match.group(1).strip()):
            return ""
        return tag

    return _IFRAME_RE.sub(_replace, html)


def drop_code_blocks(html: str) -> str:
    """Remove script/style/noscript/template elements *with their content*.

    bleach.clean(strip=True) removes the tags and leaves the body behind, so
    <script>alert(1)</script> is stored and rendered as the literal text
    "alert(1)". The body of these elements is code, never prose, so deleting
    it whole is the only correct reading. Exposed because the comment sanitizer
    has its own tag list and needs the same step.
    """
    return _DROP_WITH_CONTENT_RE.sub("", html)


def sanitize_html(html: str | None) -> str:
    """Return ``html`` with everything outside the allowlist removed.

    Safe to call on already-clean content — it is idempotent, so a body that
    went through the editor's DOMPurify pass survives unchanged.

    ``None`` and empty input return ``""`` rather than ``None`` so the result
    can be assigned straight to a non-nullable column.
    """
    if not html:
        return ""
    # An iframe is allowed only from a known video provider, and that decision
    # is per-element: bleach's tag allowlist cannot see a src. Foreign frames go
    # first so they leave no inner markup behind, then code-bearing tags go
    # whole so their text does not survive as prose.
    html = _strip_foreign_iframes(html)
    html = drop_code_blocks(html)
    cleaned = bleach.clean(
        html,
        tags=_EMBED_ALLOWED_TAGS,
        attributes=_EMBED_ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
        strip_comments=True,
    )
    # bleach filters property names but passes `url(...)` and `expression(...)`
    # values through, so every surviving `style` value is filtered here.
    cleaned = _STYLE_ATTR_RE.sub(
        lambda m: (
            f' style="{_clean_style_attribute(m.group(1))}"'
            if _clean_style_attribute(m.group(1))
            else ""
        ),
        cleaned,
    )
    # A new-tab link that does not say noopener lets the opened page reach back
    # through window.opener. Editors do not think about this, so add it.
    return bleach.linkifier.Linker(
        callbacks=[bleach.callbacks.nofollow],
        skip_tags=["pre", "code"],
        parse_email=False,
    ).linkify(cleaned)
