"""Content management, homepage blocks, tree menus, and FAQ Schema service (Karta Phase 7/9).

Implements:
- Homepage blocks retrieval and drag-and-drop reordering (Karta blocks)
- Multi-location tree menu builder with recursive nesting (Karta menus)
- FAQ management with automated Google FAQPage JSON-LD structured data generation (Karta faqs)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.content.domain.models import (
    BlockType,
    FAQItem,
    HomepageBlock,
    MenuLocation,
    SiteMenu,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Homepage Blocks Management (Karta blocks) ─────────────────────────────


async def get_active_homepage_blocks(
    db: AsyncSession,
) -> list[HomepageBlock]:
    """Retrieve all active homepage blocks ordered by display position."""
    stmt = (
        select(HomepageBlock)
        .where(HomepageBlock.is_active.is_(True))
        .order_by(HomepageBlock.position.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_homepage_block(
    db: AsyncSession,
    title: str,
    block_type: BlockType,
    config: dict[str, Any] | None = None,
    position: int = 0,
) -> HomepageBlock:
    """Admin creation of a dynamic homepage section."""
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("عنوان بلوک الزامی است")

    block = HomepageBlock(
        title=clean_title,
        block_type=block_type,
        config=config,
        position=position,
        is_active=True,
    )
    db.add(block)
    await db.flush()

    await logger.ainfo("homepage_block_created", block_id=str(block.id), title=clean_title, type=block_type.value)
    return block


async def reorder_homepage_blocks(
    db: AsyncSession,
    positions: dict[uuid.UUID, int],
) -> list[HomepageBlock]:
    """Update display order for multiple blocks simultaneously."""
    blocks = []
    for b_id, pos in positions.items():
        safe_id = uuid.UUID(str(b_id))
        block = await db.get(HomepageBlock, safe_id)
        if block:
            block.position = pos
            blocks.append(block)

    await db.flush()
    return blocks


# ── Hierarchical Tree Menus (Karta menus & menu_types) ────────────────────


def _nest_menu_items(items: list[SiteMenu], parent_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    """Recursively nest flat menu items into a parent-child tree."""
    tree = []
    children = [item for item in items if item.parent_id == parent_id]
    children.sort(key=lambda x: x.position)

    for child in children:
        sub_items = _nest_menu_items(items, parent_id=child.id)
        tree.append(
            {
                "id": child.id,
                "title": child.title,
                "url": child.url,
                "location": child.location.value,
                "position": child.position,
                "icon": child.icon,
                "children": sub_items,
            }
        )
    return tree


async def build_tree_menu(
    db: AsyncSession,
    location: MenuLocation = MenuLocation.HEADER_MAIN,
) -> list[dict[str, Any]]:
    """Build nested hierarchical navigation tree for a specific location."""
    stmt = (
        select(SiteMenu)
        .where(
            SiteMenu.location == location,
            SiteMenu.is_active.is_(True),
        )
        .order_by(SiteMenu.position.asc())
    )
    items = list((await db.execute(stmt)).scalars().all())
    return _nest_menu_items(items, parent_id=None)


async def create_menu_item(
    db: AsyncSession,
    location: MenuLocation,
    title: str,
    url: str,
    parent_id: uuid.UUID | None = None,
    position: int = 0,
    icon: str | None = None,
) -> SiteMenu:
    """Create a new navigation link in a menu location."""
    clean_title = title.strip()
    clean_url = url.strip()
    if not clean_title or not clean_url:
        raise ValidationError("عنوان و آدرس پیوند منو الزامی هستند")

    safe_parent = uuid.UUID(str(parent_id)) if parent_id else None

    item = SiteMenu(
        location=location,
        title=clean_title,
        url=clean_url,
        parent_id=safe_parent,
        position=position,
        icon=icon,
        is_active=True,
    )
    db.add(item)
    await db.flush()

    return item


# ── FAQs with Automated Google FAQPage Schema.org (Karta faqs) ────────────


def generate_google_faq_schema(faqs: list[FAQItem]) -> dict[str, Any]:
    """Generate compliant Schema.org JSON-LD structured data for Google Rich Snippets."""
    entities = []
    for faq in faqs:
        entities.append(
            {
                "@type": "Question",
                "name": faq.question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq.answer_html,
                },
            }
        )

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }


async def get_active_faqs_with_schema(
    db: AsyncSession,
    category: str | None = None,
) -> dict[str, Any]:
    """Retrieve active FAQs and attach valid Google FAQPage Schema.org JSON-LD."""
    stmt = (
        select(FAQItem)
        .where(FAQItem.is_active.is_(True))
        .order_by(FAQItem.position.asc())
    )
    all_faqs = list((await db.execute(stmt)).scalars().all())

    if category:
        clean_cat = category.strip().lower()
        faqs = [f for f in all_faqs if f.category.strip().lower() == clean_cat]
    else:
        faqs = all_faqs

    schema_json = generate_google_faq_schema(faqs)

    return {
        "items": faqs,
        "total": len(faqs),
        "schema_json_ld": schema_json,
    }
