"""Breadcrumb generation service (WordPress parity).

Generates hierarchical breadcrumb trails for blog posts, CMS pages,
categories, and tags. Returns structured data suitable for both
HTML rendering and Schema.org BreadcrumbList JSON-LD.

The home label and the blog-crumb toggle come from site options (Rank Math's
Breadcrumbs panel: `seo_breadcrumb_home_label`, `seo_breadcrumb_show_blog`),
read via `settings()` — callers that pass explicit values keep working, and
the visible trail and the JSON-LD share one source so they cannot disagree.

Usage:
    from app.shared.content.breadcrumbs import BreadcrumbService
    crumbs = await BreadcrumbService.for_blog_post(db, post)
    crumbs = await BreadcrumbService.for_cms_page(db, page)
    json_ld = BreadcrumbService.to_json_ld(crumbs, base_url="https://example.com")
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Breadcrumb:
    """Single breadcrumb item."""
    label: str
    url: str | None = None
    is_current: bool = False


async def settings(db: "AsyncSession") -> dict[str, Any]:
    """The breadcrumb options, resolved once per request.

    Fail-open with the built-in defaults: an options outage must not blank
    every trail on the site, and the defaults are what shipped before the
    options existed.
    """
    out: dict[str, Any] = {"home_label": "خانه", "show_blog": True, "separator": "/"}
    try:
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        home = await SiteOptionsService.get(db, "seo_breadcrumb_home_label")
        if home:
            out["home_label"] = home
        show_blog = await SiteOptionsService.get(db, "seo_breadcrumb_show_blog", "1")
        out["show_blog"] = show_blog not in ("0", "false", "False", "no")
        sep = await SiteOptionsService.get(db, "seo_breadcrumb_separator")
        if sep:
            out["separator"] = sep
    except Exception:
        pass
    return out


class BreadcrumbService:
    """Generate breadcrumb trails for various content types."""

    @staticmethod
    async def for_blog_post(
        db: "AsyncSession",
        *,
        title: str,
        slug: str,
        category_name: str | None = None,
        category_slug: str | None = None,
    ) -> list[Breadcrumb]:
        """Breadcrumbs for a blog post: Home > [Blog] > [Category] > Post.

        The Blog crumb is optional (operator option) — some shops prefer the
        flatter Home > Category > Post trail.
        """
        opts = await settings(db)
        crumbs = [Breadcrumb(label=opts["home_label"], url="/")]
        if opts["show_blog"]:
            crumbs.append(Breadcrumb(label="وبلاگ", url="/blog"))
        if category_name and category_slug:
            crumbs.append(Breadcrumb(label=category_name, url=f"/blog/category/{category_slug}"))
        crumbs.append(Breadcrumb(label=title, url=f"/blog/{slug}", is_current=True))
        return crumbs

    @staticmethod
    async def for_cms_page(
        db: "AsyncSession",
        *,
        page_id: uuid.UUID,
        title: str,
        slug: str,
    ) -> list[Breadcrumb]:
        """Breadcrumbs for a CMS page, resolving parent hierarchy."""
        from app.modules.content.domain.models import CmsPage

        opts = await settings(db)
        crumbs = [Breadcrumb(label=opts["home_label"], url="/")]

        # Walk up the parent chain
        ancestors: list[Breadcrumb] = []
        current_parent_id: uuid.UUID | None = None

        # Get this page's parent_id
        page = await db.get(CmsPage, page_id)
        if page:
            current_parent_id = getattr(page, "parent_id", None)

        # Walk up ancestors (max 10 levels to prevent infinite loops)
        visited: set[uuid.UUID] = set()
        for _ in range(10):
            if not current_parent_id or current_parent_id in visited:
                break
            visited.add(current_parent_id)
            parent = await db.get(CmsPage, current_parent_id)
            if not parent:
                break
            ancestors.insert(0, Breadcrumb(label=parent.title, url=f"/{parent.slug}"))
            current_parent_id = getattr(parent, "parent_id", None)

        crumbs.extend(ancestors)
        crumbs.append(Breadcrumb(label=title, url=f"/{slug}", is_current=True))
        return crumbs

    @staticmethod
    async def for_category(
        *,
        category_name: str,
        category_slug: str,
        home_label: str = "خانه",
    ) -> list[Breadcrumb]:
        """Breadcrumbs for a blog category archive."""
        return [
            Breadcrumb(label=home_label, url="/"),
            Breadcrumb(label="وبلاگ", url="/blog"),
            Breadcrumb(label=category_name, url=f"/blog/category/{category_slug}", is_current=True),
        ]

    @staticmethod
    async def for_tag(
        *, tag_name: str, tag_slug: str, home_label: str = "خانه"
    ) -> list[Breadcrumb]:
        """Breadcrumbs for a blog tag archive."""
        return [
            Breadcrumb(label=home_label, url="/"),
            Breadcrumb(label="وبلاگ", url="/blog"),
            Breadcrumb(label=tag_name, url=f"/blog/tag/{tag_slug}", is_current=True),
        ]

    @staticmethod
    def to_json_ld(crumbs: list[Breadcrumb], *, base_url: str = "") -> dict[str, Any]:
        """Convert breadcrumbs to Schema.org BreadcrumbList JSON-LD."""
        items = []
        for i, crumb in enumerate(crumbs, 1):
            item: dict[str, Any] = {
                "@type": "ListItem",
                "position": i,
                "name": crumb.label,
            }
            if crumb.url:
                item["item"] = f"{base_url.rstrip('/')}{crumb.url}"
            items.append(item)

        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items,
        }

    @staticmethod
    def to_html(crumbs: list[Breadcrumb]) -> str:
        """Render breadcrumbs as simple HTML."""
        parts: list[str] = []
        for crumb in crumbs:
            if crumb.is_current:
                parts.append(f'<span class="breadcrumb-current">{crumb.label}</span>')
            elif crumb.url:
                parts.append(f'<a href="{crumb.url}" class="breadcrumb-link">{crumb.label}</a>')
            else:
                parts.append(f'<span>{crumb.label}</span>')
        separator = ' <span class="breadcrumb-sep">/</span> '
        return f'<nav class="breadcrumbs" aria-label="breadcrumb">{separator.join(parts)}</nav>'
