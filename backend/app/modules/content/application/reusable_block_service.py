"""Reusable block service: CRUD plus read-time expansion.

Expansion is deliberately a *read* concern. A page stores ``[block
slug="promo-banner"]``, and every read — storefront or admin preview —
resolves it against this table. Nothing is copied into the body, so editing
a block updates every page that embeds it, which is the whole point of a
synced pattern.

The token syntax is the project's existing shortcode grammar, so embedding a
block needs no new editor primitive: ``[block slug="…"]`` already parses.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ConflictError, NotFoundError
from app.modules.content.domain.reusable_blocks import (
    ReusableBlock,
    ReusableBlockStatus,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Matches [block slug="x"] / [block slug='x'] / [block name="x"].
_BLOCK_REF_RE = re.compile(
    r"\[block\s+(?:slug|name)=[\"']([^\"']+)[\"']\s*\]",
    re.IGNORECASE,
)

# A nested reference is inlined too, but a cycle (A embeds B, B embeds A)
# would recurse forever. Two levels covers legitimate composition and stops
# a self-reference cold.
_MAX_EXPANSION_DEPTH = 2


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9؀-ۿ]+", "-", value.strip().lower())
    return slug.strip("-")[:200] or "block"


class ReusableBlockService:
    """CRUD for reusable blocks and expansion of their references."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Reads ────────────────────────────────────────────────────────────

    async def list_blocks(
        self,
        *,
        status: ReusableBlockStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ReusableBlock]:
        stmt = select(ReusableBlock)
        if not include_deleted:
            stmt = stmt.where(ReusableBlock.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(ReusableBlock.status == status)
        stmt = stmt.order_by(ReusableBlock.name)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_block(self, block_id: uuid.UUID) -> ReusableBlock:
        block = await self.db.get(ReusableBlock, block_id)
        if block is None or block.deleted_at is not None:
            raise NotFoundError("ReusableBlock", f"Block {block_id} not found")
        return block

    async def get_by_slug(
        self,
        slug: str,
        *,
        only_published: bool = False,
    ) -> ReusableBlock | None:
        stmt = select(ReusableBlock).where(
            ReusableBlock.slug == slug,
            ReusableBlock.deleted_at.is_(None),
        )
        if only_published:
            stmt = stmt.where(
                ReusableBlock.status == ReusableBlockStatus.PUBLISHED,
                ReusableBlock.is_active.is_(True),
            )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Writes ───────────────────────────────────────────────────────────

    async def create_block(
        self,
        *,
        name: str,
        body_html: str,
        slug: str | None = None,
        description: str | None = None,
        status: ReusableBlockStatus = ReusableBlockStatus.DRAFT,
        author_id: uuid.UUID | None = None,
    ) -> ReusableBlock:
        resolved = _slugify(slug or name)
        existing = await self.db.execute(
            select(ReusableBlock).where(ReusableBlock.slug == resolved)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(detail=f"A block with slug '{resolved}' already exists")

        block = ReusableBlock(
            name=name.strip(),
            slug=resolved,
            body_html=body_html,
            description=description,
            status=status,
            author_id=author_id,
        )
        self.db.add(block)
        await self.db.flush()
        logger.info("reusable_block_created", block_id=str(block.id), slug=resolved)
        return block

    async def update_block(
        self,
        block_id: uuid.UUID,
        *,
        data: dict[str, Any],
    ) -> ReusableBlock:
        """Update a block. Edits propagate to every embedding page."""
        block = await self.get_block(block_id)
        for key, value in data.items():
            if value is not None and hasattr(block, key):
                setattr(block, key, value)
        await self.db.flush()
        logger.info("reusable_block_updated", block_id=str(block_id))
        return block

    async def delete_block(self, block_id: uuid.UUID) -> None:
        """Move to trash (restorable)."""
        block = await self.get_block(block_id)
        block.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def restore_block(self, block_id: uuid.UUID) -> ReusableBlock:
        block = await self.db.get(ReusableBlock, block_id)
        if block is None:
            raise NotFoundError("ReusableBlock", f"Block {block_id} not found")
        block.deleted_at = None
        await self.db.flush()
        return block

    async def hard_delete_block(self, block_id: uuid.UUID) -> None:
        """Permanently remove a block.

        Embedding pages keep their ``[block slug="…"]`` token and will render
        it literally — a visible dangling reference is better than silently
        deleting a fragment out of an editor's page.
        """
        block = await self.db.get(ReusableBlock, block_id)
        if block is None:
            raise NotFoundError("ReusableBlock", f"Block {block_id} not found")
        await self.db.delete(block)
        await self.db.flush()

    # ── Expansion ────────────────────────────────────────────────────────

    @staticmethod
    def referenced_slugs(html: str | None) -> list[str]:
        """Slugs referenced by a body, in order of first appearance."""
        if not html:
            return []
        seen: dict[str, None] = {}
        for match in _BLOCK_REF_RE.finditer(html):
            seen.setdefault(match.group(1), None)
        return list(seen)

    async def expand(
        self,
        html: str | None,
        *,
        include_unpublished: bool = False,
    ) -> str:
        """Replace every ``[block slug="…"]`` token with the block's body.

        Unresolvable references are left as the literal token: an editor
        who embeds a block that does not exist (or is not published) should
        see that in the output rather than get an unexplained gap.
        """
        if not html or "[block" not in html.lower():
            return html or ""

        return await self._expand(html, depth=0, include_unpublished=include_unpublished)

    async def _expand(
        self,
        html: str,
        *,
        depth: int,
        include_unpublished: bool,
    ) -> str:
        slugs = self.referenced_slugs(html)
        if not slugs:
            return html

        stmt = select(ReusableBlock).where(
            ReusableBlock.slug.in_(slugs),
            ReusableBlock.deleted_at.is_(None),
        )
        if not include_unpublished:
            stmt = stmt.where(
                ReusableBlock.status == ReusableBlockStatus.PUBLISHED,
                ReusableBlock.is_active.is_(True),
            )
        found = {
            block.slug: block
            for block in (await self.db.execute(stmt)).scalars().all()
        }

        def _replace(match: re.Match[str]) -> str:
            block = found.get(match.group(1))
            if block is None:
                return match.group(0)
            return block.body_html

        expanded = _BLOCK_REF_RE.sub(_replace, html)

        # Nested references, but never deeper than the cycle guard allows.
        if depth + 1 < _MAX_EXPANSION_DEPTH and self.referenced_slugs(expanded):
            return await self._expand(
                expanded, depth=depth + 1, include_unpublished=include_unpublished
            )
        return expanded

    async def count_active(self) -> int:
        stmt = select(func.count(ReusableBlock.id)).where(
            ReusableBlock.deleted_at.is_(None),
            ReusableBlock.status == ReusableBlockStatus.PUBLISHED,
            ReusableBlock.is_active.is_(True),
        )
        return int((await self.db.execute(stmt)).scalar() or 0)
