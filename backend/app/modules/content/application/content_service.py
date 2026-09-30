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


async def list_all_homepage_blocks(
    db: AsyncSession,
) -> list[HomepageBlock]:
    """Admin listing: every block, active or not, in display order."""
    stmt = select(HomepageBlock).order_by(
        HomepageBlock.position.asc(), HomepageBlock.created_at.asc()
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

    await logger.ainfo(
        "homepage_block_created",
        block_id=str(block.id),
        title=clean_title,
        type=block_type.value,
    )
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


def _nest_menu_items(
    items: list[SiteMenu],
    parent_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
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
    stmt = select(FAQItem).where(FAQItem.is_active.is_(True)).order_by(FAQItem.position.asc())
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


# ── Admin updates / deletes (Strapi content-manager parity) ───────────────


async def update_homepage_block(
    db: AsyncSession,
    block_id: uuid.UUID,
    *,
    title: str | None = None,
    config: dict[str, Any] | None = None,
    position: int | None = None,
    is_active: bool | None = None,
) -> HomepageBlock:
    """Partially update a homepage block; only provided fields change."""
    block = await db.get(HomepageBlock, block_id)
    if not block:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("HomepageBlock", f"Block {block_id} not found")
    if title is not None:
        clean = title.strip()
        if not clean:
            raise ValidationError("عنوان بلوک الزامی است")
        block.title = clean
    if config is not None:
        block.config = config
    if position is not None:
        block.position = position
    if is_active is not None:
        block.is_active = is_active
    await db.flush()
    await logger.ainfo("homepage_block_updated", block_id=str(block_id))
    return block


async def delete_homepage_block(db: AsyncSession, block_id: uuid.UUID) -> None:
    """Delete a homepage block (the storefront falls back to default sections)."""
    block = await db.get(HomepageBlock, block_id)
    if not block:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("HomepageBlock", f"Block {block_id} not found")
    await db.delete(block)
    await db.flush()
    await logger.ainfo("homepage_block_deleted", block_id=str(block_id))


async def update_menu_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    *,
    title: str | None = None,
    url: str | None = None,
    position: int | None = None,
    icon: str | None = None,
    is_active: bool | None = None,
) -> SiteMenu:
    """Partially update a navigation item."""
    item = await db.get(SiteMenu, item_id)
    if not item:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("SiteMenu", f"Menu item {item_id} not found")
    if title is not None:
        clean = title.strip()
        if not clean:
            raise ValidationError("عنوان پیوند منو الزامی است")
        item.title = clean
    if url is not None:
        clean_url = url.strip()
        if not clean_url:
            raise ValidationError("آدرس پیوند منو الزامی است")
        item.url = clean_url
    if position is not None:
        item.position = position
    if icon is not None:
        item.icon = icon
    if is_active is not None:
        item.is_active = is_active
    await db.flush()
    await logger.ainfo("menu_item_updated", item_id=str(item_id))
    return item


async def delete_menu_item(db: AsyncSession, item_id: uuid.UUID) -> None:
    """Delete a menu item; children are cascade-deleted by the FK."""
    item = await db.get(SiteMenu, item_id)
    if not item:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("SiteMenu", f"Menu item {item_id} not found")
    await db.delete(item)
    await db.flush()
    await logger.ainfo("menu_item_deleted", item_id=str(item_id))


async def update_faq(
    db: AsyncSession,
    faq_id: uuid.UUID,
    *,
    question: str | None = None,
    answer_html: str | None = None,
    category: str | None = None,
    position: int | None = None,
    is_active: bool | None = None,
) -> FAQItem:
    """Partially update an FAQ entry."""
    faq = await db.get(FAQItem, faq_id)
    if not faq:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("FAQItem", f"FAQ {faq_id} not found")
    if question is not None:
        clean = question.strip()
        if not clean:
            raise ValidationError("سوال الزامی است")
        faq.question = clean
    if answer_html is not None:
        faq.answer_html = answer_html
    if category is not None:
        faq.category = category.strip()
    if position is not None:
        faq.position = position
    if is_active is not None:
        faq.is_active = is_active
    await db.flush()
    await logger.ainfo("faq_updated", faq_id=str(faq_id))
    return faq


async def delete_faq(db: AsyncSession, faq_id: uuid.UUID) -> None:
    """Delete an FAQ entry."""
    faq = await db.get(FAQItem, faq_id)
    if not faq:
        from app.core.exceptions.handlers import NotFoundError

        raise NotFoundError("FAQItem", f"FAQ {faq_id} not found")
    await db.delete(faq)
    await db.flush()
    await logger.ainfo("faq_deleted", faq_id=str(faq_id))
