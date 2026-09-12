"""Content API routes: Homepage Blocks, Tree Menus, and FAQs with Google Schema (Karta Phase
7/9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.content.application import content_service
from app.modules.content.domain.models import MenuLocation
from app.modules.content.schemas.content import (
    BlockReorderRequest,
    FAQItemCreateRequest,
    FAQItemResponse,
    FAQListWithGoogleSchemaResponse,
    HomepageBlockCreateRequest,
    HomepageBlockResponse,
    MenuItemCreateRequest,
    MenuItemResponse,
    TreeMenuItemNode,
)

router = APIRouter(tags=["content"])


# ── Homepage Blocks Endpoints ─────────────────────────────────────────────


@router.get(
    "/blocks",
    response_model=list[HomepageBlockResponse],
    summary="Get active homepage layout blocks ordered by position",
)
async def get_homepage_blocks(
    db: AsyncSession = Depends(get_db),
) -> list[HomepageBlockResponse]:
    blocks = await content_service.get_active_homepage_blocks(db)
    return [HomepageBlockResponse.model_validate(b) for b in blocks]


@router.post(
    "/admin/blocks",
    response_model=HomepageBlockResponse,
    summary="Create a new homepage block (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_block(
    body: HomepageBlockCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> HomepageBlockResponse:
    block = await content_service.create_homepage_block(
        db,
        title=body.title,
        block_type=body.block_type,
        config=body.config,
        position=body.position,
    )
    return HomepageBlockResponse.model_validate(block)


@router.put(
    "/admin/blocks/reorder",
    response_model=list[HomepageBlockResponse],
    summary="Reorder homepage blocks display positions (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def reorder_blocks(
    body: BlockReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> list[HomepageBlockResponse]:
    blocks = await content_service.reorder_homepage_blocks(db, positions=body.positions)
    return [HomepageBlockResponse.model_validate(b) for b in blocks]


# ── Hierarchical Tree Menus Endpoints ─────────────────────────────────────


@router.get(
    "/menus/{location}",
    response_model=list[TreeMenuItemNode],
    summary="Get hierarchical navigation tree for a location (header, footer, mobile)",
)
async def get_tree_menu(
    location: MenuLocation,
    db: AsyncSession = Depends(get_db),
) -> list[TreeMenuItemNode]:
    tree = await content_service.build_tree_menu(db, location=location)
    return [TreeMenuItemNode.model_validate(node) for node in tree]


@router.post(
    "/admin/menus",
    response_model=MenuItemResponse,
    summary="Add a menu navigation link (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_menu_item(
    body: MenuItemCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    item = await content_service.create_menu_item(
        db,
        location=body.location,
        title=body.title,
        url=body.url,
        parent_id=body.parent_id,
        position=body.position,
        icon=body.icon,
    )
    return MenuItemResponse.model_validate(item)


# ── FAQs with Automated Google FAQPage Schema.org ─────────────────────────


@router.get(
    "/faqs",
    response_model=FAQListWithGoogleSchemaResponse,
    summary="Get active FAQs with automated Google FAQPage Schema.org JSON-LD for rich snippets",
)
async def get_faqs(
    category: str | None = Query(None, description="Filter FAQs by category"),
    db: AsyncSession = Depends(get_db),
) -> FAQListWithGoogleSchemaResponse:
    res = await content_service.get_active_faqs_with_schema(db, category=category)
    return FAQListWithGoogleSchemaResponse(
        items=[FAQItemResponse.model_validate(f) for f in res["items"]],
        total=res["total"],
        schema_json_ld=res["schema_json_ld"],
    )


@router.post(
    "/admin/faqs",
    response_model=FAQItemResponse,
    summary="Create a new FAQ entry (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_faq(
    body: FAQItemCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> FAQItemResponse:
    from app.modules.content.domain.models import FAQItem

    faq = FAQItem(
        question=body.question.strip(),
        answer_html=body.answer_html,
        category=body.category.strip(),
        position=body.position,
        is_active=True,
    )
    db.add(faq)
    await db.flush()
    return FAQItemResponse.model_validate(faq)
