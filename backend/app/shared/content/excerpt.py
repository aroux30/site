"""Excerpt auto-generation from blog post content (WordPress parity).

Strips HTML tags and truncates to a configurable word count.

Usage:
    from app.shared.content.excerpt import auto_excerpt
    excerpt = auto_excerpt(html_content, max_words=55)
"""

from __future__ import annotations

import re


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_tags(html: str) -> str:
    """Remove all HTML tags from a string."""
    return _TAG_RE.sub("", html)


def auto_excerpt(
    html_content: str,
    *,
    max_words: int = 55,
    suffix: str = "...",
) -> str:
    """Generate an excerpt from HTML content.

    Strips tags, normalizes whitespace, and truncates to max_words.
    """
    text = strip_tags(html_content)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + suffix
