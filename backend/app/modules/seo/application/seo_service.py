"""SEO service handling metadata storage, retrieval, and schema generation."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import NotFoundError
from app.modules.blog.domain.models import BlogPost
from app.modules.catalog.domain.models import Category, Product
from app.modules.seo.domain.models import SEOMetadata
from app.modules.seo.schemas.seo import (
    SEOMetadataCreate,
    SEOMetadataResponse,
    SEOMetadataUpdate,
)

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
            raise NotFoundError("SEOMetadata", f"SEO metadata for {resource_type}:{resource_id} not found")

        await self.db.delete(record)
        await self.db.commit()

    async def _generate_default_seo(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> SEOMetadataResponse:
        """Generate default SEO title, description, and JSON-LD schema from the domain model."""
        if resource_type in ("blog_post", "post", "blog"):
            post = await self.db.get(BlogPost, resource_id)
            if post:
                title = f"{post.title} | وبلاگ"
                desc = post.excerpt or (post.content[:150] + "..." if len(post.content) > 150 else post.content)
                schema: dict[str, Any] = {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": post.title,
                    "description": desc,
                    "datePublished": post.published_at.isoformat() if post.published_at else None,
                    "image": post.cover_image_url,
                }
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
                    schema_markup=schema,
                )

        if resource_type in ("product", "products"):
            prod = await self.db.get(Product, resource_id)
            if prod:
                title = f"{prod.name} | خرید و بررسی"
                desc = prod.short_description or prod.name
                schema = {
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": prod.name,
                    "description": desc,
                }
                return SEOMetadataResponse(
                    id=uuid.uuid4(),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    title=title,
                    description=desc,
                    canonical_url=f"/products/{prod.slug}",
                    og_title=prod.name,
                    og_description=desc,
                    schema_markup=schema,
                )

        if resource_type in ("category", "categories"):
            cat = await self.db.get(Category, resource_id)
            if cat:
                title = f"خرید محصولات دسته‌بندی {cat.name}"
                desc = cat.description or f"بهترین قیمت و مشخصات محصولات {cat.name}"
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
