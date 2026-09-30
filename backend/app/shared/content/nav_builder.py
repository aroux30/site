"""Navigation builder data model: drag & drop menu construction (WordPress parity).

The existing SiteMenu model already supports hierarchical parent-child menus.
This service adds the builder-specific operations: reorder, nest, bulk update.

Usage:
    from app.shared.content.nav_builder import NavBuilderService
    tree = await NavBuilderService.get_menu_tree(db, location="header_main")
    await NavBuilderService.reorder(db, location, ordered_ids)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, update

from app.modules.content.domain.models import MenuLocation, SiteMenu

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class NavBuilderService:
    """Drag & drop menu construction operations."""

    @staticmethod
    async def get_menu_tree(
        db: "AsyncSession",
        location: str,
    ) -> list[dict[str, Any]]:
        """Get a hierarchical menu tree for a location."""
        stmt = (
            select(SiteMenu)
            .where(SiteMenu.location == location, SiteMenu.is_active.is_(True))
            .order_by(SiteMenu.position.asc())
        )
        items = (await db.execute(stmt)).scalars().all()

        # Build tree
        items_by_id: dict[uuid.UUID, dict[str, Any]] = {}
        roots: list[dict[str, Any]] = []

        for item in items:
            node = {
                "id": str(item.id),
                "title": item.title,
                "url": item.url,
                "icon": item.icon,
                "position": item.position,
                "parent_id": str(item.parent_id) if item.parent_id else None,
                "children": [],
            }
            items_by_id[item.id] = node

        for item in items:
            node = items_by_id[item.id]
            if item.parent_id and item.parent_id in items_by_id:
                items_by_id[item.parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    @staticmethod
    async def reorder(
        db: "AsyncSession",
        location: str,
        ordered_items: list[dict[str, Any]],
    ) -> int:
        """Reorder and re-nest menu items from a drag & drop operation.

        Each item in ordered_items: {"id": "...", "parent_id": "..." or null, "position": int}
        """
        updated = 0
        for item_data in ordered_items:
            item_id = uuid.UUID(item_data["id"])
            parent_id = uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None
            position = item_data.get("position", 0)

            stmt = (
                update(SiteMenu)
                .where(SiteMenu.id == item_id)
                .values(parent_id=parent_id, position=position)
            )
            await db.execute(stmt)
            updated += 1

        await db.commit()
        logger.info("menu_reordered", location=location, items=updated)
        return updated

    @staticmethod
    async def add_item(
        db: "AsyncSession",
        location: str,
        title: str,
        url: str,
        *,
        parent_id: uuid.UUID | None = None,
        icon: str | None = None,
        position: int = 0,
    ) -> dict[str, Any]:
        """Add a new menu item."""
        try:
            loc = MenuLocation(location)
        except ValueError:
            loc = MenuLocation.HEADER_MAIN

        item = SiteMenu(
            location=loc,
            title=title,
            url=url,
            parent_id=parent_id,
            icon=icon,
            position=position,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return {"id": str(item.id), "title": item.title, "url": item.url}

    @staticmethod
    async def delete_item(db: "AsyncSession", item_id: uuid.UUID) -> bool:
        """Delete a menu item (children cascade)."""
        item = await db.get(SiteMenu, item_id)
        if not item:
            return False
        await db.delete(item)
        await db.commit()
        return True
