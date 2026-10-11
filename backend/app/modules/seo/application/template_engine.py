"""Rank Math-style template engine for meta titles and descriptions.

Rank Math's Titles & Meta panel lets an operator write one template per
content type — ``%title% %sep% %sitename%`` — instead of hand-writing every
meta tag. The storefront used to hardcode ``f"{post.title} | وبلاگ"``, so the
operator could not change the suffix without a deploy, and each content type
had its own hand-rolled format string.

This module is the single renderer. It is pure (no DB, no I/O): callers pass a
context dict, tests pin every variable. The site-option reading and the
context-building live in the callers (seo_service / routes).

Design rules, each answering a failure mode of the old hardcoded strings:

- An **unknown variable renders as empty**, not as the literal token. Shipping
  ``%unknown%`` into a meta tag is a visible defect on every page; an empty
  string degrades to "the operator used a variable that does not exist here",
  which the settings UI warns about at save time.
- A template that renders **only** whitespace/separators falls back to the
  caller's default. An empty meta title is worse than a generic one.
- The **case modifiers** (``%ucwords(x)%``, ``%lowercase(x)%``,
  ``%uppercase(x)%``) wrap another variable — Rank Math's way of fixing an
  all-caps product name without editing the product.
- ``%customfield(key)%`` and ``%term(taxonomy)%`` take a parameter; a missing
  key/term renders empty for the same reason unknown variables do.
"""

from __future__ import annotations

import re
from typing import Any, Callable

#: ``%name%`` or ``%name(param)%`` — the parameter may contain anything but a
#: closing paren (field names and slugs never contain one).
_VARIABLE = re.compile(r"%([a-z_]+)(?:\(([^)]*)\))?%", re.IGNORECASE)

#: Characters that never count as meaningful output. A template that renders
#: to " | " is empty for practical purposes.
_MEANINGLESS = re.compile(r"^[\s\|\-–—_.,،؛;:]*$")


def _ucwords(value: str) -> str:
    """Title-case every whitespace-separated word, keeping the rest intact."""
    return " ".join(w[:1].upper() + w[1:] if w else w for w in value.split(" "))


class TemplateEngine:
    """Renders a template string against a context.

    ``variables`` maps a lowercase variable name to a callable that receives
    the optional parameter and returns the replacement. The engine owns the
    matching, casing wrappers and empty-handling; callers own the vocabulary.
    """

    def __init__(self, variables: dict[str, Callable[[str | None], str]]) -> None:
        self._variables = {k.lower(): v for k, v in variables.items()}

    def render(self, template: str, *, context: dict[str, Any] | None = None) -> str:
        """Render *template*; unknown variables become empty strings."""
        # `context` is accepted for forward-compatibility (a future variable
        # may want the raw object); today every variable closes over its data.
        del context

        def replace(match: re.Match[str]) -> str:
            name = match.group(1).lower()
            param = match.group(2)
            resolver = self._variables.get(name)
            if resolver is None:
                return ""
            # A wrapper's parameter is itself a template: %ucwords(%title%)%
            # must case the RESOLVED title, not the literal "%title%". Nested
            # parens cannot be expressed in the regex, so the inner token is
            # rendered here, one level deep (Rank Math's wrappers take exactly
            # one variable — deeper nesting is not part of its vocabulary).
            if param is not None and "%" in param:
                param = _VARIABLE.sub(replace, param)
            try:
                value = resolver(param)
            except Exception:
                # A resolver that raises must not take the page down; a meta
                # tag is not worth a 500. Empty is the safe rendering.
                return ""
            return value or ""

        return _VARIABLE.sub(replace, template)

    def render_or_default(self, template: str, default: str) -> str:
        """Render, falling back to *default* when the result is meaningless."""
        rendered = self.render(template).strip()
        if not rendered or _MEANINGLESS.match(rendered):
            return default
        # Collapse doubled separators left by empty variables: "Foo | | Site".
        rendered = re.sub(r"\s{2,}", " ", rendered)
        rendered = re.sub(r"(\|\s*){2,}", "| ", rendered)
        return rendered.strip()


def build_variables(
    *,
    title: str | None = None,
    sitename: str | None = None,
    sitedesc: str | None = None,
    separator: str = "|",
    excerpt: str | None = None,
    focus_keyword: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    modified: str | None = None,
    currentdate: str | None = None,
    currenttime: str | None = None,
    page: str | None = None,
    pagenumber: str | None = None,
    search_query: str | None = None,
    resource_id: str | None = None,
    filename: str | None = None,
    parent_title: str | None = None,
    custom_fields: dict[str, str] | None = None,
    terms: dict[str, str] | None = None,
    random_words: Callable[[str | None], str] | None = None,
) -> dict[str, Callable[[str | None], str]]:
    """The standard variable vocabulary, from plain values.

    Every caller (preview, settings UI, storefront resolution) builds the
    context through this one function, so the variable list cannot drift
    between what the settings screen offers and what the renderer knows.
    """
    fields = {k.lower(): v for k, v in (custom_fields or {}).items()}
    term_map = {k.lower(): v for k, v in (terms or {}).items()}

    def const(value: str | None) -> Callable[[str | None], str]:
        return lambda _param: value or ""

    def wrap(fn: Callable[[str], str]) -> Callable[[str | None], str]:
        return lambda param: fn(param or "")

    def customfield(param: str | None) -> str:
        return fields.get((param or "").strip().lower(), "")

    def term(param: str | None) -> str:
        return term_map.get((param or "").strip().lower(), "")

    return {
        "title": const(title),
        "sitename": const(sitename),
        "sitedesc": const(sitedesc),
        "sep": const(separator),
        "excerpt": const(excerpt),
        "focuskw": const(focus_keyword),
        "category": const(category),
        "tag": const(tag),
        "author": const(author),
        "modified": const(modified),
        "currentdate": const(currentdate),
        "currenttime": const(currenttime),
        "page": const(page),
        "pagenumber": const(pagenumber),
        "search_query": const(search_query),
        "id": const(resource_id),
        "filename": const(filename),
        "parent_title": const(parent_title),
        "customfield": customfield,
        "term": term,
        "ucwords": wrap(_ucwords),
        "lowercase": wrap(str.lower),
        "uppercase": wrap(str.upper),
        "randomword": random_words or (lambda _param: ""),
    }


#: The variable list shown in the settings UI, with example output. Kept here
#: (not in the frontend) so the UI and the renderer cannot disagree.
VARIABLE_CATALOG: tuple[dict[str, str], ...] = (
    {"name": "%title%", "label": "عنوان مطلب", "example": "راهنمای خرید"},
    {"name": "%sep%", "label": "جداکننده", "example": "|"},
    {"name": "%sitename%", "label": "نام سایت", "example": "فروشگاه"},
    {"name": "%sitedesc%", "label": "توضیح سایت", "example": "یک سایت فروشگاهی"},
    {"name": "%excerpt%", "label": "خلاصه", "example": "در این مطلب..."},
    {"name": "%focuskw%", "label": "کلمه کانونی", "example": "خرید آنلاین"},
    {"name": "%category%", "label": "دسته‌بندی", "example": "آموزش"},
    {"name": "%tag%", "label": "برچسب", "example": "راهنما"},
    {"name": "%author%", "label": "نویسنده", "example": "علی"},
    {"name": "%modified%", "label": "تاریخ آخرین ویرایش", "example": "1405/07/17"},
    {"name": "%currentdate%", "label": "تاریخ امروز", "example": "1405/07/17"},
    {"name": "%currenttime%", "label": "ساعت", "example": "14:30"},
    {"name": "%page%", "label": "شماره صفحه", "example": "2"},
    {"name": "%pagenumber%", "label": "شماره صفحه (متنی)", "example": "صفحه 2"},
    {"name": "%search_query%", "label": "عبارت جست‌وجو", "example": "کفش"},
    {"name": "%id%", "label": "شناسه", "example": "42"},
    {"name": "%filename%", "label": "نام فایل (پیوست)", "example": "photo"},
    {"name": "%parent_title%", "label": "عنوان والد", "example": "دسته مادر"},
    {"name": "%customfield(نام)%", "label": "فیلد سفارشی", "example": "مقدار فیلد"},
    {"name": "%term(نام)%", "label": "ترم تاکسونومی", "example": "نام ترم"},
    {"name": "%ucwords(...)%", "label": "حروف اول بزرگ", "example": "عنوان بزرگ"},
    {"name": "%lowercase(...)%", "label": "حروف کوچک", "example": "عنوان"},
    {"name": "%uppercase(...)%", "label": "حروف بزرگ", "example": "عنوان"},
    {"name": "%randomword(الف|ب)%", "label": "کلمه تصادفی", "example": "الف"},
)
