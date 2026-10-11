"""Titles & Meta — default template resolution per content type.

Rank Math's Titles & Meta panel: one title/description template per content
type (post, page, product, category, tag, author, archive), plus the global
separator. Before this module the defaults were hardcoded f-strings
(``f"{post.title} | وبلاگ"``) so an operator could not change a suffix without
a deploy — and the site option keys the seom1 migration *claimed* the panel
writes (``seo_default_title_template``) were read by nothing.

Storage: ``site_options`` keys, one pair per content type:

    seo_default_title_template_<type>
    seo_default_description_template_<type>

with ``<type>`` one of: post, page, product, category, tag, author, archive,
home. Plus the global ``seo_title_separator`` (default "|"). Missing rows fall
back to the built-in defaults below — the same strings the code used to
hardcode, now expressed as templates.

The renderer is ``template_engine.TemplateEngine``; this module only owns the
option reading and the default vocabulary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.seo.application.template_engine import TemplateEngine, build_variables

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Content types the panel exposes. The order is the UI order.
CONTENT_TYPES: tuple[str, ...] = (
    "post",
    "page",
    "product",
    "category",
    "tag",
    "author",
    "archive",
    "home",
)

#: Built-in defaults — what the code hardcoded before the templates existed.
#: An operator can override any of these; clearing an override restores these.
DEFAULT_TITLE_TEMPLATES: dict[str, str] = {
    "post": "%title% %sep% %sitename%",
    "page": "%title% %sep% %sitename%",
    "product": "%title% %sep% خرید و بررسی",
    "category": "%title% %sep% %sitename%",
    "tag": "%title% %sep% %sitename%",
    "author": "نوشته‌های %title% %sep% %sitename%",
    "archive": "%title% %sep% %sitename%",
    "home": "%sitename% %sep% %sitedesc%",
}

DEFAULT_DESCRIPTION_TEMPLATES: dict[str, str] = {
    "post": "%excerpt%",
    "page": "%excerpt%",
    "product": "%excerpt%",
    "category": "بهترین قیمت و مشخصات محصولات %title%",
    "tag": "مطالب مرتبط با %title%",
    "author": "همهٔ نوشته‌های %title%",
    "archive": "آرشیو %title%",
    "home": "%sitedesc%",
}

DEFAULT_SEPARATOR = "|"

#: Keys an operator may set. Exposed so the settings API can validate writes
#: instead of accepting any typo'd key silently.
def title_option_key(content_type: str) -> str:
    return f"seo_default_title_template_{content_type}"


def description_option_key(content_type: str) -> str:
    return f"seo_default_description_template_{content_type}"


class TitlesMetaService:
    """Resolves the operator's default templates against a content context."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._cache: dict[str, str] | None = None

    async def _options(self) -> dict[str, str]:
        """Read every template option once per service instance.

        Site options have no cache layer (documented in
        ``site_options_service``), and resolving one page's metadata would
        otherwise read 20 keys one by one — so this instance caches the map it
        needs. The service lives for one request; a settings change applies to
        the next request.
        """
        if self._cache is not None:
            return self._cache
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        values: dict[str, str] = {}
        try:
            # blogname/blogdescription feed %sitename%/%sitedesc% — reading
            # them here (not at the call sites) is what makes every caller get
            # a complete render without remembering to pass site identity.
            keys = ["seo_title_separator", "blogname", "blogdescription"]
            for t in CONTENT_TYPES:
                keys.append(title_option_key(t))
                keys.append(description_option_key(t))
            for key in keys:
                value = await SiteOptionsService.get(self.db, key)
                if value:
                    values[key] = value
        except Exception:
            logger.warning("titles_meta_options_read_failed")
        self._cache = values
        return values

    async def separator(self) -> str:
        options = await self._options()
        return options.get("seo_title_separator") or DEFAULT_SEPARATOR

    async def title_template(self, content_type: str) -> str:
        options = await self._options()
        return options.get(title_option_key(content_type)) or DEFAULT_TITLE_TEMPLATES.get(
            content_type, "%title% %sep% %sitename%"
        )

    async def description_template(self, content_type: str) -> str:
        options = await self._options()
        return options.get(
            description_option_key(content_type)
        ) or DEFAULT_DESCRIPTION_TEMPLATES.get(content_type, "%excerpt%")

    async def resolve(
        self,
        content_type: str,
        *,
        title: str | None = None,
        excerpt: str | None = None,
        focus_keyword: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        author: str | None = None,
        modified: str | None = None,
        currentdate: str | None = None,
        currenttime: str | None = None,
        resource_id: str | None = None,
        filename: str | None = None,
        parent_title: str | None = None,
        custom_fields: dict[str, str] | None = None,
        terms: dict[str, str] | None = None,
        sitename: str | None = None,
        sitedesc: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Render (title, description) for one resource of *content_type*.

        Returns ``(None, None)`` when the caller passed no title at all — an
        entity with no title has no meaningful meta, and inventing one would
        be worse than the caller's own fallback.
        """
        if not title:
            return None, None

        options = await self._options()
        separator = options.get("seo_title_separator") or DEFAULT_SEPARATOR
        # Site identity from the options when the caller did not override it.
        effective_sitename = sitename or options.get("blogname") or ""
        effective_sitedesc = sitedesc or options.get("blogdescription") or ""
        variables = build_variables(
            title=title,
            sitename=effective_sitename,
            sitedesc=effective_sitedesc,
            separator=separator,
            excerpt=excerpt,
            focus_keyword=focus_keyword,
            category=category,
            tag=tag,
            author=author,
            modified=modified,
            currentdate=currentdate,
            currenttime=currenttime,
            resource_id=resource_id,
            filename=filename,
            parent_title=parent_title,
            custom_fields=custom_fields,
            terms=terms,
        )
        engine = TemplateEngine(variables)

        title_template = await self.title_template(content_type)
        description_template = await self.description_template(content_type)

        resolved_title = engine.render_or_default(
            title_template,
            f"{title} {separator} {effective_sitename}".strip(),
        )
        resolved_description = engine.render_or_default(
            description_template,
            excerpt or title,
        )
        return resolved_title, resolved_description
