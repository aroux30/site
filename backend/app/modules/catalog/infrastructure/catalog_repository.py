"""Repository layer for the Catalog module.

Implements the repository pattern on top of async SQLAlchemy.  Each repository
exposes query methods that return model instances; the service layer is
responsible for mapping them to Pydantic schemas.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import joinedload, selectinload

from app.modules.catalog.domain.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductAttribute,
    ProductImage,
    ProductTag,
    ProductVariant,
    Tag,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ============================================================================
# Category Repository
# ============================================================================


class CategoryRepository:
    """Data-access methods for :class:`Category`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---- Single lookups ----

    async def get_by_id(self, category_id: uuid.UUID) -> Category | None:
        stmt = select(Category).where(Category.id == category_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).select_from(Category).where(Category.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Category.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    # ---- Lists ----

    async def get_all(
        self,
        *,
        is_active: bool | None = None,
        parent_id: uuid.UUID | None = ...,  # type: ignore[assignment]
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[Category], int]:
        stmt = select(Category)
        count_stmt = select(func.count()).select_from(Category)

        if is_active is not None:
            stmt = stmt.where(Category.is_active == is_active)
            count_stmt = count_stmt.where(Category.is_active == is_active)

        # parent_id sentinel: ... means "don't filter", None means "top-level"
        if parent_id is not ...:
            if parent_id is None:
                stmt = stmt.where(Category.parent_id.is_(None))
                count_stmt = count_stmt.where(Category.parent_id.is_(None))
            else:
                stmt = stmt.where(Category.parent_id == parent_id)
                count_stmt = count_stmt.where(Category.parent_id == parent_id)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            stmt.order_by(Category.position, Category.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def get_children(self, parent_id: uuid.UUID) -> Sequence[Category]:
        stmt = (
            select(Category)
            .where(Category.parent_id == parent_id)
            .order_by(Category.position, Category.name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_tree(self, *, is_active: bool | None = None) -> Sequence[Category]:
        """Return all categories ordered for tree construction."""
        stmt = select(Category).order_by(Category.depth, Category.position, Category.name)
        if is_active is not None:
            stmt = stmt.where(Category.is_active == is_active)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ---- Mutations ----

    async def create(self, category: Category) -> Category:
        self._session.add(category)
        await self._session.flush()
        await self._session.refresh(category)
        return category

    async def update(self, category: Category) -> Category:
        await self._session.flush()
        await self._session.refresh(category)
        return category

    async def delete(self, category_id: uuid.UUID) -> bool:
        stmt = delete(Category).where(Category.id == category_id)
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def bulk_update_positions(self, items: list[tuple[uuid.UUID, int]]) -> int:
        """Update positions for multiple categories.  Returns affected count."""
        updated = 0
        for cat_id, position in items:
            stmt = update(Category).where(Category.id == cat_id).values(position=position)
            result = await self._session.execute(stmt)
            updated += result.rowcount or 0
        await self._session.flush()
        return updated

    async def has_products(self, category_id: uuid.UUID) -> bool:
        stmt = select(func.count()).select_from(Product).where(Product.category_id == category_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def has_children(self, category_id: uuid.UUID) -> bool:
        stmt = select(func.count()).select_from(Category).where(Category.parent_id == category_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0


# ============================================================================
# Brand Repository
# ============================================================================


class BrandRepository:
    """Data-access methods for :class:`Brand`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, brand_id: uuid.UUID) -> Brand | None:
        stmt = select(Brand).where(Brand.id == brand_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Brand | None:
        stmt = select(Brand).where(Brand.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).select_from(Brand).where(Brand.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Brand.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def get_all(
        self,
        *,
        is_active: bool | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[Brand], int]:
        stmt = select(Brand)
        count_stmt = select(func.count()).select_from(Brand)

        if is_active is not None:
            stmt = stmt.where(Brand.is_active == is_active)
            count_stmt = count_stmt.where(Brand.is_active == is_active)

        if q:
            like_q = f"%{q}%"
            filter_cond = or_(
                Brand.name.ilike(like_q),
                Brand.slug.ilike(like_q),
            )
            stmt = stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(Brand.name).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def create(self, brand: Brand) -> Brand:
        self._session.add(brand)
        await self._session.flush()
        await self._session.refresh(brand)
        return brand

    async def update(self, brand: Brand) -> Brand:
        await self._session.flush()
        await self._session.refresh(brand)
        return brand

    async def delete(self, brand_id: uuid.UUID) -> bool:
        stmt = delete(Brand).where(Brand.id == brand_id)
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def has_products(self, brand_id: uuid.UUID) -> bool:
        stmt = select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0


# ============================================================================
# Product Repository
# ============================================================================


class ProductRepository:
    """Data-access methods for :class:`Product` with complex queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---- Eager-loading helpers ----

    @staticmethod
    def _list_options():
        """Lightweight eager-load options for list views."""
        return [
            joinedload(Product.category),
            joinedload(Product.brand),
            selectinload(Product.variants),
            selectinload(Product.images),
        ]

    @staticmethod
    def _detail_options():
        """Full eager-load options for detail views."""
        return [
            joinedload(Product.category),
            joinedload(Product.brand),
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.product_tags).joinedload(ProductTag.tag),
            selectinload(Product.product_attributes).joinedload(ProductAttribute.attribute),
            selectinload(Product.product_attributes).joinedload(ProductAttribute.attribute_value),
        ]

    # ---- Single lookups ----

    async def get_by_id(self, product_id: uuid.UUID, *, eager: bool = True) -> Product | None:
        stmt = select(Product).where(Product.id == product_id)
        if eager:
            for opt in self._detail_options():
                stmt = stmt.options(opt)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(Product.slug == slug)
        for opt in self._detail_options():
            stmt = stmt.options(opt)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).select_from(Product).where(Product.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    # ---- Filtered list ----

    async def get_filtered(
        self,
        *,
        q: str | None = None,
        category_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        brand_id: uuid.UUID | None = None,
        brand_slug: str | None = None,
        status: str | None = None,
        product_type: str | None = None,
        is_active: bool | None = None,
        is_featured: bool | None = None,
        min_price_rial: int | None = None,
        max_price_rial: int | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        attribute_value_ids: list[uuid.UUID] | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> tuple[Sequence[Product], int]:
        """Return filtered, sorted, paginated products with total count."""
        conditions: list[Any] = []

        # Text search
        if q:
            like_q = f"%{q}%"
            conditions.append(
                or_(
                    Product.name.ilike(like_q),
                    Product.slug.ilike(like_q),
                    Product.description.ilike(like_q),
                    Product.short_description.ilike(like_q),
                    Product.meta_keywords.ilike(like_q),
                )
            )

        # Category filter
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        elif category_slug:
            subq = select(Category.id).where(Category.slug == category_slug).scalar_subquery()
            conditions.append(Product.category_id == subq)

        # Brand filter
        if brand_id is not None:
            conditions.append(Product.brand_id == brand_id)
        elif brand_slug:
            subq = select(Brand.id).where(Brand.slug == brand_slug).scalar_subquery()
            conditions.append(Product.brand_id == subq)

        # Enum filters
        if status is not None:
            conditions.append(Product.status == status)
        if product_type is not None:
            conditions.append(Product.product_type == product_type)
        if is_active is not None:
            conditions.append(Product.is_active == is_active)
        if is_featured is not None:
            conditions.append(Product.is_featured == is_featured)

        # Price range filter (against variants)
        if min_price_rial is not None or max_price_rial is not None:
            price_subq = select(ProductVariant.product_id).where(
                ProductVariant.is_active.is_(True)
            )
            if min_price_rial is not None:
                price_subq = price_subq.where(ProductVariant.price >= min_price_rial)
            if max_price_rial is not None:
                price_subq = price_subq.where(ProductVariant.price <= max_price_rial)
            price_subq = price_subq.group_by(ProductVariant.product_id).subquery()
            conditions.append(Product.id.in_(select(price_subq.c.product_id)))

        # Tag filter
        if tag_ids:
            tag_subq = (
                select(ProductTag.product_id)
                .where(ProductTag.tag_id.in_(tag_ids))
                .group_by(ProductTag.product_id)
                .having(func.count(ProductTag.tag_id.distinct()) >= len(tag_ids))
                .subquery()
            )
            conditions.append(Product.id.in_(select(tag_subq.c.product_id)))

        # Attribute filter
        if attribute_value_ids:
            attr_subq = (
                select(ProductAttribute.product_id)
                .where(ProductAttribute.attribute_value_id.in_(attribute_value_ids))
                .group_by(ProductAttribute.product_id)
                .having(
                    func.count(ProductAttribute.attribute_value_id.distinct())
                    >= len(attribute_value_ids)
                )
                .subquery()
            )
            conditions.append(Product.id.in_(select(attr_subq.c.product_id)))

        where_clause = and_(*conditions) if conditions else True  # type: ignore[arg-type]

        # Count query
        count_stmt = select(func.count()).select_from(Product).where(where_clause)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Sorting
        sort_column_map = {
            "name": Product.name,
            "created_at": Product.created_at,
            "updated_at": Product.updated_at,
        }
        sort_col = sort_column_map.get(sort_by, Product.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()

        # Cursor-based pagination
        if cursor:
            try:
                cursor_id = uuid.UUID(cursor)
                cursor_product = await self.get_by_id(cursor_id, eager=False)
                if cursor_product:
                    cursor_val = getattr(cursor_product, sort_by, cursor_product.created_at)
                    if sort_order == "desc":
                        conditions.append(
                            or_(
                                sort_col < cursor_val,
                                and_(sort_col == cursor_val, Product.id < cursor_id),
                            )
                        )
                    else:
                        conditions.append(
                            or_(
                                sort_col > cursor_val,
                                and_(sort_col == cursor_val, Product.id > cursor_id),
                            )
                        )
                    where_clause = and_(*conditions) if conditions else True  # type: ignore[arg-type]
            except (ValueError, AttributeError):
                pass  # Invalid cursor – fall back to offset

        # Data query with eager loading
        data_stmt = select(Product).where(where_clause)
        for opt in self._list_options():
            data_stmt = data_stmt.options(opt)

        if not cursor:
            data_stmt = data_stmt.offset((page - 1) * page_size)

        data_stmt = data_stmt.order_by(order, Product.id.desc()).limit(page_size)

        result = await self._session.execute(data_stmt)
        products = result.unique().scalars().all()

        return products, total

    # ---- Mutations ----

    async def create(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        # Re-fetch with eager loading
        return await self.get_by_id(product.id, eager=True)  # type: ignore[return-value]

    async def update(self, product: Product) -> Product:
        await self._session.flush()
        return await self.get_by_id(product.id, eager=True)  # type: ignore[return-value]

    async def delete(self, product_id: uuid.UUID) -> bool:
        stmt = delete(Product).where(Product.id == product_id)
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def bulk_update(
        self,
        items: list[dict[str, Any]],
    ) -> int:
        """Update multiple products.  Each dict must contain 'id' and fields to update."""
        updated = 0
        for item in items:
            product_id = item.pop("id")
            if not item:
                continue
            stmt = update(Product).where(Product.id == product_id).values(**item)
            result = await self._session.execute(stmt)
            updated += result.rowcount or 0
        await self._session.flush()
        return updated

    async def bulk_delete(self, product_ids: list[uuid.UUID]) -> int:
        stmt = delete(Product).where(Product.id.in_(product_ids))
        result = await self._session.execute(stmt)
        return result.rowcount or 0


# ============================================================================
# Variant Repository
# ============================================================================


class VariantRepository:
    """Data-access methods for :class:`ProductVariant`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, variant_id: uuid.UUID) -> ProductVariant | None:
        stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_product(self, product_id: uuid.UUID) -> Sequence[ProductVariant]:
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.position, ProductVariant.sku)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def sku_exists(self, sku: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).select_from(ProductVariant).where(ProductVariant.sku == sku)
        if exclude_id is not None:
            stmt = stmt.where(ProductVariant.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def create(self, variant: ProductVariant) -> ProductVariant:
        self._session.add(variant)
        await self._session.flush()
        await self._session.refresh(variant)
        return variant

    async def update(self, variant: ProductVariant) -> ProductVariant:
        await self._session.flush()
        await self._session.refresh(variant)
        return variant

    async def delete(self, variant_id: uuid.UUID) -> bool:
        stmt = delete(ProductVariant).where(ProductVariant.id == variant_id)
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0


# ============================================================================
# Image Repository
# ============================================================================


class ImageRepository:
    """Data-access methods for :class:`ProductImage`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, image_id: uuid.UUID) -> ProductImage | None:
        stmt = select(ProductImage).where(ProductImage.id == image_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_product(self, product_id: uuid.UUID) -> Sequence[ProductImage]:
        stmt = (
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.position)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, image: ProductImage) -> ProductImage:
        self._session.add(image)
        await self._session.flush()
        await self._session.refresh(image)
        return image

    async def delete(self, image_id: uuid.UUID) -> bool:
        stmt = delete(ProductImage).where(ProductImage.id == image_id)
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def bulk_update_positions(self, items: list[tuple[uuid.UUID, int]]) -> int:
        updated = 0
        for img_id, position in items:
            stmt = update(ProductImage).where(ProductImage.id == img_id).values(position=position)
            result = await self._session.execute(stmt)
            updated += result.rowcount or 0
        await self._session.flush()
        return updated

    async def clear_primary(self, product_id: uuid.UUID) -> None:
        """Remove primary flag from all images of a product."""
        stmt = (
            update(ProductImage)
            .where(
                and_(
                    ProductImage.product_id == product_id,
                    ProductImage.is_primary.is_(True),
                )
            )
            .values(is_primary=False)
        )
        await self._session.execute(stmt)


# ============================================================================
# Tag Repository
# ============================================================================


class TagRepository:
    """Data-access methods for :class:`Tag` and :class:`ProductTag`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tag_id: uuid.UUID) -> Tag | None:
        stmt = select(Tag).where(Tag.id == tag_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tag | None:
        stmt = select(Tag).where(Tag.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).select_from(Tag).where(Tag.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Tag.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def get_all(
        self,
        *,
        q: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[Tag], int]:
        stmt = select(Tag)
        count_stmt = select(func.count()).select_from(Tag)

        if q:
            like_q = f"%{q}%"
            filter_cond = or_(Tag.name.ilike(like_q), Tag.slug.ilike(like_q))
            stmt = stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(Tag.name).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def create(self, tag: Tag) -> Tag:
        self._session.add(tag)
        await self._session.flush()
        await self._session.refresh(tag)
        return tag

    async def assign_to_product(self, product_id: uuid.UUID, tag_ids: list[uuid.UUID]) -> int:
        """Assign tags to a product, skipping duplicates."""
        existing_stmt = select(ProductTag.tag_id).where(ProductTag.product_id == product_id)
        existing_result = await self._session.execute(existing_stmt)
        existing_tag_ids = {row[0] for row in existing_result}

        added = 0
        for tag_id in tag_ids:
            if tag_id in existing_tag_ids:
                continue
            pt = ProductTag(product_id=product_id, tag_id=tag_id)
            self._session.add(pt)
            added += 1

        if added:
            await self._session.flush()
        return added

    async def remove_from_product(self, product_id: uuid.UUID, tag_ids: list[uuid.UUID]) -> int:
        stmt = delete(ProductTag).where(
            and_(
                ProductTag.product_id == product_id,
                ProductTag.tag_id.in_(tag_ids),
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def get_product_tags(self, product_id: uuid.UUID) -> Sequence[Tag]:
        stmt = (
            select(Tag)
            .join(ProductTag, ProductTag.tag_id == Tag.id)
            .where(ProductTag.product_id == product_id)
            .order_by(Tag.name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


# ============================================================================
# Attribute Repository
# ============================================================================


class AttributeRepository:
    """Data-access methods for :class:`Attribute` and :class:`AttributeValue`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, attribute_id: uuid.UUID) -> Attribute | None:
        stmt = (
            select(Attribute)
            .where(Attribute.id == attribute_id)
            .options(selectinload(Attribute.values))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).select_from(Attribute).where(Attribute.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Attribute.id != exclude_id)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def get_all(
        self,
        *,
        filterable_only: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[Attribute], int]:
        stmt = select(Attribute).options(selectinload(Attribute.values))
        count_stmt = select(func.count()).select_from(Attribute)

        if filterable_only:
            stmt = stmt.where(Attribute.filterable.is_(True))
            count_stmt = count_stmt.where(Attribute.filterable.is_(True))

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            stmt.order_by(Attribute.position, Attribute.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return result.unique().scalars().all(), total

    async def create(self, attribute: Attribute) -> Attribute:
        self._session.add(attribute)
        await self._session.flush()
        await self._session.refresh(attribute)
        # Re-load with values
        return await self.get_by_id(attribute.id)  # type: ignore[return-value]

    async def create_value(self, value: AttributeValue) -> AttributeValue:
        self._session.add(value)
        await self._session.flush()
        await self._session.refresh(value)
        return value


# ============================================================================
# Product Attribute Repository
# ============================================================================


class ProductAttributeRepository:
    """Data-access for :class:`ProductAttribute` join table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_attributes(
        self,
        product_id: uuid.UUID,
        items: list[dict[str, uuid.UUID]],
    ) -> list[ProductAttribute]:
        """Replace all attribute associations for a product."""
        # Delete existing
        del_stmt = delete(ProductAttribute).where(ProductAttribute.product_id == product_id)
        await self._session.execute(del_stmt)

        created: list[ProductAttribute] = []
        for item in items:
            pa = ProductAttribute(
                product_id=product_id,
                attribute_id=item["attribute_id"],
                attribute_value_id=item["attribute_value_id"],
            )
            self._session.add(pa)
            created.append(pa)

        if created:
            await self._session.flush()
        return created

    async def add_attribute(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        attribute_value_id: uuid.UUID,
    ) -> ProductAttribute:
        pa = ProductAttribute(
            product_id=product_id,
            attribute_id=attribute_id,
            attribute_value_id=attribute_value_id,
        )
        self._session.add(pa)
        await self._session.flush()
        await self._session.refresh(pa)
        return pa

    async def remove_attribute(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        attribute_value_id: uuid.UUID | None = None,
    ) -> int:
        conditions = [
            ProductAttribute.product_id == product_id,
            ProductAttribute.attribute_id == attribute_id,
        ]
        if attribute_value_id is not None:
            conditions.append(ProductAttribute.attribute_value_id == attribute_value_id)
        stmt = delete(ProductAttribute).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return result.rowcount or 0
