"""Render stored CMS body HTML for display.

Bodies are stored as authored — with ``[block slug="…"]`` references and
shortcode tokens intact. Rendering happens on read, mirroring WordPress's
``the_content`` filter, which is what lets an edit to a reusable block or a
shortcode's behaviour reach every page that already embeds it.

Order matters: reusable blocks expand *first*, so a block whose body itself
contains shortcodes still gets them rendered, and a shortcode cannot smuggle
in a block reference that was never checked against the blocks table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def render_body(
    db: AsyncSession,
    html: str | None,
    *,
    include_unpublished: bool = False,
) -> str:
    """Expand reusable blocks and run shortcodes over a stored body.

    ``include_unpublished`` is for admin preview: it lets an editor see a
    draft block in place instead of staring at the raw token.
    """
    from app.modules.content.application.reusable_block_service import (
        ReusableBlockService,
    )
    from app.shared.content.shortcodes import process_shortcodes_async

    expanded = await ReusableBlockService(db).expand(
        html, include_unpublished=include_unpublished
    )
    return await process_shortcodes_async(db, expanded)
