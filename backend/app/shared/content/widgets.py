"""Widget areas: configurable content zones (WordPress sidebar/footer parity).

Defines widget areas (sidebar, footer columns, header) and the widgets
placed in them. Each widget has a type (text, recent_posts, categories, etc.)
and a JSONB config for its content/settings.

This is stored in the site_options table as JSON, not separate tables,
matching WordPress's approach of serializing widget settings as options.

Usage:
    from app.shared.content.widgets import WidgetService
    areas = await WidgetService.get_all_areas(db)
    await WidgetService.update_area(db, "sidebar", widgets=[...])
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import structlog

from app.modules.settings.application.site_options_service import SiteOptionsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Default widget areas
DEFAULT_AREAS = {
    "sidebar": {"name": "Sidebar", "description": "Main sidebar", "widgets": []},
    "footer_1": {"name": "Footer Column 1", "description": "First footer column", "widgets": []},
    "footer_2": {"name": "Footer Column 2", "description": "Second footer column", "widgets": []},
    "footer_3": {"name": "Footer Column 3", "description": "Third footer column", "widgets": []},
    "header_top": {"name": "Header Top Bar", "description": "Above main navigation", "widgets": []},
}

# Available widget types
WIDGET_TYPES = {
    "text": {"name": "Text", "description": "Custom text/HTML content"},
    "recent_posts": {"name": "Recent Posts", "description": "List of recent blog posts"},
    "categories": {"name": "Categories", "description": "Blog category list"},
    "tags": {"name": "Tag Cloud", "description": "Blog tag cloud"},
    "search": {"name": "Search", "description": "Search box"},
    "menu": {"name": "Navigation Menu", "description": "Custom menu"},
    "image": {"name": "Image", "description": "Single image with optional link"},
    "social_links": {"name": "Social Links", "description": "Social media icon links"},
    "newsletter": {"name": "Newsletter", "description": "Email subscription form"},
    "custom_html": {"name": "Custom HTML", "description": "Arbitrary HTML block"},
    # WordPress core widgets that were missing (the storefront renders each in
    # widget-area.tsx). Added so an operator can place the standard set without
    # a code change — the point of the widget screen.
    "archives": {"name": "Archives", "description": "Monthly blog archive links"},
    "calendar": {"name": "Calendar", "description": "Month calendar of published posts"},
    "recent_comments": {"name": "Recent Comments", "description": "Most recent comments"},
    "pages": {"name": "Pages", "description": "List of published CMS pages"},
    "meta": {"name": "Meta", "description": "Login, feed and admin links"},
    "rss": {"name": "RSS", "description": "Link to an RSS feed"},
    "links": {"name": "Links / Blogroll", "description": "List of custom links"},
    # A blank spacing widget (no visible output), matched to the storefront's
    # existing `spacer` filter so a layout can be fine-tuned without markup.
    "spacer": {"name": "Spacer", "description": "Empty vertical gap"},
}

#: Config keys each widget type understands, with a friendly label and kind.
#: The admin form renders one control per entry instead of the two-field
#: title/content form, so a "recent posts" widget can set its count and a
#: "recent comments" widget its limit. Kind drives the control: "text",
#: "number", "bool", "select" (with `options`), or "textarea".
WIDGET_CONFIG_SCHEMA: dict[str, list[dict[str, Any]]] = {
    "text": [{"key": "content", "label": "متن", "kind": "textarea"}],
    "custom_html": [{"key": "content", "label": "HTML", "kind": "textarea"}],
    "image": [
        {"key": "url", "label": "آدرس تصویر", "kind": "text"},
        {"key": "link", "label": "پیوند (اختیاری)", "kind": "text"},
    ],
    "recent_posts": [{"key": "count", "label": "تعداد", "kind": "number", "min": 1, "max": 50}],
    "categories": [{"key": "count", "label": "تعداد", "kind": "number", "min": 1, "max": 50}],
    "tags": [{"key": "count", "label": "تعداد", "kind": "number", "min": 1, "max": 100}],
    "recent_comments": [
        {"key": "count", "label": "تعداد", "kind": "number", "min": 1, "max": 50},
    ],
    "archives": [
        {"key": "count", "label": "تعداد ماه", "kind": "number", "min": 1, "max": 24},
        {
            "key": "type",
            "label": "نمایش",
            "kind": "select",
            "options": [
                {"value": "monthly", "label": "ماهانه"},
                {"value": "yearly", "label": "سالانه"},
            ],
        },
    ],
    "pages": [
        {"key": "count", "label": "تعداد", "kind": "number", "min": 1, "max": 100},
        {"key": "sortby", "label": "ترتیب", "kind": "select", "options": [
            {"value": "title", "label": "عنوان"},
            {"value": "menu_order", "label": "ترتیب منو"},
        ]},
    ],
    "links": [{"key": "items", "label": "پیوندها", "kind": "links"}],
    "social_links": [{"key": "items", "label": "شبکه‌ها", "kind": "links"}],
    "menu": [{"key": "items", "label": "آیتم‌ها", "kind": "links"}],
    "newsletter": [{"key": "source", "label": "برچسب منبع", "kind": "text"}],
    "rss": [
        {"key": "url", "label": "آدرس فید", "kind": "text"},
        {"key": "title", "label": "عنوان پیوند", "kind": "text"},
    ],
    "calendar": [],
    "search": [],
    "meta": [],
    "spacer": [],
}

WIDGET_OPTIONS_KEY = "widget_areas"

#: An area id is rendered into a storefront layout call, so it must be a slug.
_AREA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _sanitise_widgets(widgets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean every ``custom_html`` body on the way into storage.

    Returns copies rather than mutating the caller's dictionaries: the route
    passes the parsed request body, and mutating it in place would mean a caller
    that also logged the request — or retried it — saw a different value from the
    one it sent. The stored copy is the clean one either way; being surprised by
    your own payload is not worth it.

    Only the HTML body is touched. Every other field is plain text the storefront
    already renders escaped, and running them through an HTML sanitizer would
    mangle them: a `text` widget whose content is "a < b" would come back
    altered for no benefit.
    """
    from app.shared.content.html_sanitizer import sanitize_html

    cleaned: list[dict[str, Any]] = []
    for widget in widgets:
        if not isinstance(widget, dict):
            continue
        if widget.get("type") != "custom_html":
            cleaned.append(dict(widget))
            continue

        copy = dict(widget)
        config = copy.get("config")
        if isinstance(config, dict) and isinstance(config.get("content"), str):
            config = dict(config)
            config["content"] = sanitize_html(config["content"])
            copy["config"] = config
        cleaned.append(copy)
    return cleaned


class WidgetService:
    """Manage widget areas and their contents."""

    @staticmethod
    async def get_all_areas(db: "AsyncSession") -> dict[str, Any]:
        """Get all widget areas with their widgets."""
        raw = await SiteOptionsService.get(db, WIDGET_OPTIONS_KEY)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return DEFAULT_AREAS.copy()

    @staticmethod
    async def get_area(db: "AsyncSession", area_id: str) -> dict[str, Any] | None:
        """Get a single widget area."""
        areas = await WidgetService.get_all_areas(db)
        return areas.get(area_id)

    @staticmethod
    async def update_area(
        db: "AsyncSession",
        area_id: str,
        widgets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update widgets in a specific area.

        A ``custom_html`` widget's markup is sanitized **here**, on the way into
        the database, rather than in the storefront before it renders. That
        ordering is the whole point:

          - the value in ``site_options`` is then already safe, so any future
            reader of that row — a new render path, an export, a support tool, a
            raw ``psql`` session — sees sanitized markup without having to know
            to clean it first
          - the storefront can render the stored value directly instead of
            trusting it, which is what lets it use ``dangerouslySetInnerHTML``
            without becoming a stored-XSS vector

        Sanitizing on read instead would leave an unsanitized value in the
        database and push the guarantee onto every consumer, which is how the
        next consumer forgets.
        """
        areas = await WidgetService.get_all_areas(db)
        if area_id not in areas:
            areas[area_id] = {"name": area_id, "description": "", "widgets": []}
        areas[area_id]["widgets"] = _sanitise_widgets(widgets)
        await SiteOptionsService.set(db, WIDGET_OPTIONS_KEY, json.dumps(areas, ensure_ascii=False))
        logger.info("widgets_updated", area=area_id, count=len(widgets))
        return areas[area_id]

    @staticmethod
    def list_widget_types() -> dict[str, Any]:
        """List available widget types."""
        return WIDGET_TYPES.copy()

    @staticmethod
    async def create_area(
        db: "AsyncSession",
        area_id: str,
        *,
        name: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Register a new widget area so an operator can place widgets in it.

        WordPress lets an operator register widget areas from a screen rather
        than only in theme code; here the areas were a fixed dict, so a new
        column could only be added by a developer. ``area_id`` is the key the
        storefront layout passes to ``<WidgetArea area=...>``, so it is
        constrained to a slug — a space or a slash could never be rendered.

        Reuses an existing area's widgets when the id already exists: this is an
        upsert of the *metadata*, not a way to silently drop a populated area.
        """
        cleaned = area_id.strip()
        if not cleaned or not _AREA_ID_RE.match(cleaned):
            raise ValueError(
                "شناسهٔ ناحیه باید فقط حروف، رقم، - و _ باشد"
            )
        areas = await WidgetService.get_all_areas(db)
        existing = areas.get(cleaned) or {}
        areas[cleaned] = {
            "name": name.strip() or cleaned,
            "description": description.strip(),
            "widgets": existing.get("widgets", []),
        }
        await SiteOptionsService.set(
            db, WIDGET_OPTIONS_KEY, json.dumps(areas, ensure_ascii=False)
        )
        logger.info("widget_area_created", area=cleaned)
        return areas[cleaned]

    @staticmethod
    async def delete_area(db: "AsyncSession", area_id: str) -> bool:
        """Remove a widget area. Refuses the built-in areas the layout hardcodes.

        Deleting ``sidebar`` would empty a column the storefront still renders;
        the built-ins are the layout's fixed contract, so only operator-created
        areas can be removed.
        """
        areas = await WidgetService.get_all_areas(db)
        if area_id not in areas:
            return False
        if area_id in DEFAULT_AREAS:
            raise ValueError("ناحیه‌های پیش‌فرض قابل حذف نیستند")
        del areas[area_id]
        await SiteOptionsService.set(
            db, WIDGET_OPTIONS_KEY, json.dumps(areas, ensure_ascii=False)
        )
        logger.info("widget_area_deleted", area=area_id)
        return True
