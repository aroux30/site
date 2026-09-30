"""Catalog service – business logic for categories, brands, products, and related entities.

This service layer orchestrates repository calls, performs validation, handles
slug generation (including from Persian/Farsi text), and maps between domain
models and Pydantic schemas.
"""

from __future__ import annotations

import builtins
import math
import time
import uuid
from collections.abc import Awaitable, Callable
from types import EllipsisType
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.observability.tracer import get_tracer
from app.modules.catalog.domain.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductImage,
    ProductVariant,
    Tag,
)
from app.modules.catalog.infrastructure.catalog_repository import (
    AttributeRepository,
    BrandRepository,
    CategoryRepository,
    ImageRepository,
    ProductAttributeRepository,
    ProductRepository,
    TagRepository,
    VariantRepository,
)
from app.modules.catalog.schemas.catalog import (
    AttributeCreate,
    AttributeListResponse,
    AttributeResponse,
    AttributeUpdate,
    AttributeValueCreate,
    AttributeValueListResponse,
    AttributeValueResponse,
    BrandCreate,
    BrandListResponse,
    BrandResponse,
    BrandUpdate,
    CategoryCreate,
    CategoryListResponse,
    CategoryReorderRequest,
    CategoryResponse,
    CategoryTreeResponse,
    CategoryUpdate,
    ImageReorderRequest,
    PaginationMeta,
    ProductAttributeResponse,
    ProductBulkDeleteRequest,
    ProductBulkUpdateRequest,
    ProductCreate,
    ProductDetailResponse,
    ProductFilterParams,
    ProductImageCreate,
    ProductImageResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    TagAssignRequest,
    TagCreate,
    TagListResponse,
    TagResponse,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
    rial_to_toman,
    toman_to_rial,
)
from app.shared.domain.slug import generate_slug as _generate_slug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _publish_product_event(
    session: AsyncSession,
    event_type: str,
    product_id: uuid.UUID,
) -> None:
    """Publish a product lifecycle event to the transactional outbox.

    The outbox worker dispatches ``sync_single_product`` so the Elasticsearch
    projection tracks catalog writes without waiting for the nightly
    reindex.  Publishing failures are logged, never raised: search sync is
    best-effort and must not fail catalog mutations.
    """
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            session,
            event_type=event_type,
            aggregate_type="product",
            aggregate_id=str(product_id),
            payload={"product_id": str(product_id)},
        )
    except Exception as exc:  # search sync must never block writes
        await logger.awarning(
            "product_event_publish_skipped",
            event_type=event_type,
            product_id=str(product_id),
            error=str(exc),
        )


# ============================================================================
# Slug Generation (Persian / Latin)
# ============================================================================

# Mapping of Persian characters to Latin equivalents for slug generation
def generate_slug(text: str) -> str:
    """Generate a URL-safe slug (shared Persian/Arabic transliteration helper).

    Kept as a local name so existing call sites and imports stay untouched.
    """
    return _generate_slug(text)


async def _ensure_unique_slug(
    slug: str,
    exists_fn: Callable[[str, uuid.UUID | None], Awaitable[bool]],
    exclude_id: uuid.UUID | None = None,
) -> str:
    """Append a numeric suffix to *slug* until it is unique."""
    candidate = slug
    counter = 1
    while await exists_fn(candidate, exclude_id):
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


# ============================================================================
# Pagination Helper
# ============================================================================


def _build_meta(
    total: int,
    page: int,
    page_size: int,
    items_count: int,
    cursor: str | None = None,
) -> PaginationMeta:
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    return PaginationMeta(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
        next_cursor=cursor,
    )


# ============================================================================
# Category Service
# ============================================================================


class CategoryService:
    """Business logic for categories."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = CategoryRepository(session)
        self._session = session

    async def create(self, data: CategoryCreate) -> CategoryResponse:
        slug = data.slug or generate_slug(data.name)
        slug = await _ensure_unique_slug(slug, self._repo.slug_exists)

        # Calculate depth and path
        depth = 0
        path = slug
        if data.parent_id:
            parent = await self._repo.get_by_id(data.parent_id)
            if parent is None:
                raise NotFoundError("Category", detail="Parent category not found")
            depth = parent.depth + 1
            path = f"{parent.path}/{slug}" if parent.path else slug

        category = Category(
            name=data.name,
            slug=slug,
            parent_id=data.parent_id,
            description=data.description,
            image_url=data.image_url,
            path=path,
            depth=depth,
            position=data.position,
            is_active=data.is_active,
            seo_title=data.seo_title,
            seo_description=data.seo_description,
        )
        category = await self._repo.create(category)
        await logger.ainfo("category_created", category_id=str(category.id), slug=slug)
        return CategoryResponse.model_validate(category)

    async def update(self, category_id: uuid.UUID, data: CategoryUpdate) -> CategoryResponse:
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise NotFoundError("Category")

        update_data = data.model_dump(exclude_unset=True)

        # Handle slug
        if "name" in update_data and "slug" not in update_data:
            update_data["slug"] = generate_slug(update_data["name"])
        if "slug" in update_data:
            update_data["slug"] = await _ensure_unique_slug(
                update_data["slug"], self._repo.slug_exists, exclude_id=category_id
            )

        # Handle parent change → recalculate depth/path
        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id == category_id:
                raise ValidationError("A category cannot be its own parent")
            if new_parent_id is not None:
                parent = await self._repo.get_by_id(new_parent_id)
                if parent is None:
                    raise NotFoundError("Category", detail="Parent category not found")
                # Prevent circular references
                if parent.path and str(category_id) in (parent.path or ""):
                    raise ValidationError("Circular parent reference detected")
                update_data["depth"] = parent.depth + 1
                slug_for_path = update_data.get("slug", category.slug)
                update_data["path"] = (
                    f"{parent.path}/{slug_for_path}" if parent.path else slug_for_path
                )
            else:
                update_data["depth"] = 0
                update_data["path"] = update_data.get("slug", category.slug)

        for key, value in update_data.items():
            setattr(category, key, value)

        category = await self._repo.update(category)
        await logger.ainfo("category_updated", category_id=str(category_id))
        return CategoryResponse.model_validate(category)

    async def delete(self, category_id: uuid.UUID) -> None:
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise NotFoundError("Category")

        if await self._repo.has_children(category_id):
            raise ConflictError(
                "Cannot delete category with subcategories. Move or delete children first."
            )
        if await self._repo.has_products(category_id):
            raise ConflictError(
                "Cannot delete category with associated products. Reassign products first."
            )

        await self._repo.delete(category_id)
        await logger.ainfo("category_deleted", category_id=str(category_id))

    async def get_by_id(self, category_id: uuid.UUID) -> CategoryResponse:
        tracer = get_tracer()
        with tracer.start_as_current_span("catalog.get_category") as span:
            span.set_attribute("catalog.category_id", str(category_id))
            t0 = time.perf_counter()
            category = await self._repo.get_by_id(category_id)
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            span.set_attribute("catalog.cache_fetch_duration_ms", duration_ms)
            if category is None:
                raise NotFoundError("Category")
            return CategoryResponse.model_validate(category)

    async def get_by_slug(self, slug: str) -> CategoryResponse:
        category = await self._repo.get_by_slug(slug)
        if category is None:
            raise NotFoundError("Category")
        return CategoryResponse.model_validate(category)

    async def list(
        self,
        *,
        is_active: bool | None = None,
        parent_id: uuid.UUID | None | EllipsisType = ...,
        page: int = 1,
        page_size: int = 50,
    ) -> CategoryListResponse:
        categories, total = await self._repo.get_all(
            is_active=is_active, parent_id=parent_id, page=page, page_size=page_size
        )
        items = [CategoryResponse.model_validate(c) for c in categories]
        return CategoryListResponse(
            items=items,
            meta=_build_meta(total, page, page_size, len(items)),
        )

    async def get_tree(
        self, *, is_active: bool | None = None
    ) -> builtins.list[CategoryTreeResponse]:
        """Build and return the full category tree."""
        all_categories = await self._repo.get_tree(is_active=is_active)

        # Build lookup and tree
        nodes: dict[uuid.UUID, CategoryTreeResponse] = {}
        roots: list[CategoryTreeResponse] = []

        for cat in all_categories:
            node = CategoryTreeResponse(
                id=cat.id,
                parent_id=cat.parent_id,
                name=cat.name,
                slug=cat.slug,
                description=cat.description,
                image_url=cat.image_url,
                path=cat.path,
                depth=cat.depth,
                position=cat.position,
                is_active=cat.is_active,
                children=[],
            )
            nodes[cat.id] = node

        for cat in all_categories:
            node = nodes[cat.id]
            if cat.parent_id and cat.parent_id in nodes:
                nodes[cat.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots

    async def reorder(self, data: CategoryReorderRequest) -> int:
        items = [(item.id, item.position) for item in data.items]
        count = await self._repo.bulk_update_positions(items)
        await logger.ainfo("categories_reordered", count=count)
        return count


# ============================================================================
# Brand Service
# ============================================================================


class BrandService:
    """Business logic for brands."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = BrandRepository(session)

    async def create(self, data: BrandCreate) -> BrandResponse:
        slug = data.slug or generate_slug(data.name)
        slug = await _ensure_unique_slug(slug, self._repo.slug_exists)

        brand = Brand(
            name=data.name,
            slug=slug,
            logo_url=data.logo_url,
            description=data.description,
            is_active=data.is_active,
        )
        brand = await self._repo.create(brand)
        await logger.ainfo("brand_created", brand_id=str(brand.id), slug=slug)
        return BrandResponse.model_validate(brand)

    async def update(self, brand_id: uuid.UUID, data: BrandUpdate) -> BrandResponse:
        brand = await self._repo.get_by_id(brand_id)
        if brand is None:
            raise NotFoundError("Brand")

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and "slug" not in update_data:
            update_data["slug"] = generate_slug(update_data["name"])
        if "slug" in update_data:
            update_data["slug"] = await _ensure_unique_slug(
                update_data["slug"], self._repo.slug_exists, exclude_id=brand_id
            )

        for key, value in update_data.items():
            setattr(brand, key, value)

        brand = await self._repo.update(brand)
        await logger.ainfo("brand_updated", brand_id=str(brand_id))
        return BrandResponse.model_validate(brand)

    async def delete(self, brand_id: uuid.UUID) -> None:
        brand = await self._repo.get_by_id(brand_id)
        if brand is None:
            raise NotFoundError("Brand")

        if await self._repo.has_products(brand_id):
            raise ConflictError(
                "Cannot delete brand with associated products. Reassign products first."
            )

        await self._repo.delete(brand_id)
        await logger.ainfo("brand_deleted", brand_id=str(brand_id))

    async def get_by_id(self, brand_id: uuid.UUID) -> BrandResponse:
        brand = await self._repo.get_by_id(brand_id)
        if brand is None:
            raise NotFoundError("Brand")
        return BrandResponse.model_validate(brand)

    async def get_by_slug(self, slug: str) -> BrandResponse:
        brand = await self._repo.get_by_slug(slug)
        if brand is None:
            raise NotFoundError("Brand")
        return BrandResponse.model_validate(brand)

    async def list(
        self,
        *,
        is_active: bool | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> BrandListResponse:
        brands, total = await self._repo.get_all(
            is_active=is_active, q=q, page=page, page_size=page_size
        )
        items = [BrandResponse.model_validate(b) for b in brands]
        return BrandListResponse(
            items=items,
            meta=_build_meta(total, page, page_size, len(items)),
        )


# ============================================================================
# Product Service
# ============================================================================


class ProductService:
    """Business logic for products, variants, images, tags, and attributes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ProductRepository(session)
        self._variant_repo = VariantRepository(session)
        self._image_repo = ImageRepository(session)
        self._tag_repo = TagRepository(session)
        self._attr_repo = ProductAttributeRepository(session)
        self._category_repo = CategoryRepository(session)
        self._brand_repo = BrandRepository(session)

    # ---- Product CRUD ----

    async def create(self, data: ProductCreate) -> ProductDetailResponse:
        # Validate foreign keys
        category = await self._category_repo.get_by_id(data.category_id)
        if category is None:
            raise NotFoundError("Category")
        if data.brand_id:
            brand = await self._brand_repo.get_by_id(data.brand_id)
            if brand is None:
                raise NotFoundError("Brand")

        slug = data.slug or generate_slug(data.name)
        slug = await _ensure_unique_slug(slug, self._repo.slug_exists)

        product = Product(
            name=data.name,
            slug=slug,
            category_id=data.category_id,
            brand_id=data.brand_id,
            description=data.description,
            short_description=data.short_description,
            product_type=data.product_type,
            status=data.status,
            is_active=data.is_active,
            is_featured=data.is_featured,
            weight=data.weight,
            dimensions_json=data.dimensions_json,
            seo_title=data.seo_title,
            seo_description=data.seo_description,
            meta_keywords=data.meta_keywords,
        )
        product = await self._repo.create(product)

        # Create nested variants
        for v_data in data.variants:
            if await self._variant_repo.sku_exists(v_data.sku):
                raise ConflictError(f"SKU '{v_data.sku}' already exists")
            variant = ProductVariant(
                product_id=product.id,
                sku=v_data.sku,
                barcode=v_data.barcode,
                price=toman_to_rial(v_data.price),
                compare_at_price=toman_to_rial(v_data.compare_at_price),
                cost=toman_to_rial(v_data.cost),
                weight=v_data.weight,
                is_active=v_data.is_active,
                position=v_data.position,
                attributes=v_data.attributes,
            )
            await self._variant_repo.create(variant)

        # Create nested images
        for idx, i_data in enumerate(data.images):
            image = ProductImage(
                product_id=product.id,
                variant_id=i_data.variant_id,
                url=i_data.url,
                alt_text=i_data.alt_text,
                position=i_data.position or idx,
                is_primary=i_data.is_primary,
            )
            await self._image_repo.create(image)

        # Assign tags
        if data.tag_ids:
            await self._tag_repo.assign_to_product(product.id, data.tag_ids)

        # Assign attributes
        if data.attributes:
            attr_items = [
                {
                    "attribute_id": a.attribute_id,
                    "attribute_value_id": a.attribute_value_id,
                }
                for a in data.attributes
            ]
            await self._attr_repo.set_attributes(product.id, attr_items)

        # Re-fetch with all relations
        fresh_product = await self._repo.get_by_id(product.id, eager=True)
        if fresh_product is None:  # pragma: no cover — row was just created in this transaction
            raise NotFoundError("Product")
        product = fresh_product
        await logger.ainfo("product_created", product_id=str(product.id), slug=slug)
        await _publish_product_event(self._session, "ProductCreated", product.id)
        return await self._to_detail_response(product)

    async def update(self, product_id: uuid.UUID, data: ProductUpdate) -> ProductDetailResponse:
        product = await self._repo.get_by_id(product_id, eager=True)
        if product is None:
            raise NotFoundError("Product")

        update_data = data.model_dump(exclude_unset=True)

        # Validate FKs
        if "category_id" in update_data:
            cat = await self._category_repo.get_by_id(update_data["category_id"])
            if cat is None:
                raise NotFoundError("Category")
        if "brand_id" in update_data and update_data["brand_id"] is not None:
            brand = await self._brand_repo.get_by_id(update_data["brand_id"])
            if brand is None:
                raise NotFoundError("Brand")

        # Slug handling
        if "name" in update_data and "slug" not in update_data:
            update_data["slug"] = generate_slug(update_data["name"])
        if "slug" in update_data:
            update_data["slug"] = await _ensure_unique_slug(
                update_data["slug"], self._repo.slug_exists, exclude_id=product_id
            )

        # Relations are association tables, not columns: the `setattr` loop
        # below cannot express them, so they are applied explicitly and popped
        # from the payload first. Without this an edit that carried tags or
        # attributes silently kept the old set — and the product page's spec
        # tab and the faceted filters, which both read these tables, showed
        # stale data.
        tag_ids = update_data.pop("tag_ids", None)
        attributes = update_data.pop("attributes", None)

        for key, value in update_data.items():
            setattr(product, key, value)

        if tag_ids is not None:
            await self._tag_repo.assign_to_product(product.id, tag_ids)
        if attributes is not None:
            await self._attr_repo.set_attributes(
                product.id,
                [
                    {"attribute_id": a["attribute_id"],
                     "attribute_value_id": a["attribute_value_id"]}
                    for a in attributes
                ],
            )

        product = await self._repo.update(product)
        # `_to_detail_response` reads `product.product_attributes`, a lazy
        # collection that `get_by_id(eager=True)` above already loaded. The
        # `set_attributes` above deleted and re-inserted those rows, but the
        # in-memory list is unchanged, so the response would carry the previous
        # set — a write that looks like a no-op until the next read. `refresh`
        # re-queries it inside greenlet context; a bare `expire` here raises
        # MissingGreenlet, because the reload is a plain attribute access.
        await self._session.refresh(product, ["product_attributes"])
        await logger.ainfo("product_updated", product_id=str(product_id))
        await _publish_product_event(self._session, "ProductUpdated", product_id)
        return await self._to_detail_response(product)

    async def delete(self, product_id: uuid.UUID) -> None:
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")
        await self._repo.delete(product_id)
        await logger.ainfo("product_deleted", product_id=str(product_id))
        await _publish_product_event(self._session, "ProductDeleted", product_id)

    async def get_by_id(self, product_id: uuid.UUID) -> ProductDetailResponse:
        product = await self._repo.get_by_id(product_id, eager=True)
        if product is None:
            raise NotFoundError("Product")
        return await self._to_detail_response(product)

    async def get_by_slug(self, slug: str) -> ProductDetailResponse:
        product = await self._repo.get_by_slug(slug)
        if product is None:
            raise NotFoundError("Product")
        return await self._to_detail_response(product)

    async def list(self, filters: ProductFilterParams) -> ProductListResponse:
        tracer = get_tracer()
        with tracer.start_as_current_span("catalog.list_products") as span:
            if filters.category_id:
                span.set_attribute("catalog.category_id", str(filters.category_id))

            t0 = time.perf_counter()
            # Convert Toman prices to Rial for DB query
            min_price_rial = toman_to_rial(filters.min_price) if filters.min_price else None
            max_price_rial = toman_to_rial(filters.max_price) if filters.max_price else None

            products, total = await self._repo.get_filtered(
                q=filters.q,
                category_id=filters.category_id,
                category_slug=filters.category_slug,
                brand_id=filters.brand_id,
                brand_slug=filters.brand_slug,
                status=filters.status.value if filters.status else None,
                product_type=filters.product_type.value if filters.product_type else None,
                is_active=filters.is_active,
                is_featured=filters.is_featured,
                min_price_rial=min_price_rial,
                max_price_rial=max_price_rial,
                in_stock_only=filters.in_stock_only,
                tag_ids=filters.tag_ids,
                attribute_value_ids=filters.attribute_values,
                sort_by=filters.sort_by,
                sort_order=filters.sort_order,
                page=filters.page,
                page_size=filters.page_size,
                cursor=filters.cursor,
            )
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            span.set_attribute("catalog.cache_fetch_duration_ms", duration_ms)

            items = [self._to_list_response(p) for p in products]
            next_cursor = (
                str(products[-1].id) if products and len(products) == filters.page_size else None
            )
            meta = _build_meta(
                total, filters.page, filters.page_size, len(items), cursor=next_cursor
            )

            return ProductListResponse(items=items, meta=meta)

    # ---- Bulk operations ----

    async def bulk_update(self, data: ProductBulkUpdateRequest) -> int:
        items: list[dict[str, Any]] = []
        for item in data.items:
            d: dict[str, Any] = {"id": item.id}
            if item.status is not None:
                d["status"] = item.status
            if item.is_active is not None:
                d["is_active"] = item.is_active
            if item.is_featured is not None:
                d["is_featured"] = item.is_featured
            if item.category_id is not None:
                d["category_id"] = item.category_id
            items.append(d)
        count = await self._repo.bulk_update(items)
        await logger.ainfo("products_bulk_updated", count=count)
        return count

    async def bulk_delete(self, data: ProductBulkDeleteRequest) -> int:
        count = await self._repo.bulk_delete(data.ids)
        await logger.ainfo("products_bulk_deleted", count=count)
        return count

    # ---- Variants ----

    async def create_variant(self, product_id: uuid.UUID, data: VariantCreate) -> VariantResponse:
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")

        if await self._variant_repo.sku_exists(data.sku):
            raise ConflictError(f"SKU '{data.sku}' already exists")

        variant = ProductVariant(
            product_id=product_id,
            sku=data.sku,
            barcode=data.barcode,
            price=toman_to_rial(data.price),
            compare_at_price=toman_to_rial(data.compare_at_price),
            cost=toman_to_rial(data.cost),
            weight=data.weight,
            is_active=data.is_active,
            position=data.position,
            attributes=data.attributes,
        )
        variant = await self._variant_repo.create(variant)
        await logger.ainfo(
            "variant_created",
            variant_id=str(variant.id),
            product_id=str(product_id),
            sku=data.sku,
        )
        await _publish_product_event(self._session, "ProductUpdated", product_id)
        return VariantResponse.model_validate(variant)

    async def update_variant(self, variant_id: uuid.UUID, data: VariantUpdate) -> VariantResponse:
        variant = await self._variant_repo.get_by_id(variant_id)
        if variant is None:
            raise NotFoundError("Variant")

        update_data = data.model_dump(exclude_unset=True)

        # SKU uniqueness
        if "sku" in update_data and await self._variant_repo.sku_exists(
            update_data["sku"], exclude_id=variant_id
        ):
            raise ConflictError(f"SKU '{update_data['sku']}' already exists")

        # Convert money fields Toman → Rial
        for money_field in ("price", "compare_at_price", "cost"):
            if money_field in update_data and update_data[money_field] is not None:
                if update_data[money_field] == 0:
                    # 0 means "clear" for nullable fields
                    if money_field != "price":
                        update_data[money_field] = None
                else:
                    update_data[money_field] = toman_to_rial(update_data[money_field])

        for key, value in update_data.items():
            setattr(variant, key, value)

        variant = await self._variant_repo.update(variant)
        await logger.ainfo("variant_updated", variant_id=str(variant_id))
        await _publish_product_event(self._session, "ProductUpdated", variant.product_id)
        return VariantResponse.model_validate(variant)

    async def delete_variant(self, variant_id: uuid.UUID) -> None:
        variant = await self._variant_repo.get_by_id(variant_id)
        if variant is None:
            raise NotFoundError("Variant")
        product_id = variant.product_id
        await self._variant_repo.delete(variant_id)
        await logger.ainfo("variant_deleted", variant_id=str(variant_id))
        await _publish_product_event(self._session, "ProductUpdated", product_id)

    async def list_variants(self, product_id: uuid.UUID) -> builtins.list[VariantResponse]:
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")
        variants = await self._variant_repo.get_by_product(product_id)
        return [VariantResponse.model_validate(v) for v in variants]

    # ---- Images ----

    async def add_image(
        self, product_id: uuid.UUID, data: ProductImageCreate
    ) -> ProductImageResponse:
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")

        # If this image is primary, clear existing primary
        if data.is_primary:
            await self._image_repo.clear_primary(product_id)

        image = ProductImage(
            product_id=product_id,
            variant_id=data.variant_id,
            url=data.url,
            alt_text=data.alt_text,
            position=data.position,
            is_primary=data.is_primary,
        )
        image = await self._image_repo.create(image)
        await logger.ainfo(
            "image_added",
            image_id=str(image.id),
            product_id=str(product_id),
        )
        return ProductImageResponse.model_validate(image)

    async def remove_image(self, product_id: uuid.UUID, image_id: uuid.UUID) -> None:
        image = await self._image_repo.get_by_id(image_id)
        if image is None or image.product_id != product_id:
            raise NotFoundError("Image")
        await self._image_repo.delete(image_id)
        await logger.ainfo("image_removed", image_id=str(image_id))

    async def reorder_images(self, product_id: uuid.UUID, data: ImageReorderRequest) -> int:
        # Verify product exists
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")
        items = [(item.id, item.position) for item in data.items]
        count = await self._image_repo.bulk_update_positions(items)
        await logger.ainfo("images_reordered", product_id=str(product_id), count=count)
        return count

    async def list_images(self, product_id: uuid.UUID) -> builtins.list[ProductImageResponse]:
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")
        images = await self._image_repo.get_by_product(product_id)
        return [ProductImageResponse.model_validate(img) for img in images]

    # ---- Tags ----

    async def assign_tags(
        self, product_id: uuid.UUID, data: TagAssignRequest
    ) -> builtins.list[TagResponse]:
        product = await self._repo.get_by_id(product_id, eager=False)
        if product is None:
            raise NotFoundError("Product")
        await self._tag_repo.assign_to_product(product_id, data.tag_ids)
        tags = await self._tag_repo.get_product_tags(product_id)
        await logger.ainfo(
            "tags_assigned",
            product_id=str(product_id),
            tag_count=len(data.tag_ids),
        )
        return [TagResponse.model_validate(t) for t in tags]

    async def remove_tags(
        self, product_id: uuid.UUID, tag_ids: builtins.list[uuid.UUID]
    ) -> None:
        await self._tag_repo.remove_from_product(product_id, tag_ids)
        await logger.ainfo("tags_removed", product_id=str(product_id), tag_count=len(tag_ids))

    # ---- Response mappers ----

    def _to_list_response(self, product: Product) -> ProductResponse:
        """Map a Product model (with eagerly loaded relations) to a list-view response."""
        # Compute price range and primary image from loaded relations
        active_variants = [v for v in product.variants if v.is_active]
        min_price: int | None = None
        max_price: int | None = None
        if active_variants:
            prices = [v.price for v in active_variants]
            min_price = rial_to_toman(min(prices))
            max_price = rial_to_toman(max(prices))

        primary_image_url: str | None = None
        if product.images:
            primary_images = [img for img in product.images if img.is_primary]
            if primary_images:
                primary_image_url = primary_images[0].url
            else:
                # Fall back to lowest-position image
                sorted_images = sorted(product.images, key=lambda i: i.position)
                primary_image_url = sorted_images[0].url

        return ProductResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            category_id=product.category_id,
            brand_id=product.brand_id,
            short_description=product.short_description,
            product_type=product.product_type,
            status=product.status,
            is_active=product.is_active,
            is_featured=product.is_featured,
            primary_image_url=primary_image_url,
            min_price=min_price,
            max_price=max_price,
            variant_count=len(product.variants),
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

    async def _to_detail_response(self, product: Product) -> ProductDetailResponse:
        """Map a Product model (fully eager-loaded) to a detail response."""
        category_resp = (
            CategoryResponse.model_validate(product.category) if product.category else None
        )
        brand_resp = BrandResponse.model_validate(product.brand) if product.brand else None
        # Real-time availability per variant (Odoo "free_qty" concept): the
        # sellable on-hand count, so the PDP can show "in stock" vs "out of
        # stock" from actual inventory instead of treating is_active as stock.
        variant_ids = [v.id for v in product.variants]
        available_by_variant: dict[uuid.UUID, int] = {}
        if variant_ids:
            from app.modules.inventory.domain.models import InventoryItem

            inv_stmt = (
                select(InventoryItem.variant_id, func.sum(InventoryItem.available))
                .where(InventoryItem.variant_id.in_(variant_ids))
                .group_by(InventoryItem.variant_id)
            )
            available_by_variant = {
                row[0]: int(row[1] or 0) for row in await self._session.execute(inv_stmt)
            }

        variant_resps = [
            VariantResponse.model_validate(v).model_copy(
                update={"available": available_by_variant.get(v.id, 0)}
            )
            for v in product.variants
        ]
        image_resps = [ProductImageResponse.model_validate(img) for img in product.images]

        # Tags
        tag_resps: list[TagResponse] = []
        for pt in product.product_tags:
            if pt.tag:
                tag_resps.append(TagResponse.model_validate(pt.tag))

        # Attributes
        attr_resps: list[ProductAttributeResponse] = []
        for pa in product.product_attributes:
            attr_resps.append(
                ProductAttributeResponse(
                    id=pa.id,
                    product_id=pa.product_id,
                    attribute_id=pa.attribute_id,
                    attribute_value_id=pa.attribute_value_id,
                    attribute_name=pa.attribute.name if pa.attribute else None,
                    attribute_value=pa.attribute_value.value if pa.attribute_value else None,
                )
            )

        return ProductDetailResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            category_id=product.category_id,
            brand_id=product.brand_id,
            description=product.description,
            short_description=product.short_description,
            product_type=product.product_type,
            status=product.status,
            is_active=product.is_active,
            is_featured=product.is_featured,
            weight=product.weight,
            dimensions_json=product.dimensions_json,
            seo_title=product.seo_title,
            seo_description=product.seo_description,
            meta_keywords=product.meta_keywords,
            created_at=product.created_at,
            updated_at=product.updated_at,
            category=category_resp,
            brand=brand_resp,
            variants=variant_resps,
            images=image_resps,
            tags=tag_resps,
            product_attributes=attr_resps,
        )


# ============================================================================
# Tag Service
# ============================================================================


class TagService:
    """Business logic for tags (standalone)."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = TagRepository(session)

    async def create(self, data: TagCreate) -> TagResponse:
        slug = data.slug or generate_slug(data.name)
        slug = await _ensure_unique_slug(slug, self._repo.slug_exists)

        tag = Tag(name=data.name, slug=slug)
        tag = await self._repo.create(tag)
        await logger.ainfo("tag_created", tag_id=str(tag.id), slug=slug)
        return TagResponse.model_validate(tag)

    async def list(
        self, *, q: str | None = None, page: int = 1, page_size: int = 50
    ) -> TagListResponse:
        tags, total = await self._repo.get_all(q=q, page=page, page_size=page_size)
        items = [TagResponse.model_validate(t) for t in tags]
        return TagListResponse(
            items=items,
            meta=_build_meta(total, page, page_size, len(items)),
        )

    async def get_by_id(self, tag_id: uuid.UUID) -> TagResponse:
        tag = await self._repo.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag")
        return TagResponse.model_validate(tag)


# ============================================================================
# Attribute Service
# ============================================================================


class AttributeService:
    """Business logic for product attributes and their values."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = AttributeRepository(session)

    async def create(self, data: AttributeCreate) -> AttributeResponse:
        slug = data.slug or generate_slug(data.name)
        slug = await _ensure_unique_slug(slug, self._repo.slug_exists)

        attribute = Attribute(
            name=data.name,
            slug=slug,
            type=data.type,
            filterable=data.filterable,
            position=data.position,
        )
        attribute = await self._repo.create(attribute)

        # Create values
        for v_data in data.values:
            v_slug = v_data.slug or generate_slug(v_data.value)
            val = AttributeValue(
                attribute_id=attribute.id,
                value=v_data.value,
                slug=v_slug,
                position=v_data.position,
            )
            await self._repo.create_value(val)

        # Re-fetch with values. `AttributeRepository.create` reloads the
        # attribute with `selectinload(values)` while `values` is still an
        # empty list, and lazy="select" then caches that empty list on the
        # instance the identity map holds — so the reload hands back the same
        # object and the created values never reach the response. Expiring the
        # collection forces the reload to actually re-query.
        await self._repo.expire_values(attribute.id)
        fresh_attribute = await self._repo.get_by_id(attribute.id)
        if fresh_attribute is None:  # pragma: no cover — row was just created in this transaction
            raise NotFoundError("Attribute")
        attribute = fresh_attribute
        await logger.ainfo("attribute_created", attribute_id=str(attribute.id), slug=slug)
        return AttributeResponse.model_validate(attribute)

    async def list(
        self,
        *,
        filterable_only: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> AttributeListResponse:
        attributes, total = await self._repo.get_all(
            filterable_only=filterable_only, page=page, page_size=page_size
        )
        items = [AttributeResponse.model_validate(a) for a in attributes]
        return AttributeListResponse(
            items=items,
            meta=_build_meta(total, page, page_size, len(items)),
        )

    async def get_by_id(self, attribute_id: uuid.UUID) -> AttributeResponse:
        attribute = await self._repo.get_by_id(attribute_id)
        if attribute is None:
            raise NotFoundError("Attribute")
        return AttributeResponse.model_validate(attribute)

    async def update(
        self, attribute_id: uuid.UUID, data: AttributeUpdate
    ) -> AttributeResponse:
        attribute = await self._repo.get_by_id(attribute_id)
        if attribute is None:
            raise NotFoundError("Attribute")

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and "slug" not in update_data:
            update_data["slug"] = generate_slug(update_data["name"])
        if "slug" in update_data:
            update_data["slug"] = await _ensure_unique_slug(
                update_data["slug"], self._repo.slug_exists, exclude_id=attribute_id
            )

        for key, value in update_data.items():
            setattr(attribute, key, value)

        attribute = await self._repo.update(attribute)
        await logger.ainfo("attribute_updated", attribute_id=str(attribute_id))
        return AttributeResponse.model_validate(attribute)

    async def delete(self, attribute_id: uuid.UUID, *, force: bool = False) -> None:
        """Delete an attribute.

        ``product_attributes`` rows CASCADE on attribute deletion, so deleting
        one that products still use strips the specification off those
        products with no error anywhere.  Following the category/brand
        convention in this module, the delete is refused with the affected
        count, and the operator re-issues it with ``force=true`` to accept the
        loss deliberately.
        """
        attribute = await self._repo.get_by_id(attribute_id)
        if attribute is None:
            raise NotFoundError("Attribute")

        if not force:
            affected = await self._repo.count_products(attribute_id)
            if affected > 0:
                raise ConflictError(
                    f"Cannot delete attribute: {affected} product(s) use it. "
                    "Reassign those products first, or re-send with force=true "
                    "to delete it and strip the specification from them."
                )

        await self._repo.delete(attribute_id)
        await logger.ainfo("attribute_deleted", attribute_id=str(attribute_id), forced=force)

    async def list_values(
        self, attribute_id: uuid.UUID
    ) -> AttributeValueListResponse:
        if await self._repo.get_by_id(attribute_id) is None:
            raise NotFoundError("Attribute")
        values = await self._repo.get_values(attribute_id)
        return AttributeValueListResponse(
            items=[AttributeValueResponse.model_validate(v) for v in values]
        )

    async def create_value(
        self, attribute_id: uuid.UUID, data: AttributeValueCreate
    ) -> AttributeValueResponse:
        """Add one value to an existing attribute.

        ``(attribute_id, slug)`` is a unique constraint, so the generated slug
        is checked first and reported as a conflict rather than surfacing as a
        raw IntegrityError.
        """
        if await self._repo.get_by_id(attribute_id) is None:
            raise NotFoundError("Attribute")

        v_slug = data.slug or generate_slug(data.value)
        if await self._repo.value_slug_exists(attribute_id, v_slug):
            raise ConflictError(
                f"A value with slug '{v_slug}' already exists on this attribute."
            )

        value = await self._repo.create_value(
            AttributeValue(
                attribute_id=attribute_id,
                value=data.value,
                slug=v_slug,
                position=data.position,
            )
        )
        await logger.ainfo(
            "attribute_value_created",
            attribute_id=str(attribute_id),
            value_id=str(value.id),
            slug=v_slug,
        )
        await self._repo.expire_values(attribute_id)
        return AttributeValueResponse.model_validate(value)

    async def delete_value(self, attribute_id: uuid.UUID, value_id: uuid.UUID) -> None:
        """Remove one value.  Same CASCADE hazard as the attribute itself."""
        if await self._repo.get_by_id(attribute_id) is None:
            raise NotFoundError("Attribute")

        affected = await self._repo.count_value_products(attribute_id, value_id)
        if affected > 0:
            raise ConflictError(
                f"Cannot delete attribute value: {affected} product(s) use it. "
                "Reassign those products first."
            )

        if not await self._repo.delete_value(attribute_id, value_id):
            raise NotFoundError("AttributeValue")
        await self._repo.expire_values(attribute_id)
        await logger.ainfo(
            "attribute_value_deleted",
            attribute_id=str(attribute_id),
            value_id=str(value_id),
        )

