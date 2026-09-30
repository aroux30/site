"""Permalink structure utilities (WordPress wp-includes/rewrite parity).

A permalink structure like ``/blog/%year%/%monthnum%/%postname%/`` describes
the public URL shape of a blog post. The admin edits the structure once in
settings; link generation (RSS feed, sitemap, storefront) and URL resolution
(Next.js middleware rewrite) both derive from it through this module.

Pure string logic — no database, no framework imports — so the same rules
run on the backend (feed links) and are mirrored 1:1 in the frontend's
``lib/permalinks.ts`` (link building + middleware resolution).

Supported structure tags (WordPress subset that makes sense here):
%postname%  %post_id%  %year%  %monthnum%  %day%  %category%  %author%
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STRUCTURE_TOKENS = (
    "%postname%",
    "%post_id%",
    "%year%",
    "%monthnum%",
    "%day%",
    "%category%",
    "%author%",
)

# Tokens that map to date parts; a structure must keep them in descending
# granularity (year before month before day) so generated URLs parse back.
_DATE_ORDER = ("year", "monthnum", "day")

_VALID_TAG_RE = re.compile(r"^/(?:[\w\-/%]+/)*[\w\-/%]*$")


@dataclass(frozen=True)
class PermalinkParts:
    """Everything the structure tags can be filled with for one post."""

    postname: str
    post_id: str
    year: str
    monthnum: str
    day: str
    category: str  # slug of the primary category ("" when uncategorized)
    author: str  # slug of the author


def validate_structure(structure: str) -> list[str]:
    """Return the list of problems with a proposed structure (empty = valid).

    Rules (mirrored in lib/permalinks.ts):
    - must start with "/"
    - only letters, digits, "-", "_", "/", "%" and known %tags%
    - at least one %tag% (otherwise every post would collide)
    - %postname% or %post_id% must be present (unique tail)
    - date tokens must appear in year → monthnum → day order
    """
    problems: list[str] = []
    structure = (structure or "").strip()
    if not structure.startswith("/"):
        problems.append("ساختار باید با / شروع شود.")
        return problems
    if not _VALID_TAG_RE.match(structure):
        problems.append("فقط حروف، رقم، -, _, / و تگ‌های مجاز %+...% پذیرفته می‌شود.")
        return problems

    tags = re.findall(r"%(\w+)%", structure)
    known = {t.strip("%") for t in STRUCTURE_TOKENS}
    unknown = [t for t in tags if t not in known]
    if unknown:
        problems.append(f"تگ ناشناخته: {', '.join('%' + t + '%' for t in unknown)}")

    if not tags:
        problems.append("ساختار باید حداقل یک تگ %...% داشته باشد.")
    elif not ({"postname", "post_id"} & set(tags)):
        problems.append("ساختار باید شامل %postname% یا %post_id% باشد تا آدرس‌ها یکتا بمانند.")

    positions = {name: i for i, name in enumerate(tags)}
    ordered_dates = [d for d in _DATE_ORDER if d in positions]
    if [positions[d] for d in ordered_dates] != sorted(positions[d] for d in ordered_dates):
        problems.append("ترتیب تگ‌های تاریخ باید سال → ماه → روز باشد.")

    return problems


def build_post_path(structure: str, parts: PermalinkParts) -> str:
    """Fill a structure with a post's parts and normalize the path.

    Empty parts (e.g. no category) collapse their separators so a structure
    like ``/blog/%category%/%postname%/`` degrades to ``/blog/my-post/``
    instead of producing a double slash.
    """
    values = {
        "postname": parts.postname,
        "post_id": parts.post_id,
        "year": parts.year,
        "monthnum": parts.monthnum,
        "day": parts.day,
        "category": parts.category,
        "author": parts.author,
    }
    path = structure
    for token, value in values.items():
        path = path.replace(f"%{token}%", value)

    # Collapse separator runs left by empty parts, then tidy the edges.
    path = re.sub(r"/{2,}", "/", path)
    if not path.endswith("/"):
        path += "/"
    return path


def structure_regex(structure: str) -> re.Pattern[str]:
    """Compile a structure into a regex with named groups per tag.

    Used to match an incoming URL back to its post identity; ``postname`` or
    ``post_id`` (whichever the structure ends with) is the capture that
    matters for resolution.
    """
    tag_patterns = {
        "postname": r"[^/]+",
        "post_id": r"\d+",
        "year": r"\d{4}",
        "monthnum": r"\d{1,2}",
        "day": r"\d{1,2}",
        "category": r"[^/]+",
        "author": r"[^/]+",
    }
    expr = re.sub(r"/{2,}", "/", structure)
    for tag, pattern in tag_patterns.items():
        expr = expr.replace(f"%{tag}%", f"(?P<{tag}>{pattern})")
    return re.compile(f"^{expr.rstrip('/')}/?$")


def is_default_structure(structure: str) -> bool:
    """True when the structure matches the canonical Next.js file tree
    (``/blog/<slug>/``) and needs no middleware involvement."""
    return structure.strip() in ("", "/blog/%postname%/")
