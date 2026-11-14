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
    AttributeValueUpdate,
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
    VariationAttributeGroup,
    VariationAttributeOption,
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
        resp = CategoryResponse.model_validate(category)
        if category.parent_id:
            parent = await self._repo.get_by_id(category.parent_id)
            if parent:
                resp.parent_name = parent.name
        return resp

    async def _update_children_paths(
        self, parent_id: uuid.UUID, parent_path: str, parent_depth: int
    ) -> None:
        children = await self._repo.get_children(parent_id)
        for child in children:
            child.depth = parent_depth + 1
            child.path = f"{parent_path}/{child.slug}"
            await self._session.flush()
            await self._update_children_paths(child.id, child.path, child.depth)

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
                curr_slug = update_data.get("slug", category.slug)
                if parent.id == category_id or (parent.path and curr_slug in parent.path.split("/")):
                    raise ValidationError("Circular parent reference detected")
                update_data["depth"] = parent.depth + 1
                slug_for_path = update_data.get("slug", category.slug)
                update_data["path"] = (
                    f"{parent.path}/{slug_for_path}" if parent.path else slug_for_path
                )
            else:
                update_data["depth"] = 0
                update_data["path"] = update_data.get("slug", category.slug)

        old_path = category.path
        for key, value in update_data.items():
            setattr(category, key, value)

        category = await self._repo.update(category)
        if "path" in update_data and category.path and old_path and category.path != old_path:
            await self._update_children_paths(category.id, category.path, category.depth)

        await logger.ainfo("category_updated", category_id=str(category_id))
        resp = CategoryResponse.model_validate(category)
        if category.parent_id:
            parent = await self._repo.get_by_id(category.parent_id)
            if parent:
                resp.parent_name = parent.name
        return resp

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
            resp = CategoryResponse.model_validate(category)
            if category.parent_id:
                parent = await self._repo.get_by_id(category.parent_id)
                if parent:
                    resp.parent_name = parent.name
            return resp

    async def get_by_slug(self, slug: str) -> CategoryResponse:
        category = await self._repo.get_by_slug(slug)
        if category is None:
            raise NotFoundError("Category")
        resp = CategoryResponse.model_validate(category)
        if category.parent_id:
            parent = await self._repo.get_by_id(category.parent_id)
            if parent:
                resp.parent_name = parent.name
        return resp

    async def list(
        self,
        *,
        is_active: bool | None = None,
        parent_id: uuid.UUID | None | EllipsisType = ...,
        page: int = 1,
        page_size: int = 50,
        q: str | None = None,
    ) -> CategoryListResponse:
        from sqlalchemy import func, select
        from app.modules.catalog.domain.models import Category, Product

        categories, total = await self._repo.get_all(
            is_active=is_active, parent_id=parent_id, page=page, page_size=page_size, q=q
        )
        cat_ids = [c.id for c in categories]
        parent_ids = {c.parent_id for c in categories if c.parent_id}
        counts: dict[uuid.UUID, int] = {}
        parent_names: dict[uuid.UUID, str] = {}
        if cat_ids:
            count_stmt = (
                select(Product.category_id, func.count(Product.id))
                .where(Product.category_id.in_(cat_ids))
                .group_by(Product.category_id)
            )
            count_res = await self._session.execute(count_stmt)
            counts = dict(count_res.all())

        if parent_ids:
            p_stmt = select(Category.id, Category.name).where(Category.id.in_(parent_ids))
            p_res = await self._session.execute(p_stmt)
            parent_names = dict(p_res.all())

        items = []
        for c in categories:
            resp = CategoryResponse.model_validate(c)
            resp.products_count = counts.get(c.id, 0)
            resp.parent_name = parent_names.get(c.parent_id)
            items.append(resp)

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
            stock_status=data.stock_status,
            weight=data.weight,
            dimensions_json=data.dimensions_json,
            seo_title=data.seo_title,
            seo_description=data.seo_description,
            meta_keywords=data.meta_keywords,
        )
        product = await self._repo.create(product)

        # Create nested variants
        for v_data in data.variants:
            # SKU is truly optional (owner directive): empty means the product
            # has NO warehouse code — nothing is generated. Uniqueness is only
            # enforced for a code the operator actually provided.
            sku = (v_data.sku or "").strip() or None
            if sku is not None and await self._variant_repo.sku_exists(sku):
                raise ConflictError(f"SKU '{sku}' already exists")
            variant = ProductVariant(
                product_id=product.id,
                sku=sku,
                barcode=v_data.barcode,
                price=toman_to_rial(v_data.price),
                compare_at_price=toman_to_rial(v_data.compare_at_price),
                cost=toman_to_rial(v_data.cost),
                usd_price=v_data.usd_price,
                usd_sale_price=v_data.usd_sale_price,
                weight=v_data.weight,
                is_active=v_data.is_active,
                position=v_data.position,
                attributes=v_data.attributes,
            )
            variant = await self._variant_repo.create(variant)
            # Keep the in-memory relationship in sync: the response mapper runs
            # in THIS session right after the insert, and a backref-less
            # product_id-only construction leaves product.variants empty there.
            product.variants.append(variant)
            # Inventory semantics (WooCommerce parity):
            #   stock given  → tracked stock, `available` = the given number;
            #   stock absent → UNLIMITED supply (track off): digital goods such
            #   as subscriptions are sellable without a warehouse count. The
            #   cart/checkout already gate on `track_inventory`, so untracked
            #   variants stay purchasable in any quantity. No magic default —
            #   an omitted number must never silently mean "10 in stock".
            from app.modules.inventory.domain.models import InventoryItem
            if v_data.stock is not None:
                inv = InventoryItem(
                    variant_id=variant.id,
                    available=v_data.stock,
                    track_inventory=True,
                )
            else:
                inv = InventoryItem(
                    variant_id=variant.id,
                    available=0,
                    track_inventory=False,
                )
            # WooCommerce "Low stock threshold" parity: only applied when the
            # operator typed one; otherwise the model default (5) stands.
            if v_data.low_stock_threshold is not None:
                inv.low_stock_threshold = v_data.low_stock_threshold
            # WooCommerce "Allow backorders?" parity.
            if v_data.backorder_allowed is not None:
                inv.backorder_allowed = v_data.backorder_allowed
            self._session.add(inv)

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
        variant_rows = update_data.pop("variants", None)

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
        if variant_rows is not None:
            await self._sync_variants(product, variant_rows)

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
        # Any product edit can change what the cached by-slug PDP shows —
        # name, variants (the variation manager), attributes/swatches — so a
        # product-level update must bust it the same way variant writes do.
        # Missing bust: an edited product kept serving the stale page for up
        # to five minutes while the admin panel showed the new values.
        await self._invalidate_pdp_cache(product_id)
        await _publish_product_event(self._session, "ProductUpdated", product_id)
        return await self._to_detail_response(product)

    async def _sync_variants(
        self, product: Product, rows: list[dict[str, Any]]
    ) -> None:
        """Apply the admin variation manager's rows to a product's variants.

        woo-variation-swatches parity: one product page hosts many purchasable
        options, so an edit must be able to add options (60/325/660 UC), reprice
        them, and retire removed ones — without hard-deleting anything order
        rows still reference. Rows with ``id`` patch in place; rows without one
        create; variants absent from the payload are soft-retired
        (``is_active=False``), which hides them from the storefront while
        keeping every cart/order foreign key valid.
        """
        from app.modules.inventory.domain.models import InventoryItem

        existing = {v.id: v for v in product.variants}
        keep_ids: set[uuid.UUID] = set()

        for idx, row in enumerate(rows):
            vid = row.get("id")
            if vid is not None and vid in existing:
                variant = existing[vid]
                if row.get("sku") is not None:
                    variant.sku = row["sku"]
                if row.get("price") is not None:
                    variant.price = toman_to_rial(row["price"])
                # 0 clears; omitted/None leaves untouched.
                if row.get("compare_at_price") is not None:
                    variant.compare_at_price = (
                        toman_to_rial(row["compare_at_price"])
                        if row["compare_at_price"] > 0
                        else None
                    )
                if "is_active" in row:
                    variant.is_active = bool(row["is_active"])
                variant.position = row.get("position", idx)
                # USD-managed prices (Nobitex sweep), same clear-convention as
                # VariantUpdate: 0 clears, omitted/None leaves untouched.
                if row.get("usd_price") is not None:
                    variant.usd_price = row["usd_price"] or None
                if row.get("usd_sale_price") is not None:
                    variant.usd_sale_price = row["usd_sale_price"] or None
                if row.get("attributes") is not None:
                    # MERGE, not replace: the manager edits ONE swatch group's
                    # keys; a full overwrite wiped every other group's mapping
                    # (a color key vanished the moment a UC price was saved).
                    # Explicit per-key removal can come later via null values.
                    merged = dict(variant.attributes or {})
                    merged.update(row["attributes"] or {})
                    variant.attributes = merged
                # Physical-goods knobs (barcode / weight) — the admin UI hides
                # them for digital products but the payload shape is shared.
                if row.get("barcode") is not None:
                    variant.barcode = row["barcode"] or None
                if row.get("weight") is not None:
                    variant.weight = row["weight"]
                # Per-option gallery image (Woo variation-image parity): an
                # empty string clears the variant-scoped image, a URL upserts
                # it, omitted leaves images untouched.
                if row.get("image_url") is not None:
                    from app.modules.catalog.domain.models import ProductImage

                    existing_image = (
                        await self._session.execute(
                            select(ProductImage).where(
                                ProductImage.variant_id == variant.id
                            )
                        )
                    ).scalars().first()
                    if row["image_url"]:
                        if existing_image is not None:
                            existing_image.url = row["image_url"]
                        else:
                            self._session.add(
                                ProductImage(
                                    product_id=product.id,
                                    variant_id=variant.id,
                                    url=row["image_url"],
                                    is_primary=True,
                                    position=99,
                                )
                            )
                    elif existing_image is not None:
                        await self._session.delete(existing_image)
                keep_ids.add(vid)
            else:
                variant = ProductVariant(
                    product_id=product.id,
                    sku=row.get("sku"),
                    price=toman_to_rial(row["price"] or 0),
                    compare_at_price=(
                        toman_to_rial(row["compare_at_price"])
                        if row.get("compare_at_price")
                        else None
                    ),
                    is_active=bool(row.get("is_active", True)),
                    position=row.get("position", idx),
                    attributes=row.get("attributes"),
                )
                self._session.add(variant)
                await self._session.flush()
                keep_ids.add(variant.id)

            # Stock: a provided number = tracked inventory at that count; no
            # ledger row yet → create one (same semantics as create_variant).
            inv = (
                await self._session.execute(
                    select(InventoryItem).where(
                        InventoryItem.variant_id == variant.id
                    )
                )
            ).scalar_one_or_none()
            if row.get("stock") is not None:
                if inv is None:
                    inv = InventoryItem(
                        variant_id=variant.id,
                        available=row["stock"],
                        track_inventory=True,
                    )
                    self._session.add(inv)
                else:
                    inv.available = row["stock"]
                    inv.track_inventory = True
            elif inv is None and variant.id not in existing:
                # A brand-new variant needs a ledger row even when the operator
                # left the stock box empty (untracked/unlimited), or the PDP's
                # availability lookup has nothing to read.
                inv = InventoryItem(
                    variant_id=variant.id,
                    available=0,
                    track_inventory=False,
                )
                self._session.add(inv)
            # Low-stock threshold + backorders live on the ledger row; create
            # it on demand so these knobs work for previously untracked
            # variants too (simple-product parity).
            if row.get("low_stock_threshold") is not None:
                if inv is None:
                    inv = InventoryItem(
                        variant_id=variant.id,
                        available=0,
                        track_inventory=False,
                    )
                    self._session.add(inv)
                inv.low_stock_threshold = row["low_stock_threshold"]
            if row.get("backorder_allowed") is not None:
                if inv is None:
                    inv = InventoryItem(
                        variant_id=variant.id,
                        available=0,
                        track_inventory=False,
                    )
                    self._session.add(inv)
                inv.backorder_allowed = bool(row["backorder_allowed"])
            # Manage-stock switch (simple-product editor parity): True =
            # counted stock, False = untracked/unlimited. The explicit OFF
            # must survive even when a stock number rides along — OFF wins.
            if row.get("manage_stock") is not None:
                if inv is None:
                    inv = InventoryItem(
                        variant_id=variant.id,
                        available=0,
                        track_inventory=False,
                    )
                    self._session.add(inv)
                if bool(row["manage_stock"]) is False:
                    inv.track_inventory = False
                elif row.get("stock") is None:
                    # ON without a count: start counting from the current
                    # on-hand (or zero) rather than silently staying untracked.
                    inv.track_inventory = True

        # Soft-retire everything the payload dropped (never hard-delete: cart
        # and order rows reference variant ids).
        for vid, variant in existing.items():
            if vid not in keep_ids:
                variant.is_active = False

        # The response mapper reads product.variants; new rows must be visible.
        await self._session.refresh(product, ["variants"])

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

            # Real stock for the page (one ledger query for the whole page) —
            # the admin table's stock column read a field the list never
            # provided and flagged EVERY product "out of stock". Same
            # semantics as the detail mapper: tracked variants expose their
            # available count; untracked ones expose None (unlimited supply).
            stock_by_product: dict[uuid.UUID, tuple[int | None, int | None]] = {}
            all_variant_ids = [v.id for p in products for v in p.variants if v.is_active]
            if all_variant_ids:
                from app.modules.inventory.domain.models import InventoryItem

                inv_stmt = (
                    select(
                        ProductVariant.id,
                        ProductVariant.product_id,
                        InventoryItem.track_inventory,
                        func.sum(InventoryItem.available),
                        func.max(InventoryItem.low_stock_threshold),
                    )
                    .join(InventoryItem, InventoryItem.variant_id == ProductVariant.id)
                    .where(ProductVariant.id.in_(all_variant_ids))
                    .group_by(
                        ProductVariant.id,
                        ProductVariant.product_id,
                        InventoryItem.track_inventory,
                    )
                )
                for v_id, v_pid, tracked, total, v_thr in (
                    await self._session.execute(inv_stmt)
                ).all():
                    stock_by_product[v_pid] = (
                        int(total or 0) if tracked else None,
                        int(v_thr) if (tracked and v_thr is not None) else None,
                    )
            items = [
                self._to_list_response(
                    p,
                    stock=(stock_by_product.get(p.id) or (None, None))[0],
                    low_stock_threshold=(stock_by_product.get(p.id) or (None, None))[1],
                )
                for p in products
            ]
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
            usd_price=data.usd_price,
            usd_sale_price=data.usd_sale_price,
            weight=data.weight,
            is_active=data.is_active,
            position=data.position,
            attributes=data.attributes,
        )
        variant = await self._variant_repo.create(variant)
        # Same inventory semantics as the nested product-create path: a given
        # stock number = tracked stock; omitted = untracked/unlimited. No
        # magic default — an omitted number must never mean "10 in stock".
        from app.modules.inventory.domain.models import InventoryItem
        if data.stock is not None:
            inv = InventoryItem(
                variant_id=variant.id,
                available=data.stock,
                track_inventory=True,
            )
        else:
            inv = InventoryItem(
                variant_id=variant.id,
                available=0,
                track_inventory=False,
            )
        if data.low_stock_threshold is not None:
            inv.low_stock_threshold = data.low_stock_threshold
        if data.backorder_allowed is not None:
            inv.backorder_allowed = data.backorder_allowed
        self._session.add(inv)
        await logger.ainfo(
            "variant_created",
            variant_id=str(variant.id),
            product_id=str(product_id),
            sku=data.sku,
        )
        await self._invalidate_pdp_cache(product_id)
        await _publish_product_event(self._session, "ProductUpdated", product_id)
        return VariantResponse.model_validate(variant)

    async def _invalidate_pdp_cache(self, product_id: uuid.UUID) -> None:
        """Drop the cached by-slug PDP payload after a variant-level change.

        GET /products/by-slug/{slug} caches for 300s; without this bust an
        edited SKU or price kept serving the stale page for up to five
        minutes while the admin panel showed the new values.
        """
        from app.core.cache.redis import cache_delete

        product = await self._repo.get_by_id(product_id, eager=False)
        if product is not None and product.slug:
            await cache_delete(f"catalog:product:slug:v2:{product.slug}")

    async def update_variant(self, variant_id: uuid.UUID, data: VariantUpdate) -> VariantResponse:
        variant = await self._variant_repo.get_by_id(variant_id)
        if variant is None:
            raise NotFoundError("Variant")

        update_data = data.model_dump(exclude_unset=True)

        # SKU uniqueness — only for a provided code; a submitted NULL clears
        # the SKU entirely (owner directive: empty means no warehouse code).
        if (
            "sku" in update_data
            and update_data["sku"] is not None
            and await self._variant_repo.sku_exists(
                update_data["sku"], exclude_id=variant_id
            )
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

        # USD source prices: no unit conversion (they are USD), but 0 means
        # "clear" exactly like the nullable price fields above — clearing
        # usd_price is how an operator takes a variant OUT of the automatic
        # USD→Toman sweep.
        for usd_field in ("usd_price", "usd_sale_price"):
            if usd_field in update_data and update_data[usd_field] is not None:
                if update_data[usd_field] == 0:
                    update_data[usd_field] = None

        for key, value in update_data.items():
            setattr(variant, key, value)

        variant = await self._variant_repo.update(variant)
        # WooCommerce inventory-ledger updates: low-stock threshold, stock
        # quantity (with the concurrent-edit guard), and backorders.
        if any(
            key in update_data
            for key in ("low_stock_threshold", "stock", "backorder_allowed")
        ):
            from app.modules.inventory.domain.models import InventoryItem

            inv_row = (
                await self._session.execute(
                    select(InventoryItem).where(
                        InventoryItem.variant_id == variant_id
                    )
                )
            ).scalar_one_or_none()
            if inv_row is not None:
                # A submitted null CLEARS the alert (owner directive: empty
                # field = no low-stock alert for this product).
                if "low_stock_threshold" in update_data:
                    inv_row.low_stock_threshold = update_data["low_stock_threshold"]
                if "backorder_allowed" in update_data and update_data["backorder_allowed"] is not None:
                    inv_row.backorder_allowed = update_data["backorder_allowed"]
                if update_data.get("stock") is not None:
                    # Concurrent-edit guard (WooCommerce `_original_stock`):
                    # the editor sends the quantity it was opened with; if the
                    # ledger moved since, reject instead of clobbering.
                    if (
                        update_data.get("original_stock") is not None
                        and inv_row.available != update_data["original_stock"]
                    ):
                        raise ConflictError(
                            detail=(
                                "موجودی از زمان باز شدن فرم تغییر کرده است. "
                                f"موجودی فعلی: {inv_row.available} عدد — "
                                "فرم را ببندید و دوباره باز کنید."
                            )
                        )
                    inv_row.available = update_data["stock"]
                    inv_row.track_inventory = True
                await self._session.flush()
        await logger.ainfo("variant_updated", variant_id=str(variant_id))
        await self._invalidate_pdp_cache(variant.product_id)
        await _publish_product_event(self._session, "ProductUpdated", variant.product_id)
        return VariantResponse.model_validate(variant)

    async def delete_variant(self, variant_id: uuid.UUID) -> None:
        variant = await self._variant_repo.get_by_id(variant_id)
        if variant is None:
            raise NotFoundError("Variant")
        product_id = variant.product_id
        await self._variant_repo.delete(variant_id)
        await logger.ainfo("variant_deleted", variant_id=str(variant_id))
        await self._invalidate_pdp_cache(product_id)
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

    def _to_list_response(
        self,
        product: Product,
        *,
        stock: int | None = None,
        low_stock_threshold: int | None = None,
    ) -> ProductResponse:
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
            category_name=product.category.name if product.category else None,
            category_slug=product.category.slug if product.category else None,
            brand_id=product.brand_id,
            short_description=product.short_description,
            product_type=product.product_type,
            status=product.status,
            is_active=product.is_active,
            is_featured=product.is_featured,
            stock_status=product.stock_status,
            primary_image_url=primary_image_url,
            min_price=min_price,
            max_price=max_price,
            variant_count=len(product.variants),
            stock=stock,
            low_stock_threshold=low_stock_threshold,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

    async def _to_detail_response(self, product: Product) -> ProductDetailResponse:
        """Map a Product model (fully eager-loaded) to a detail response."""
        category_resp = (
            CategoryResponse.model_validate(product.category) if product.category else None
        )
        if category_resp and product.category and product.category.parent_id:
            parent_cat = await CategoryRepository(self._session).get_by_id(product.category.parent_id)
            if parent_cat:
                category_resp.parent_name = parent_cat.name
        brand_resp = BrandResponse.model_validate(product.brand) if product.brand else None
        # Price range from active variants — the list mapper always had this,
        # the detail mapper never did, so `min_price` was null on EVERY
        # product page. The PDP's Product JSON-LD reads min_price for its
        # Offer, so every rich result shipped "price": 0 (Google rejects a
        # zero-priced offer) while the page displayed the real price. Toman
        # at the boundary, same as the list mapper.
        active_variants = [v for v in product.variants if v.is_active]
        min_price: int | None = None
        max_price: int | None = None
        if active_variants:
            prices = [v.price for v in active_variants]
            min_price = rial_to_toman(min(prices))
            max_price = rial_to_toman(max(prices))

        # Real-time availability per variant (Odoo "free_qty" concept): the
        # sellable on-hand count, so the PDP can show "in stock" vs "out of
        # stock" from actual inventory instead of treating is_active as stock.
        # Untracked variants (unlimited supply, digital goods) expose
        # available=None: the storefront reads null as "always buyable" and
        # the raw 0 an untracked row carries must not read as out-of-stock.
        variant_ids = [v.id for v in product.variants]
        available_by_variant: dict[uuid.UUID, object] = {}
        threshold_by_variant: dict[uuid.UUID, int | None] = {}
        track_by_variant: dict[uuid.UUID, bool] = {}
        backorder_by_variant: dict[uuid.UUID, bool] = {}
        # WooCommerce parity: an UNTRACKED product respects its manual stock
        # status — "outofstock" reads as unavailable (available=0) on the
        # storefront instead of the unconditional "always buyable" of old.
        if variant_ids:
            from app.modules.inventory.domain.models import InventoryItem

            # A variant has ONE ledger row; group by it and pull the low-stock
            # threshold alongside so the admin editor can render the
            # WooCommerce-style "manage stock" switch from real data.
            inv_stmt = (
                select(
                    InventoryItem.variant_id,
                    InventoryItem.track_inventory,
                    func.sum(InventoryItem.available),
                    func.max(InventoryItem.low_stock_threshold),
                    func.bool_or(InventoryItem.backorder_allowed),
                )
                .where(InventoryItem.variant_id.in_(variant_ids))
                .group_by(InventoryItem.variant_id, InventoryItem.track_inventory)
            )
            inv_rows = (await self._session.execute(inv_stmt)).all()
            for inv_row in inv_rows:
                # Untracked → None (unlimited supply), ALWAYS — including when
                # the operator set the manual وضعیت عرضه to "outofstock". That
                # state used to fold into available=0 here, and the admin
                # editor's "number = manage stock ON" rule then flipped the
                # مدیریت موجودی switch on by itself after every save. The
                # manual state rides on product.stock_status (in this same
                # payload) and the cart enforces it server-side.
                available_by_variant[inv_row[0]] = (
                    int(inv_row[2] or 0) if inv_row[1] else None
                )
                threshold_by_variant[inv_row[0]] = (
                    int(inv_row[3]) if inv_row[3] is not None else None
                )
                track_by_variant[inv_row[0]] = bool(inv_row[1])
                backorder_by_variant[inv_row[0]] = bool(inv_row[4])

        variant_resps = [
            VariantResponse.model_validate(v).model_copy(
                update={
                    "available": available_by_variant.get(v.id, 0),
                    "low_stock_threshold": threshold_by_variant.get(v.id),
                    "track_inventory": track_by_variant.get(v.id),
                    "backorder_allowed": backorder_by_variant.get(v.id),
                }
            )
            for v in product.variants
        ]
        image_resps = [ProductImageResponse.model_validate(img) for img in product.images]

        # The schema declares `primary_image_url` and the PDP reads it for
        # og:image and the Product JSON-LD image — but this mapper never
        # filled it, so every product page shipped no image (found live
        # 2026-10-10 during the SEO audit). Same primary/lowest-position
        # rule as the list mapper; None when the product has no images.
        primary_image_url: str | None = None
        if product.images:
            primary_images = [img for img in product.images if img.is_primary]
            if primary_images:
                primary_image_url = primary_images[0].url
            else:
                primary_image_url = sorted(
                    product.images, key=lambda i: i.position
                )[0].url

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

        # Variation swatch groups (woo-variation-swatches parity): group the
        # product's attribute associations by attribute, keep each group's
        # display type and per-option swatch payload, order by the attribute
        # position then the value position — the PDP renders one swatch row
        # per group and the shopper's combination selects the variant.
        groups_by_id: dict[uuid.UUID, VariationAttributeGroup] = {}
        group_order: list[uuid.UUID] = []
        for pa in product.product_attributes:
            attr = pa.attribute
            val = pa.attribute_value
            if attr is None or val is None:
                continue
            group = groups_by_id.get(attr.id)
            if group is None:
                group = VariationAttributeGroup(
                    attribute_id=attr.id,
                    name=attr.name,
                    slug=attr.slug,
                    type=attr.type,
                    options=[],
                )
                groups_by_id[attr.id] = group
                group_order.append(attr.id)
            group.options.append(
                VariationAttributeOption(
                    value_id=val.id,
                    value=val.value,
                    slug=val.slug,
                    color=val.color,
                    image_url=val.image_url,
                    tooltip=val.tooltip,
                )
            )
        variation_groups = [
            groups_by_id[aid]
            for aid in sorted(
                group_order,
                key=lambda aid: (groups_by_id[aid].name.lower()),
            )
        ]

        # Option ORDER follows the variants' positions (woo-variation-swatches
        # parity): the admin drags the option rows in the variation manager,
        # the save stores those positions on the variants, and the storefront
        # swatches render in exactly that order. An option whose variant is
        # missing/retired keeps its relative place at the end.
        for group in variation_groups:
            pos_by_option = {}
            for variant in product.variants:
                attrs = variant.attributes or {}
                option_slug = attrs.get(group.slug)
                if option_slug is not None and option_slug not in pos_by_option:
                    pos_by_option[str(option_slug)] = variant.position
            group.options.sort(
                key=lambda o: (pos_by_option.get(o.slug, 10_000),)
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
            stock_status=product.stock_status,
            weight=product.weight,
            dimensions_json=product.dimensions_json,
            seo_title=product.seo_title,
            seo_description=product.seo_description,
            meta_keywords=product.meta_keywords,
            min_price=min_price,
            max_price=max_price,
            primary_image_url=primary_image_url,
            created_at=product.created_at,
            updated_at=product.updated_at,
            category=category_resp,
            brand=brand_resp,
            variants=variant_resps,
            images=image_resps,
            tags=tag_resps,
            product_attributes=attr_resps,
            variation_attributes=variation_groups,
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
        # Kept for the value-level writes that touch variants' JSONB keys
        # (orphan-key cleanup) and the value update lookup.
        self._session = session

    async def create(self, data: AttributeCreate) -> AttributeResponse:
        # Duplicate-name guard (WooCommerce identity rule): two same-named
        # attributes are the «رنگ دموی سواچ» twice trap — operators then cannot
        # tell which one the variation manager should use. Names are compared
        # case-insensitively in Python: the attribute table holds a handful of
        # rows, and the store-wide uniqueness is the operator's mental model.
        all_attrs = await self._repo.get_all(page_size=500)
        normalized = data.name.strip().casefold()
        for existing in all_attrs[0]:
            if existing.name.strip().casefold() == normalized:
                raise ConflictError(
                    f"An attribute named '{existing.name}' already exists. "
                    "Open it in the variation manager instead of creating a twin."
                )

        slug = data.slug or generate_slug(data.name)

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
                color=v_data.color,
                image_url=v_data.image_url,
                tooltip=v_data.tooltip,
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
        # Orphan-key cleanup (variation swatches): a force delete cascades the
        # product_attributes rows away, but variants keep a dead
        # ``{attribute_slug: ...}`` JSONB key. A surviving key makes the admin
        # variation manager match nothing and the PDP swatch group vanish, so
        # the key must die with the attribute.
        if force:
            from app.modules.catalog.domain.models import ProductVariant

            orphan_rows = await self._session.execute(
                select(ProductVariant).where(
                    ProductVariant.attributes.has_key(attribute.slug)
                )
            )
            touched = 0
            for variant in orphan_rows.scalars().all():
                attrs = dict(variant.attributes or {})
                attrs.pop(attribute.slug, None)
                variant.attributes = attrs
                touched += 1
            if touched:
                await logger.ainfo(
                    "variant_orphan_attribute_keys_stripped",
                    attribute_slug=attribute.slug,
                    variants=touched,
                )
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
                color=data.color,
                image_url=data.image_url,
                tooltip=data.tooltip,
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

    async def update_value(
        self, attribute_id: uuid.UUID, value_id: uuid.UUID, data: AttributeValueUpdate
    ) -> AttributeValueResponse:
        """Update one value — label, position, and its swatch payloads
        (color hex / image URL / tooltip). The swatch editor on the admin
        variation manager calls this; without it a mis-colored swatch could
        only be fixed by deleting and recreating the value (losing every
        product association)."""
        value = (
            await self._session.execute(
                select(AttributeValue).where(
                    AttributeValue.id == value_id,
                    AttributeValue.attribute_id == attribute_id,
                )
            )
        ).scalar_one_or_none()
        if value is None:
            raise NotFoundError("AttributeValue")

        data_dump = data.model_dump(exclude_unset=True)
        if "value" in data_dump and data_dump["value"]:
            value.value = data_dump["value"]
            if "slug" not in data_dump:
                value.slug = generate_slug(data_dump["value"])
        if "slug" in data_dump and data_dump["slug"]:
            value.slug = data_dump["slug"]
        if "position" in data_dump and data_dump["position"] is not None:
            value.position = data_dump["position"]
        if "color" in data_dump:
            value.color = data_dump["color"]
        if "image_url" in data_dump:
            value.image_url = data_dump["image_url"]
        if "tooltip" in data_dump:
            value.tooltip = data_dump["tooltip"]

        await self._session.flush()
        await self._repo.expire_values(attribute_id)
        await logger.ainfo(
            "attribute_value_updated",
            attribute_id=str(attribute_id),
            value_id=str(value_id),
        )
        return AttributeValueResponse.model_validate(value)

    async def delete_value(
        self, attribute_id: uuid.UUID, value_id: uuid.UUID, *, force: bool = False
    ) -> None:
        """Remove one value.

        Refused with 409 while products use it, naming how many; with
        ``force=true`` the product→value links are detached first (those
        products keep every other specification value they have) and the
        value disappears from the catalogue and from every storefront filter
        built on it — WooCommerce term-delete parity.
        """
        if await self._repo.get_by_id(attribute_id) is None:
            raise NotFoundError("Attribute")

        affected = await self._repo.count_value_products(attribute_id, value_id)
        if affected > 0 and not force:
            raise ConflictError(
                f"Cannot delete attribute value: {affected} product(s) use it. "
                "Reassign those products first, or re-send with force=true "
                "to detach it from them and delete it anyway."
            )

        # Resolve the option slug BEFORE deletion — the variants' JSONB is
        # keyed by it, and after the row is gone it is unrecoverable.
        deleted_value = (
            await self._session.execute(
                select(AttributeValue).where(AttributeValue.id == value_id)
            )
        ).scalar_one_or_none()
        value_slug_used = deleted_value.slug if deleted_value else None

        if not await self._repo.delete_value(attribute_id, value_id):
            raise NotFoundError("AttributeValue")
        if affected > 0 and force:
            await self._repo.detach_value_from_products(attribute_id, value_id)
        # Orphan-key cleanup (variation swatches): variants mapping THIS value
        # under the attribute's key lose that mapping with the value itself,
        # exactly as the attribute-level force delete strips the whole key.
        if force:
            attr = await self._repo.get_by_id(attribute_id)
            if attr is not None and value_slug_used is not None:
                from app.modules.catalog.domain.models import ProductVariant

                orphan_rows = await self._session.execute(
                    select(ProductVariant).where(
                        ProductVariant.attributes.has_key(attr.slug)
                    )
                )
                touched = 0
                for variant in orphan_rows.scalars().all():
                    attrs = dict(variant.attributes or {})
                    if str(attrs.get(attr.slug)) == value_slug_used:
                        attrs.pop(attr.slug, None)
                        variant.attributes = attrs
                        touched += 1
                if touched:
                    await logger.ainfo(
                        "variant_orphan_value_keys_stripped",
                        attribute_slug=attr.slug,
                        value_slug_used=value_slug_used,
                        variants=touched,
                    )
        await self._repo.expire_values(attribute_id)
        await logger.ainfo(
            "attribute_value_deleted",
            attribute_id=str(attribute_id),
            value_id=str(value_id),
            forced=force,
            detached_products=affected,
        )

