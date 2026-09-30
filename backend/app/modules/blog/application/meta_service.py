"""Key-value custom fields for pages, comments and taxonomy terms.

WordPress parity: ``wp_postmeta`` / ``wp_commentmeta`` / ``wp_termmeta`` all
follow the same shape, and post meta already shipped with routes on the blog
router. The tables for comments and terms existed but nothing ever read or
wrote them, so an extension could store a key and never see it again.

One service covers all three so the access pattern stays identical: list by
owner, upsert by key, delete by key. Term meta is keyed by ``(term_type,
term_id)`` because a term id is only unique within its taxonomy, and a term id
may be a category, a tag, or a custom-taxonomy term.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.blog.domain.wp_parity_models import BlogCommentMeta, BlogTermMeta
from app.modules.content.domain.models import CmsPage

MAX_KEY_LENGTH = 255
# Term types we can resolve a term id against, so a meta write cannot point at
# a term that does not exist in that taxonomy.
_TERM_TABLES = {
    "category": ("app.modules.blog.domain.models", "BlogCategory"),
    "tag": ("app.modules.blog.domain.models", "BlogTag"),
    "custom": ("app.modules.blog.domain.taxonomy_models", "CustomTaxonomyTerm"),
}


def _validate_key(meta_key: str) -> str:
    key = (meta_key or "").strip()
    if not key:
        raise ValidationError("کلید متا نمی‌تواند خالی باشد")
    if len(key) > MAX_KEY_LENGTH:
        raise ValidationError(f"کلید متا حداکثر {MAX_KEY_LENGTH} نویسه است")
    return key


def _row(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "meta_key": row.meta_key,
        "meta_value": row.meta_value,
    }


async def _term_model(db: AsyncSession, term_type: str, term_id: uuid.UUID) -> Any:
    spec = _TERM_TABLES.get(term_type)
    if spec is None:
        raise ValidationError(
            f"نوع ترم نامعتبر: {term_type}",
            extra={"allowed": sorted(_TERM_TABLES)},
        )
    import importlib

    model = getattr(importlib.import_module(spec[0]), spec[1])
    if await db.get(model, term_id) is None:
        raise NotFoundError(spec[1], f"ترم {term_id} در نوع {term_type} یافت نشد")
    return model


class CommentMetaService:
    """Custom fields on blog comments."""

    @staticmethod
    async def list(db: AsyncSession, comment_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await db.execute(
            select(BlogCommentMeta)
            .where(BlogCommentMeta.comment_id == comment_id)
            .order_by(BlogCommentMeta.meta_key)
        )).scalars().all()
        return [_row(r) for r in rows]

    @staticmethod
    async def upsert(
        db: AsyncSession, comment_id: uuid.UUID, meta_key: str, meta_value: str | None
    ) -> dict[str, Any]:
        from app.modules.blog.domain.models import BlogComment

        if await db.get(BlogComment, comment_id) is None:
            raise NotFoundError("BlogComment", f"دیدگاه {comment_id} یافت نشد")
        key = _validate_key(meta_key)
        existing = (await db.execute(
            select(BlogCommentMeta).where(
                BlogCommentMeta.comment_id == comment_id, BlogCommentMeta.meta_key == key)
        )).scalar_one_or_none()
        if existing is not None:
            existing.meta_value = meta_value
        else:
            existing = BlogCommentMeta(comment_id=comment_id, meta_key=key, meta_value=meta_value)
            db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return _row(existing)

    @staticmethod
    async def delete(db: AsyncSession, comment_id: uuid.UUID, meta_key: str) -> bool:
        result = await db.execute(sa_delete(BlogCommentMeta).where(
            BlogCommentMeta.comment_id == comment_id,
            BlogCommentMeta.meta_key == meta_key,
        ))
        await db.commit()
        return bool(result.rowcount)


class TermMetaService:
    """Custom fields on categories, tags and custom-taxonomy terms."""

    @staticmethod
    async def list(
        db: AsyncSession, term_type: str, term_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        if term_type not in _TERM_TABLES:
            raise ValidationError(
                f"نوع ترم نامعتبر: {term_type}",
                extra={"allowed": sorted(_TERM_TABLES)},
            )
        rows = (await db.execute(
            select(BlogTermMeta)
            .where(BlogTermMeta.term_type == term_type, BlogTermMeta.term_id == term_id)
            .order_by(BlogTermMeta.meta_key)
        )).scalars().all()
        return [_row(r) for r in rows]

    @staticmethod
    async def upsert(
        db: AsyncSession, term_type: str, term_id: uuid.UUID,
        meta_key: str, meta_value: str | None,
    ) -> dict[str, Any]:
        await _term_model(db, term_type, term_id)
        key = _validate_key(meta_key)
        existing = (await db.execute(
            select(BlogTermMeta).where(
                BlogTermMeta.term_type == term_type,
                BlogTermMeta.term_id == term_id,
                BlogTermMeta.meta_key == key,
            )
        )).scalar_one_or_none()
        if existing is not None:
            existing.meta_value = meta_value
        else:
            existing = BlogTermMeta(
                term_type=term_type, term_id=term_id, meta_key=key, meta_value=meta_value)
            db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return _row(existing)

    @staticmethod
    async def delete(db: AsyncSession, term_type: str, term_id: uuid.UUID, meta_key: str) -> bool:
        result = await db.execute(sa_delete(BlogTermMeta).where(
            BlogTermMeta.term_type == term_type,
            BlogTermMeta.term_id == term_id,
            BlogTermMeta.meta_key == meta_key,
        ))
        await db.commit()
        return bool(result.rowcount)


class PageMetaService:
    """Custom fields on CMS pages — the one owner that had no meta at all.

    Stored in a generic ``content_meta`` table rather than a page-specific one:
    the same shape serves every content type, so a page and a reusable block
    share one access path instead of each growing its own table.
    """

    @staticmethod
    async def list(db: AsyncSession, page_id: uuid.UUID) -> list[dict[str, Any]]:
        from app.modules.content.domain.meta import ContentMeta

        if await db.get(CmsPage, page_id) is None:
            raise NotFoundError("CmsPage", f"صفحه {page_id} یافت نشد")
        rows = (await db.execute(
            select(ContentMeta)
            .where(ContentMeta.resource_type == "page", ContentMeta.resource_id == page_id)
            .order_by(ContentMeta.meta_key)
        )).scalars().all()
        return [_row(r) for r in rows]

    @staticmethod
    async def upsert(
        db: AsyncSession, page_id: uuid.UUID, meta_key: str, meta_value: str | None
    ) -> dict[str, Any]:
        from app.modules.content.domain.meta import ContentMeta

        if await db.get(CmsPage, page_id) is None:
            raise NotFoundError("CmsPage", f"صفحه {page_id} یافت نشد")
        key = _validate_key(meta_key)
        existing = (await db.execute(
            select(ContentMeta).where(
                ContentMeta.resource_type == "page",
                ContentMeta.resource_id == page_id,
                ContentMeta.meta_key == key,
            )
        )).scalar_one_or_none()
        if existing is not None:
            existing.meta_value = meta_value
        else:
            existing = ContentMeta(
                resource_type="page", resource_id=page_id,
                meta_key=key, meta_value=meta_value)
            db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return _row(existing)

    @staticmethod
    async def delete(db: AsyncSession, page_id: uuid.UUID, meta_key: str) -> bool:
        from app.modules.content.domain.meta import ContentMeta

        result = await db.execute(sa_delete(ContentMeta).where(
            ContentMeta.resource_type == "page",
            ContentMeta.resource_id == page_id,
            ContentMeta.meta_key == meta_key,
        ))
        await db.commit()
        return bool(result.rowcount)
