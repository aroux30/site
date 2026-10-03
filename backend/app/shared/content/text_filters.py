"""WordPress-compatible text filters for stored bodies.

WordPress runs ``wpautop``, ``wptexturize`` and ``wp_staticize_emoji`` over
``the_content`` (see ``wp-includes/formatting.php``). Our editor writes plain
text paragraphs separated by blank lines, so without these a body authored as
prose renders as one run-on block wherever no client-side split happens to
exist.

Why server side: the blog detail, the CMS page and the feed all read the same
stored body. A filter that only lives in one component means the other two
render the same content differently. Rendering happens on read, in
``render_body`` (mirroring ``the_content``), so changing the formatting logic
reaches every already-published page.

What is deliberately not here: block-level HTML the author wrote is left alone.
``wpautop`` only wraps runs of text that are not already inside a block element,
so a body authored with ``<h2>`` or ``<div>`` keeps its own structure.
"""

from __future__ import annotations

import re

# Elements whose content is already block-level markup: wpautop never wraps it.
# Mirrors the block list in wp-includes/formatting.php, trimmed to what survives
# sanitize_html. ``pre``/``code`` are absent on purpose, see _PRESERVE_RE.
_BLOCK_TAGS = (
    "address|article|aside|blockquote|details|div|dl|dd|dt|fieldset|figcaption|"
    "figure|footer|form|h1|h2|h3|h4|h5|h6|header|hgroup|hr|li|main|nav|ol|p|"
    "section|table|tbody|td|tfoot|th|thead|tr|ul"
)
_BLOCK_ALT = _BLOCK_TAGS

# Regions that must survive byte for byte. ``pre``/``code`` lead and are also
# absent from _BLOCK_TAGS: a code sample has to reach the reader with its
# quotes, spacing and indentation exactly as typed. The trailing alternative
# captures any HTML tag, so a straight quote inside ``<a href="…" title="…"`` is
# never typographed — that would truncate the attribute and break the markup.
_PRESERVE_RE = re.compile(
    r"<(pre|code|textarea|script|style)\b[^>]*>.*?</\1\s*>"
    r"|<!--.*?-->"
    r"|</?[a-z][a-z0-9-]*(?:\s[^<>]*?)?/?>",
    re.IGNORECASE | re.DOTALL,
)

# A shortcode token like [block slug="news"] is not HTML, but its quotes are still
# delimiters: texturizing them produces [block slug=“news”], which the shortcode
# parser then reads as one attribute named slug=“news”. Matched on its own, with
# no cross-newline alternative, so it can never swallow the paragraphs around it.
_SHORTCODE_RE = re.compile(r"\[[a-z][a-z0-9_-]*(?:[ \t]+[^\]\n]*)?\]", re.IGNORECASE)

# A region that is itself a block element: ``<p>a</p>`` matches, prose does not.
# No backreference needed here -- this only tests the *start* of a chunk, and the
# chunk has already been separated from its neighbours by the newline split.
_BLOCK_REGION_RE = re.compile(r"\A\s*<(?:%s)\b" % _BLOCK_ALT, re.IGNORECASE)

# Regions that must survive byte for byte, and the verbatim block elements.
# Group 1 of the second alternative is the whole element and group 2 is its tag
# name, so the closing side is forced to match the same name: without a
# backreference the non-greedy body stops at whichever close tag appears first
# anywhere in the document, and a <p> followed later by a </div> is swallowed
# whole. The '<' sits outside the name group on purpose -- inside it, the engine
# matches '>' as part of the name and every region comes back missing its
# opening bracket.
_PRESERVE_BLOCK_RE = re.compile(
    r"<(?:pre|code)\b[^>]*>.*?</(?:pre|code)\s*>"
    r"|<(%s)\b[^>]*>.*?</\1\s*>" % _BLOCK_ALT,
    re.IGNORECASE | re.DOTALL,
)


def _split_verbatim(html: str) -> list[str]:
    """Split into runs of prose and regions that must stay byte for byte."""
    out: list[str] = []
    pos = 0
    for m in _PRESERVE_BLOCK_RE.finditer(html):
        if m.start() > pos:
            out.append(html[pos:m.start()])
        out.append(m.group(0))
        pos = m.end()
    if pos < len(html):
        out.append(html[pos:])
    return [p for p in out if p]

_BLANK_LINES = re.compile(r"\n{2,}")

# Markers must never collide. ``wpautop`` leaves its own markers in the string it
# returns, and the chain re-stashes that string for the texturize pass: with a
# fixed "\x000\x00" both stashes number from 0, so a marker from the first pass
# decodes into a region from the second and the body comes back shredded. A
# per-call tag keeps them apart.
_STASH_TAG = ""


def _stash(html: str) -> tuple[str, list[str]]:
    """Take out every region whose bytes must not change.

    Four kinds, all of which a text pass would otherwise corrupt: pre/code/
    script bodies (whitespace is code, quotes are literal), HTML comments, the
    tags themselves (a straight quote inside an attribute is a delimiter), and
    shortcode tokens.
    """
    stash: list[str] = []

    def _take(m: re.Match[str]) -> str:
        stash.append(m.group(0))
        return "%s%d:%d" % (_STASH_TAG, id(stash) % 100000, len(stash) - 1)

    return _SHORTCODE_RE.sub(_take, _PRESERVE_RE.sub(_take, html)), stash


def _unstash(html: str, stash: list[str]) -> str:
    if not stash:
        return html
    tag = "%s%d:" % (_STASH_TAG, id(stash) % 100000)
    return re.sub(re.escape(tag) + r"(\d+)", lambda m: stash[int(m.group(1))], html)


def wptexturize(text: str) -> str:
    """Apply WordPress's typographic replacements to a run of plain text.

    Covers what matters for Persian and English prose: the curly quotes and
    apostrophe, the em/en dash, the ellipsis, and the trademark/copyright/
    registered/phonogram marks.

    Markup is *not* touched: a quote or dash inside ``<a href="…" title="…"``
    has to stay straight or the attribute is truncated. The input is therefore a
    prose run, and every caller stashes the markup out first.

    Deliberately *not* implemented: fractions and the ordinal squaring that full
    ``wptexturize`` does. Those mangle digits, and a storefront shows prices,
    phone numbers and order ids in every body and every email.
    """
    if not text:
        return text
    for src, dst in (("...", "…"), ("---", "—"), ("--", "–"),
                     ("(c)", "©"), ("(r)", "®"), ("(tm)", "™"), ("(p)", "℗")):
        text = text.replace(src, dst)
    # The inch/foot marks and the double prime are word-internal; the opening
    # and closing doubles are word-external. Same for the single forms, which is
    # what turns don't into don’t instead of don‘t.
    text = re.sub(r'(?<=\w)"(?=\w)', "”", text)
    text = re.sub(r'(?<=\w)"(?=\s|$)', "”", text)
    text = re.sub(r'(?<!\w)"', "“", text)
    text = re.sub(r"(?<=\w)'(?=\w)", "’", text)
    text = re.sub(r"(?<=\w)'(?=\s|$)", "’", text)
    text = re.sub(r"(?<!\w)'", "‘", text)
    return text


#: A small curated subset of wp-includes/formatting.php's smilies table. The
#: full set is several hundred entries; an unknown token is left as literal text.
_EMOJI = {
    ":smile:": "\U0001f604", ":smiley:": "\U0001f603", ":grin:": "\U0001f601",
    ":laughing:": "\U0001f606", ":wink:": "\U0001f609", ":blush:": "\U0001f60a",
    ":heart_eyes:": "\U0001f60d", ":kissing_heart:": "\U0001f618",
    ":thinking:": "\U0001f914", ":neutral_face:": "\U0001f610", ":smirk:": "\U0001f60f",
    ":unamused:": "\U0001f612", ":disappointed:": "\U0001f61e", ":worried:": "\U0001f61f",
    ":cry:": "\U0001f622", ":sob:": "\U0001f62d", ":angry:": "\U0001f620",
    ":rage:": "\U0001f621", ":scream:": "\U0001f631", ":sleeping:": "\U0001f634",
    ":sunglasses:": "\U0001f60e", ":nerd_face:": "\U0001f913", ":thumbsup:": "\U0001f44d",
    ":+1:": "\U0001f44d", ":thumbsdown:": "\U0001f44e", ":-1:": "\U0001f44e",
    ":clap:": "\U0001f44f", ":pray:": "\U0001f64f", ":wave:": "\U0001f44b",
    ":ok_hand:": "\U0001f44c", ":muscle:": "\U0001f4aa", ":point_right:": "\U0001f449",
    ":point_left:": "\U0001f448", ":heart:": "❤", ":broken_heart:": "\U0001f494",
    ":star:": "⭐", ":sparkles:": "✨", ":fire:": "\U0001f525", ":tada:": "\U0001f389",
    ":rocket:": "\U0001f680", ":warning:": "⚠", ":bulb:": "\U0001f4a1", ":zap:": "⚡",
    ":boom:": "\U0001f4a5", ":gift:": "\U0001f381", ":white_check_mark:": "✅",
    ":x:": "❌", ":heavy_check_mark:": "✔", ":question:": "❓", ":exclamation:": "❗",
    ":no_entry:": "⛔", ":moneybag:": "\U0001f4b0", ":package:": "\U0001f4e6",
    ":truck:": "\U0001f69a", ":coffee:": "☕", ":pizza:": "\U0001f355",
}


def wp_staticize_emoji(text: str) -> str:
    """Turn a bare ``:smile:`` token into its Unicode character.

    WordPress renders these server-side too (``wp_staticize_emoji`` in
    wp-includes/formatting.php), so a body authored with shortcodes reads the
    same everywhere instead of only where a client-side library is loaded.
    """
    if not text or ":" not in text:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == ":":
            end = text.find(":", i + 1)
            # A shortcode name carries no whitespace, and the 24-char bound
            # stops a lone colon from scanning the rest of the document.
            if end != -1 and 1 < end - i <= 24:
                token = text[i:end + 1]
                if not any(c.isspace() for c in token):
                    emoji = _EMOJI.get(token.lower())
                    if emoji is not None:
                        out.append(emoji)
                        i = end + 1
                        continue
        out.append(text[i])
        i += 1
    return "".join(out)


def wpautop(html: str | None) -> str:
    """Wrap blank-line-separated prose in ``<p>``, as WordPress does.

    A body stored as plain text (``First line\\n\\nSecond line``) has to become
    two paragraphs before a stylesheet can space it. Text already inside a block
    element is left exactly as the author wrote it, and a blank line *between*
    two block elements is collapsed rather than turned into an empty paragraph.

    ``None``-tolerant to match ``sanitize_html``: this runs on the same
    non-nullable column.
    """
    if not html:
        return ""
    if "<" not in html and "\n" not in html:
        # A single line of text still needs its paragraph, or the prose
        # stylesheet never applies the body size.
        return "<p>%s</p>" % html

    stashed, stash = _stash(html)

    # Whitespace that merely separates two block elements is not a paragraph
    # break: </p>\n<p> must not become </p><p></p><p>. Both the closing and the
    # opening side need collapsing, which is what the two subs do.
    for pattern, repl in (
        (r"[ \t]*\n[ \t]*(</(?:%s)>)" % _BLOCK_TAGS, r"\1"),
        (r"(<(?:%s)\b[^>]*>)[ \t]*\n[ \t]*" % _BLOCK_TAGS, r"\1"),
    ):
        stashed = re.sub(pattern, repl, stashed, flags=re.IGNORECASE)

    rebuilt: list[str] = []
    for para in _BLANK_LINES.split(stashed):
        chunk = para.strip()
        if not chunk:
            continue
        # A chunk that opens with a block element is markup the author wrote.
        if _BLOCK_REGION_RE.match(chunk) or _unstash(chunk, stash).lstrip().startswith("<"):
            rebuilt.append(chunk)
        else:
            rebuilt.append("<p>%s</p>" % chunk)
    return _unstash("\n".join(rebuilt), stash)


def wpautop_texturize_emoji(html: str | None) -> str:
    """Run WordPress's full text filter chain over a body.

    Order mirrors ``the_content`` in wp-includes/default-filters.php: ``wpautop``
    first, so the texturize pass sees whole paragraphs rather than raw newlines;
    then ``wptexturize`` and the emoji pass, which both skip anything inside a
    block element.

    Display-only: nothing here writes back to the stored column. The authored
    text stays authored, which is what a revision diff and a later re-render
    both need.
    """
    if not html:
        return ""
    # wpautop hands back markers and verbatim block elements. Splitting on both
    # keeps them out of the text passes: a marker is stashed markup, and a block
    # element's own text is markup the author wrote. ``pre``/``code`` lead the
    # split pattern because they are absent from _BLOCK_ALT on purpose, yet
    # their text still must not be typographed.
    paragraphs = wpautop(html)
    out: list[str] = []
    for part in _split_verbatim(paragraphs):
        if re.match(r"\A(<%s\b|<(?:pre|code)\b|%s)" % (_BLOCK_ALT, _STASH_TAG),
                    part, re.IGNORECASE):
            out.append(part)
            continue
        prose, stash = _stash(part)
        out.append(_unstash(wp_staticize_emoji(wptexturize(prose)), stash))
    return "".join(out)


__all__ = ["wpautop", "wptexturize", "wp_staticize_emoji", "wpautop_texturize_emoji"]
