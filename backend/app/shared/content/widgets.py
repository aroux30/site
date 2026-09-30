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
}

WIDGET_OPTIONS_KEY = "widget_areas"


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
        """Update widgets in a specific area."""
        areas = await WidgetService.get_all_areas(db)
        if area_id not in areas:
            areas[area_id] = {"name": area_id, "description": "", "widgets": []}
        areas[area_id]["widgets"] = widgets
        await SiteOptionsService.set(db, WIDGET_OPTIONS_KEY, json.dumps(areas, ensure_ascii=False))
        logger.info("widgets_updated", area=area_id, count=len(widgets))
        return areas[area_id]

    @staticmethod
    def list_widget_types() -> dict[str, Any]:
        """List available widget types."""
        return WIDGET_TYPES.copy()
