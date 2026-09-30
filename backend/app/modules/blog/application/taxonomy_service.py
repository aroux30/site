"""Custom taxonomy and custom post type services (WordPress parity).

The admin routes used to write taxonomies, terms, content types and entries
inline. This service owns the write path so that update and delete exist at
all: before, a taxonomy or post type could be created but never modified or
removed, and an entry could be created but never edited.

All mutations run in one transaction and re-validate the fields the columns
actually constrain, so a rename that would collide with a unique slug fails
loudly instead of raising a bare IntegrityError.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.blog.domain.custom_post_types import (
    CustomPostEntry,
    CustomPostType,
    CustomPostTypeStatus,
)
from app.modules.blog.domain.taxonomy_models import (
    CustomTaxonomy,
    CustomTaxonomyTerm,
)
from app.shared.domain.slug import generate_slug

# Fields a client may set on each resource. Anything else in the body is
# rejected rather than silently ignored, so a typo surfaces as an error.
_TAXONOMY_FIELDS = {"name", "slug", "description", "hierarchical", "is_active"}
_TERM_FIELDS = {"name", "slug", "description", "parent_id", "position"}
_CPT_FIELDS = {
    "name", "slug", "description", "icon", "field_schema",
    "supports_categories", "supports_comments", "is_active",
}
_ENTRY_FIELDS = {
    "title", "slug", "fields", "excerpt", "cover_image_url", "status", "position",
}


def _reject_unknown(body: dict[str, Any], allowed: set[str], what: str) -> None:
    unknown = set(body) - allowed
    if unknown:
        raise ValidationError(
            f"فیلدهای ناشناخته برای {what}: {', '.join(sorted(unknown))}",
            extra={"allowed": sorted(allowed)},
        )


async def _ensure_term_slug_free(
    db: AsyncSession, taxonomy_id: uuid.UUID, slug: str, *, exclude: uuid.UUID | None = None
) -> None:
    stmt = select(CustomTaxonomyTerm.id).where(
        CustomTaxonomyTerm.taxonomy_id == taxonomy_id, CustomTaxonomyTerm.slug == slug
    )
    if exclude is not None:
        stmt = stmt.where(CustomTaxonomyTerm.id != exclude)
    if (await db.execute(stmt)).first() is not None:
        raise ConflictError(f"اسلاگ «{slug}» در این تاکسونومی قبلاً استفاده شده است")


async def _ensure_entry_slug_free(
    db: AsyncSession, post_type_id: uuid.UUID, slug: str, *, exclude: uuid.UUID | None = None
) -> None:
    stmt = select(CustomPostEntry.id).where(
        CustomPostEntry.post_type_id == post_type_id, CustomPostEntry.slug == slug
    )
    if exclude is not None:
        stmt = stmt.where(CustomPostEntry.id != exclude)
    if (await db.execute(stmt)).first() is not None:
        raise ConflictError(f"اسلاگ «{slug}» در این نوع محتوا قبلاً استفاده شده است")


class TaxonomyService:
    """Write path for custom taxonomies and their terms."""

    @staticmethod
    async def update_taxonomy(
        db: AsyncSession, taxonomy_id: uuid.UUID, body: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown(body, _TAXONOMY_FIELDS, "تاکسونومی")
        tax = await db.get(CustomTaxonomy, taxonomy_id)
        if tax is None:
            raise NotFoundError("CustomTaxonomy", f"تاکسونومی {taxonomy_id} یافت نشد")

        if "name" in body and body["name"]:
            tax.name = str(body["name"]).strip()
        if body.get("slug"):
            tax.slug = generate_slug(str(body["slug"]))
        elif "name" in body and body["name"] and not tax.slug:
            tax.slug = generate_slug(tax.name)
        for key in ("description", "hierarchical", "is_active"):
            if key in body:
                setattr(tax, key, body[key])

        await db.commit()
        await db.refresh(tax)
        return {
            "id": str(tax.id), "name": tax.name, "slug": tax.slug,
            "description": tax.description, "hierarchical": tax.hierarchical,
            "is_active": tax.is_active,
        }

    @staticmethod
    async def delete_taxonomy(db: AsyncSession, taxonomy_id: uuid.UUID) -> dict[str, int]:
        """Delete a taxonomy. Terms and post links cascade; report the size."""
        tax = await db.get(CustomTaxonomy, taxonomy_id)
        if tax is None:
            raise NotFoundError("CustomTaxonomy", f"تاکسونومی {taxonomy_id} یافت نشد")
        from app.modules.blog.domain.taxonomy_models import BlogPostTerm

        term_ids = select(CustomTaxonomyTerm.id).where(
            CustomTaxonomyTerm.taxonomy_id == taxonomy_id
        )
        links = (
            await db.execute(
                select(func.count()).select_from(BlogPostTerm).where(
                    BlogPostTerm.term_id.in_(term_ids)
                )
            )
        ).scalar_one()
        term_count = (await db.execute(
            select(func.count()).select_from(CustomTaxonomyTerm).where(
                CustomTaxonomyTerm.taxonomy_id == taxonomy_id)
        )).scalar_one()

        await db.delete(tax)  # cascade removes terms and their post links
        await db.commit()
        return {"taxonomies_deleted": 1, "terms_deleted": term_count, "post_links_deleted": links}

    @staticmethod
    async def update_term(
        db: AsyncSession, term_id: uuid.UUID, body: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown(body, _TERM_FIELDS, "ترم")
        term = await db.get(CustomTaxonomyTerm, term_id)
        if term is None:
            raise NotFoundError("CustomTaxonomyTerm", f"ترم {term_id} یافت نشد")

        if "name" in body and body["name"]:
            term.name = str(body["name"]).strip()
        slug = generate_slug(str(body["slug"])) if body.get("slug") else (
            generate_slug(term.name) if body.get("name") else term.slug
        )
        if slug != term.slug:
            await _ensure_term_slug_free(db, term.taxonomy_id, slug, exclude=term_id)
            term.slug = slug

        for key in ("description", "position"):
            if key in body:
                setattr(term, key, body[key])
        if "parent_id" in body:
            parent = body["parent_id"]
            if parent:
                parent_id = uuid.UUID(str(parent))
                if parent_id == term_id:
                    raise ValidationError("یک ترم نمی‌تواند والد خودش باشد")
                parent_row = await db.get(CustomTaxonomyTerm, parent_id)
                if parent_row is None:
                    raise NotFoundError("CustomTaxonomyTerm", f"والد {parent_id} یافت نشد")
                if parent_row.taxonomy_id != term.taxonomy_id:
                    raise ValidationError("والد باید در همان تاکسونومی باشد")
                term.parent_id = parent_id
            else:
                term.parent_id = None

        await db.commit()
        await db.refresh(term)
        return {
            "id": str(term.id), "name": term.name, "slug": term.slug,
            "description": term.description, "position": term.position,
            "parent_id": str(term.parent_id) if term.parent_id else None,
        }

    @staticmethod
    async def delete_term(db: AsyncSession, term_id: uuid.UUID) -> dict[str, int]:
        term = await db.get(CustomTaxonomyTerm, term_id)
        if term is None:
            raise NotFoundError("CustomTaxonomyTerm", f"ترم {term_id} یافت نشد")
        from app.modules.blog.domain.taxonomy_models import BlogPostTerm

        children = (await db.execute(
            select(func.count()).select_from(CustomTaxonomyTerm).where(
                CustomTaxonomyTerm.parent_id == term_id)
        )).scalar_one()
        if children:
            raise ValidationError(
                f"این ترم {children} زیرترم دارد؛ ابتدا آن‌ها را حذف یا جابه‌جا کنید")
        links = (await db.execute(
            select(func.count()).select_from(BlogPostTerm).where(BlogPostTerm.term_id == term_id)
        )).scalar_one()
        await db.delete(term)
        await db.commit()
        return {"terms_deleted": 1, "post_links_deleted": links}


class ContentTypeService:
    """Write path for custom post types and their entries."""

    @staticmethod
    async def update_content_type(
        db: AsyncSession, type_id: uuid.UUID, body: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown(body, _CPT_FIELDS, "نوع محتوا")
        cpt = await db.get(CustomPostType, type_id)
        if cpt is None:
            raise NotFoundError("CustomPostType", f"نوع محتوا {type_id} یافت نشد")

        if "name" in body and body["name"]:
            cpt.name = str(body["name"]).strip()
        if body.get("slug"):
            cpt.slug = generate_slug(str(body["slug"]))
        for key in (
            "description", "icon", "field_schema",
            "supports_categories", "supports_comments", "is_active",
        ):
            if key in body:
                setattr(cpt, key, body[key])

        await db.commit()
        await db.refresh(cpt)
        return {
            "id": str(cpt.id), "name": cpt.name, "slug": cpt.slug,
            "description": cpt.description, "icon": cpt.icon,
            "field_schema": cpt.field_schema,
            "supports_categories": cpt.supports_categories,
            "supports_comments": cpt.supports_comments, "is_active": cpt.is_active,
        }

    @staticmethod
    async def delete_content_type(db: AsyncSession, type_id: uuid.UUID) -> dict[str, int]:
        """Delete a post type and every entry under it (cascade)."""
        cpt = await db.get(CustomPostType, type_id)
        if cpt is None:
            raise NotFoundError("CustomPostType", f"نوع محتوا {type_id} یافت نشد")
        entries = (await db.execute(
            select(func.count()).select_from(CustomPostEntry).where(
                CustomPostEntry.post_type_id == type_id)
        )).scalar_one()
        await db.delete(cpt)
        await db.commit()
        return {"content_types_deleted": 1, "entries_deleted": entries}

    @staticmethod
    async def update_entry(
        db: AsyncSession, entry_id: uuid.UUID, body: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown(body, _ENTRY_FIELDS, "ورودی")
        entry = await db.get(CustomPostEntry, entry_id)
        if entry is None:
            raise NotFoundError("CustomPostEntry", f"ورودی {entry_id} یافت نشد")

        if "title" in body and body["title"]:
            entry.title = str(body["title"]).strip()
        slug = generate_slug(str(body["slug"])) if body.get("slug") else (
            generate_slug(entry.title) if body.get("title") else entry.slug
        )
        if slug != entry.slug:
            await _ensure_entry_slug_free(
                db, entry.post_type_id, slug, exclude=entry_id)
            entry.slug = slug

        for key in ("fields", "excerpt", "cover_image_url", "position"):
            if key in body:
                setattr(entry, key, body[key])
        if body.get("status"):
            try:
                entry.status = CustomPostTypeStatus(str(body["status"]))
            except ValueError as exc:
                raise ValidationError(
                    f"وضعیت نامعتبر: {body['status']}",
                    extra={"allowed": [s.value for s in CustomPostTypeStatus]},
                ) from exc
            if entry.status is CustomPostTypeStatus.PUBLISHED and entry.published_at is None:
                entry.published_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(entry)
        return {
            "id": str(entry.id), "title": entry.title, "slug": entry.slug,
            "status": entry.status.value, "fields": entry.fields,
            "excerpt": entry.excerpt, "cover_image_url": entry.cover_image_url,
            "position": entry.position,
        }

    @staticmethod
    async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> dict[str, int]:
        entry = await db.get(CustomPostEntry, entry_id)
        if entry is None:
            raise NotFoundError("CustomPostEntry", f"ورودی {entry_id} یافت نشد")
        await db.delete(entry)
        await db.commit()
        return {"entries_deleted": 1}
