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
    from app.shared.content.heading_normalizer import demote_body_h1
    from app.shared.content.shortcodes import process_shortcodes_async
    from app.shared.content.text_filters import wpautop_texturize_emoji
    from app.shared.content.toc import add_toc_links

    expanded = await ReusableBlockService(db).expand(
        html, include_unpublished=include_unpublished
    )
    expanded = await process_shortcodes_async(db, expanded)
    # Text filters run last, exactly as ``the_content`` does in
    # wp-includes/default-filters.php: after the block and shortcode expansion, so
    # the prose that comes out of a reusable block is typeset too. Before it
    # would type-set the ``[block slug="…"]`` tokens themselves, and after it
    # would retype a shortcode's own markup.
    filtered = wpautop_texturize_emoji(expanded)
    # A migrated body often opens with its own <h1> (the source article's
    # title lived inside the content), which would give the page two H1s —
    # the template already renders the post title as one. Demote the body's
    # H1 to H2 so the page has exactly one page title. Runs before the ToC
    # pass so the demoted heading is still a ToC target.
    filtered = demote_body_h1(filtered)
    # The ToC pass runs after the text filters: it compares heading text to
    # list items, and the filters (paragraph wrapping, entity decoding) are
    # what make the two comparable. It adds `id`s to headings and wraps
    # matching list items in anchor links — the "click a ToC entry and land
    # on the section" behavior a migrated WordPress article's list lacks.
    return add_toc_links(filtered)
