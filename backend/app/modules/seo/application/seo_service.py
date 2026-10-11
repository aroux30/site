"""SEO service handling metadata storage, retrieval, and schema generation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError
from app.modules.blog.domain.models import BlogPost
from app.modules.catalog.domain.models import Category, Product
from app.modules.seo.domain.models import SEOMetadata
from app.modules.seo.schemas.seo import (
    SEOMetadataCreate,
    SEOMetadataResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class SEOService:
    """Service for managing per-resource SEO and Open Graph metadata."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> SEOMetadataResponse:
        """Retrieve SEO metadata for a resource, generating sensible defaults if not found."""
        stmt = select(SEOMetadata).where(
            SEOMetadata.resource_type == resource_type,
            SEOMetadata.resource_id == resource_id,
        )
        record = (await self.db.execute(stmt)).scalar_one_or_none()

        if record:
            return SEOMetadataResponse.model_validate(record)

        # Generate sensible dynamic defaults based on resource type
        return await self._generate_default_seo(resource_type, resource_id)

    async def upsert_for_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        data: SEOMetadataCreate,
    ) -> SEOMetadataResponse:
        """Create or update SEO metadata for a resource."""
        stmt = select(SEOMetadata).where(
            SEOMetadata.resource_type == resource_type,
            SEOMetadata.resource_id == resource_id,
        )
        record = (await self.db.execute(stmt)).scalar_one_or_none()

        update_data = data.model_dump(exclude_unset=True)

        if record:
            for key, val in update_data.items():
                setattr(record, key, val)
        else:
            record = SEOMetadata(
                resource_type=resource_type,
                resource_id=resource_id,
                **update_data,
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)

        return SEOMetadataResponse.model_validate(record)

    async def delete_for_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> None:
        """Delete SEO metadata for a resource."""
        stmt = select(SEOMetadata).where(
            SEOMetadata.resource_type == resource_type,
            SEOMetadata.resource_id == resource_id,
        )
        record = (await self.db.execute(stmt)).scalar_one_or_none()
        if not record:
            raise NotFoundError(
                "SEOMetadata", f"SEO metadata for {resource_type}:{resource_id} not found"
            )

        await self.db.delete(record)
        await self.db.commit()

    async def _generate_default_seo(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> SEOMetadataResponse:
        """Generate default SEO title, description, and JSON-LD schema from the domain model.

        The title/description come from the operator's Titles & Meta
        templates (``titles_meta_service``) — the strings here are only the
        fallback when even the template render is empty, and the built-in
        template defaults reproduce the exact strings this method used to
        hardcode.
        """
        from app.modules.seo.application.titles_meta_service import TitlesMetaService

        tm = TitlesMetaService(self.db)

        if resource_type in ("blog_post", "post", "blog"):
            post = await self.db.get(BlogPost, resource_id)
            if post:
                raw_desc = post.excerpt or (
                    post.content[:150] + "..." if len(post.content) > 150 else post.content
                )
                # `category` must be eager-loaded: touching the relationship
                # on an async session raises MissingGreenlet (the exact bug
                # blog-list-500 documented). A missing category is fine —
                # %category% renders empty — but a lazy load is a crash.
                from sqlalchemy import select as _select
                from sqlalchemy.orm import selectinload as _selectinload

                post = (
                    await self.db.execute(
                        _select(BlogPost)
                        .where(BlogPost.id == post.id)
                        .options(_selectinload(BlogPost.category))
                    )
                ).scalar_one()
                # Focus keyword lives in seo_metadata (seokw1), not on the
                # post row; the row we may be generating defaults FOR can
                # carry one the operator already saved.
                focus_row = (
                    await self.db.execute(
                        _select(SEOMetadata.focus_keyword).where(
                            SEOMetadata.resource_type.in_(("blog_post", "post", "blog")),
                            SEOMetadata.resource_id == post.id,
                        )
                    )
                ).scalar_one_or_none()
                title, desc = await tm.resolve(
                    "post",
                    title=post.title,
                    excerpt=post.excerpt or raw_desc,
                    focus_keyword=focus_row,
                    category=post.category.name if post.category else None,
                    modified=post.updated_at.isoformat() if post.updated_at else None,
                    resource_id=str(post.id),
                )
                title = title or f"{post.title} | وبلاگ"
                desc = desc or raw_desc
                # schema_markup is None for the same reason as the product
                # branch: a generated stub must not masquerade as an operator
                # override, or the storefront's stored-override branch would
                # pick it over the rich built-in Article node.
                return SEOMetadataResponse(
                    id=uuid.uuid4(),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    title=title,
                    description=desc,
                    canonical_url=f"/blog/{post.slug}",
                    og_title=post.title,
                    og_description=desc,
                    og_image=post.cover_image_url,
                    schema_markup=None,
                )

        if resource_type in ("product", "products"):
            prod = await self.db.get(Product, resource_id)
            if prod:
                raw_desc = prod.short_description or prod.name
                title, desc = await tm.resolve(
                    "product",
                    title=prod.name,
                    excerpt=raw_desc,
                    resource_id=str(prod.id),
                )
                title = title or f"{prod.name} | خرید و بررسی"
                desc = desc or raw_desc
                # schema_markup is deliberately None here. A *generated* stub
                # is not an operator override: returning one made the
                # storefront's `schemaOverride ?? buildProductJsonLd` pick the
                # stub (name+description only) over the rich built-in node
                # (offers/price/availability), silently dropping the product
                # rich result. Only a stored row carries schema_markup — the
                # storefront builds its own node when none is stored.
                return SEOMetadataResponse(
                    id=uuid.uuid4(),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    title=title,
                    description=desc,
                    canonical_url=f"/products/{prod.slug}",
                    og_title=prod.name,
                    og_description=desc,
                    schema_markup=None,
                )

        if resource_type in ("category", "categories"):
            cat = await self.db.get(Category, resource_id)
            if cat:
                raw_desc = cat.description or f"بهترین قیمت و مشخصات محصولات {cat.name}"
                title, desc = await tm.resolve(
                    "category",
                    title=cat.name,
                    excerpt=raw_desc,
                    resource_id=str(cat.id),
                )
                title = title or f"خرید محصولات دسته‌بندی {cat.name}"
                desc = desc or raw_desc
                return SEOMetadataResponse(
                    id=uuid.uuid4(),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    title=title,
                    description=desc,
                    canonical_url=f"/products?category={cat.slug}",
                    og_title=cat.name,
                    og_description=desc,
                    schema_markup=None,
                )

        # Generic fallback
        return SEOMetadataResponse(
            id=uuid.uuid4(),
            resource_type=resource_type,
            resource_id=resource_id,
            title=None,
            description=None,
            canonical_url=None,
            og_title=None,
            og_description=None,
            og_image=None,
            schema_markup=None,
        )
