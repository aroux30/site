"""Normalize the heading level of stored bodies to keep one <h1> per page.

The article page renders the post's title as the page's only <h1>. A stored
body that ALSO starts with an <h1> — which is what a WordPress migration
produces, since the source article's title lived inside the content — gives
the page two H1s. Search engines read that as a structural error ("multiple
H1 tags"), and screen readers announce two page titles.

The body's H1 becomes an H2 (the next level down), and any deeper heading is
left alone. Idempotent: a second pass finds no H1 and changes nothing.

Deliberately narrow: only H1 → H2. Promoting H3s or renumbering a whole
document would rewrite the author's outline, and the bug being fixed is the
duplicate page title, not the article's internal hierarchy.
"""

from __future__ import annotations

import re

_H1_RE = re.compile(r"<h1(\s[^>]*)?>(.*?)</h1\s*>", re.IGNORECASE | re.DOTALL)


def demote_body_h1(html: str | None) -> str:
    """Turn every body-level <h1> into an <h2>. See module docstring."""
    if not html or "<h1" not in html.lower():
        return html or ""
    return _H1_RE.sub(
        lambda m: f"<h2{m.group(1) or ''}>{m.group(2)}</h2>", html
    )


__all__ = ["demote_body_h1"]
