"""REST API routes for the Catalog module.

Read endpoints are public; write endpoints require authentication and
the ``catalog:write`` permission via :class:`RequirePermissions`.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.catalog.application.catalog_service import (
    AttributeService,
    BrandService,
    CategoryService,
    ProductService,
    TagService,
)
from app.modules.catalog.domain.models import ProductStatus, ProductType
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
    ProductBulkDeleteRequest,
    ProductBulkUpdateRequest,
    ProductCreate,
    ProductDetailResponse,
    ProductFilterParams,
    ProductImageCreate,
    ProductImageResponse,
    ProductListResponse,
    ProductUpdate,
    ProductAccessoryListResponse,
    ProductAccessoryResponse,
    ProductAccessorySetRequest,
    TagAssignRequest,
    TagCreate,
    TagListResponse,
    TagResponse,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)

router = APIRouter()

# Permission dependencies
_require_catalog_write = Depends(RequirePermissions("catalog:write"))


def _accessory_to_response(product: Any) -> "ProductAccessoryResponse":
    """Map an accessory Product (enriched with upsell_price/upsell_image_url)
    onto the public rail schema."""
    return ProductAccessoryResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        is_active=product.is_active,
        price=getattr(product, "upsell_price", None),
        image_url=getattr(product, "upsell_image_url", None),
    )


# ============================================================================
# Category Endpoints
# ============================================================================


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    summary="List categories",
)
async def list_categories(
    is_active: bool | None = Query(None),
    parent_id: uuid.UUID | None = Query(None, description="Filter by parent; omit for all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CategoryListResponse:
    """List categories with optional filtering by parent and active status."""
    svc = CategoryService(db)
    # Use sentinel to differentiate "not provided" from "explicitly None"
    _parent_id = parent_id if parent_id is not None else ...
    return await svc.list(
        is_active=is_active, parent_id=_parent_id, page=page, page_size=page_size
    )


@router.get(
    "/categories/tree",
    response_model=list[CategoryTreeResponse],
    summary="Get category tree",
)
async def get_category_tree(
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryTreeResponse]:
    """Return the full category hierarchy as a nested tree."""
    svc = CategoryService(db)
    return await svc.get_tree(is_active=is_active)


@router.get(
    "/categories/by-slug/{slug}",
    response_model=CategoryResponse,
    summary="Get category by slug",
)
async def get_category_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Retrieve a single category by its slug."""
    svc = CategoryService(db)
    return await svc.get_by_slug(slug)


@router.get(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Get category by ID",
)
async def get_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Retrieve a single category by ID."""
    svc = CategoryService(db)
    return await svc.get_by_id(category_id)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
    dependencies=[_require_catalog_write],
)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Create a new category.  Requires ``catalog:write`` permission."""
    svc = CategoryService(db)
    return await svc.create(data)


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update category",
    dependencies=[_require_catalog_write],
)
async def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Update an existing category.  Requires ``catalog:write`` permission."""
    svc = CategoryService(db)
    return await svc.update(category_id, data)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete category",
    dependencies=[_require_catalog_write],
)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a category.  Fails if it has children or products.

    Requires ``catalog:write`` permission.
    """
    svc = CategoryService(db)
    await svc.delete(category_id)


@router.post(
    "/categories/reorder",
    status_code=status.HTTP_200_OK,
    summary="Reorder categories",
    dependencies=[_require_catalog_write],
)
async def reorder_categories(
    data: CategoryReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Bulk update category positions.  Requires ``catalog:write`` permission."""
    svc = CategoryService(db)
    count = await svc.reorder(data)
    return {"updated": count}


# ============================================================================
# Brand Endpoints
# ============================================================================


@router.get(
    "/brands",
    response_model=BrandListResponse,
    summary="List brands",
)
async def list_brands(
    is_active: bool | None = Query(None),
    q: str | None = Query(None, min_length=1, description="Search by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> BrandListResponse:
    """List brands with optional search and active-status filter."""
    svc = BrandService(db)
    return await svc.list(is_active=is_active, q=q, page=page, page_size=page_size)


@router.get(
    "/brands/by-slug/{slug}",
    response_model=BrandResponse,
    summary="Get brand by slug",
)
async def get_brand_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    """Retrieve a single brand by its slug."""
    svc = BrandService(db)
    return await svc.get_by_slug(slug)


@router.get(
    "/brands/{brand_id}",
    response_model=BrandResponse,
    summary="Get brand by ID",
)
async def get_brand(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    """Retrieve a single brand by ID."""
    svc = BrandService(db)
    return await svc.get_by_id(brand_id)


@router.post(
    "/brands",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create brand",
    dependencies=[_require_catalog_write],
)
async def create_brand(
    data: BrandCreate,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    """Create a new brand.  Requires ``catalog:write`` permission."""
    svc = BrandService(db)
    return await svc.create(data)


@router.patch(
    "/brands/{brand_id}",
    response_model=BrandResponse,
    summary="Update brand",
    dependencies=[_require_catalog_write],
)
async def update_brand(
    brand_id: uuid.UUID,
    data: BrandUpdate,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    """Update an existing brand.  Requires ``catalog:write`` permission."""
    svc = BrandService(db)
    return await svc.update(brand_id, data)


@router.delete(
    "/brands/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete brand",
    dependencies=[_require_catalog_write],
)
async def delete_brand(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a brand.  Fails if it has associated products.

    Requires ``catalog:write`` permission.
    """
    svc = BrandService(db)
    await svc.delete(brand_id)


# ============================================================================
# Product Endpoints
# ============================================================================


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="List products",
)
async def list_products(
    q: str | None = Query(None, description="Full-text search"),
    category_id: uuid.UUID | None = Query(None),
    category_slug: str | None = Query(None),
    brand_id: uuid.UUID | None = Query(None),
    brand_slug: str | None = Query(None),
    status_filter: ProductStatus | None = Query(None, alias="status"),
    product_type: ProductType | None = Query(None),
    is_active: bool | None = Query(None),
    is_featured: bool | None = Query(None),
    min_price: int | None = Query(None, ge=0, description="Min price in Toman"),
    max_price: int | None = Query(None, ge=0, description="Max price in Toman"),
    in_stock_only: bool = Query(False, description="Only products with available stock"),
    tag_ids: str | None = Query(None, description="Comma-separated tag UUIDs"),
    attribute_values: str | None = Query(
        None, description="Comma-separated attribute value UUIDs"
    ),
    sort_by: str = Query("created_at", pattern=r"^(name|price|created_at|updated_at|position)$"),
    sort_order: str = Query("desc", pattern=r"^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="Cursor for cursor-based pagination"),
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    """List products with rich filtering, sorting, and pagination.

    Supports both offset-based and cursor-based pagination.
    """
    # Parse comma-separated UUIDs
    parsed_tag_ids: list[uuid.UUID] | None = None
    if tag_ids:
        try:
            parsed_tag_ids = [uuid.UUID(t.strip()) for t in tag_ids.split(",")]
        except ValueError:
            parsed_tag_ids = None

    parsed_attr_values: list[uuid.UUID] | None = None
    if attribute_values:
        try:
            parsed_attr_values = [uuid.UUID(a.strip()) for a in attribute_values.split(",")]
        except ValueError:
            parsed_attr_values = None

    filters = ProductFilterParams(
        q=q,
        category_id=category_id,
        category_slug=category_slug,
        brand_id=brand_id,
        brand_slug=brand_slug,
        status=status_filter,
        product_type=product_type,
        is_active=is_active,
        is_featured=is_featured,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        tag_ids=parsed_tag_ids,
        attribute_values=parsed_attr_values,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        cursor=cursor,
    )
    svc = ProductService(db)
    return await svc.list(filters)


@router.get(
    "/products/by-slug/{slug}",
    response_model=ProductDetailResponse,
    summary="Get product by slug",
)
@router.get(
    "/products/slug/{slug}",
    response_model=ProductDetailResponse,
    summary="Get product by slug alias",
    include_in_schema=False,
)
async def get_product_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    """Retrieve a product with full details by its slug with Redis caching."""
    from app.core.cache.redis import cache_get, cache_set

    cache_key = f"catalog:product:slug:{slug}"
    hit = await cache_get(cache_key)
    if hit:
        return ProductDetailResponse.model_validate_json(hit)

    svc = ProductService(db)
    res = await svc.get_by_slug(slug)
    await cache_set(cache_key, res.model_dump_json(), ttl=300)
    return res


@router.get(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Get product by ID",
)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    """Retrieve a product with full details by ID."""
    svc = ProductService(db)
    return await svc.get_by_id(product_id)


@router.post(
    "/products",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    dependencies=[_require_catalog_write],
)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    """Create a new product with optional nested variants, images, tags, and attributes.

    Requires ``catalog:write`` permission.
    """
    svc = ProductService(db)
    return await svc.create(data)


@router.patch(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Update product",
    dependencies=[_require_catalog_write],
)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    """Update an existing product.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    return await svc.update(product_id, data)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product",
    dependencies=[_require_catalog_write],
)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a product and all associated variants/images.

    Requires ``catalog:write`` permission.
    """
    svc = ProductService(db)
    await svc.delete(product_id)


@router.post(
    "/products/bulk-update",
    status_code=status.HTTP_200_OK,
    summary="Bulk update products",
    dependencies=[_require_catalog_write],
)
async def bulk_update_products(
    data: ProductBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Update status, active state, or category for multiple products at once.

    Requires ``catalog:write`` permission.
    """
    svc = ProductService(db)
    count = await svc.bulk_update(data)
    return {"updated": count}


@router.post(
    "/products/bulk-delete",
    status_code=status.HTTP_200_OK,
    summary="Bulk delete products",
    dependencies=[_require_catalog_write],
)
async def bulk_delete_products(
    data: ProductBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Delete multiple products at once.

    Requires ``catalog:write`` permission.
    """
    svc = ProductService(db)
    count = await svc.bulk_delete(data)
    return {"deleted": count}


# ============================================================================
# Variant Endpoints
# ============================================================================


@router.get(
    "/products/{product_id}/variants",
    response_model=list[VariantResponse],
    summary="List product variants",
)
async def list_variants(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[VariantResponse]:
    """List all variants of a product."""
    svc = ProductService(db)
    return await svc.list_variants(product_id)


@router.post(
    "/products/{product_id}/variants",
    response_model=VariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create variant",
    dependencies=[_require_catalog_write],
)
async def create_variant(
    product_id: uuid.UUID,
    data: VariantCreate,
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    """Add a variant to a product.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    return await svc.create_variant(product_id, data)


@router.patch(
    "/variants/{variant_id}",
    response_model=VariantResponse,
    summary="Update variant",
    dependencies=[_require_catalog_write],
)
async def update_variant(
    variant_id: uuid.UUID,
    data: VariantUpdate,
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    """Update an existing variant.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    return await svc.update_variant(variant_id, data)


@router.delete(
    "/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete variant",
    dependencies=[_require_catalog_write],
)
async def delete_variant(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a product variant.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    await svc.delete_variant(variant_id)


# ============================================================================
# Image Endpoints
# ============================================================================


@router.get(
    "/products/{product_id}/images",
    response_model=list[ProductImageResponse],
    summary="List product images",
)
async def list_images(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ProductImageResponse]:
    """List all images of a product ordered by position."""
    svc = ProductService(db)
    return await svc.list_images(product_id)


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add image to product",
    dependencies=[_require_catalog_write],
)
async def add_image(
    product_id: uuid.UUID,
    data: ProductImageCreate,
    db: AsyncSession = Depends(get_db),
) -> ProductImageResponse:
    """Add an image to a product.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    return await svc.add_image(product_id, data)


@router.delete(
    "/products/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove image from product",
    dependencies=[_require_catalog_write],
)
async def remove_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an image from a product.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    await svc.remove_image(product_id, image_id)


@router.post(
    "/products/{product_id}/images/reorder",
    status_code=status.HTTP_200_OK,
    summary="Reorder product images",
    dependencies=[_require_catalog_write],
)
async def reorder_images(
    product_id: uuid.UUID,
    data: ImageReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Reorder images of a product.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    count = await svc.reorder_images(product_id, data)
    return {"updated": count}


# ============================================================================
# Tag Endpoints
# ============================================================================


@router.get(
    "/tags",
    response_model=TagListResponse,
    summary="List tags",
)
async def list_tags(
    q: str | None = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> TagListResponse:
    """List all tags with optional search."""
    svc = TagService(db)
    return await svc.list(q=q, page=page, page_size=page_size)


@router.post(
    "/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    dependencies=[_require_catalog_write],
)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
) -> TagResponse:
    """Create a new tag.  Requires ``catalog:write`` permission."""
    svc = TagService(db)
    return await svc.create(data)


@router.post(
    "/products/{product_id}/tags",
    response_model=list[TagResponse],
    summary="Assign tags to product",
    dependencies=[_require_catalog_write],
)
async def assign_tags(
    product_id: uuid.UUID,
    data: TagAssignRequest,
    db: AsyncSession = Depends(get_db),
) -> list[TagResponse]:
    """Assign tags to a product.  Requires ``catalog:write`` permission."""
    svc = ProductService(db)
    return await svc.assign_tags(product_id, data)


@router.delete(
    "/products/{product_id}/tags",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove tags from product",
    dependencies=[_require_catalog_write],
)
async def remove_tags(
    product_id: uuid.UUID,
    tag_ids: str = Query(..., description="Comma-separated tag UUIDs to remove"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove tags from a product.  Requires ``catalog:write`` permission."""
    parsed_ids = [uuid.UUID(t.strip()) for t in tag_ids.split(",")]
    svc = ProductService(db)
    await svc.remove_tags(product_id, parsed_ids)


# ============================================================================
# Attribute Endpoints
# ============================================================================


@router.get(
    "/attributes",
    response_model=AttributeListResponse,
    summary="List attributes",
)
async def list_attributes(
    filterable_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> AttributeListResponse:
    """List all product attributes with their values."""
    svc = AttributeService(db)
    return await svc.list(filterable_only=filterable_only, page=page, page_size=page_size)


@router.get(
    "/attributes/{attribute_id}",
    response_model=AttributeResponse,
    summary="Get attribute by ID",
)
async def get_attribute(
    attribute_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AttributeResponse:
    """Retrieve a single attribute with its values."""
    svc = AttributeService(db)
    return await svc.get_by_id(attribute_id)


@router.post(
    "/attributes",
    response_model=AttributeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create attribute",
    dependencies=[_require_catalog_write],
)
async def create_attribute(
    data: AttributeCreate,
    db: AsyncSession = Depends(get_db),
) -> AttributeResponse:
    """Create a new attribute with optional initial values.

    Requires ``catalog:write`` permission.
    """
    svc = AttributeService(db)
    return await svc.create(data)


@router.patch(
    "/attributes/{attribute_id}",
    response_model=AttributeResponse,
    summary="Update attribute",
    dependencies=[_require_catalog_write],
)
async def update_attribute(
    attribute_id: uuid.UUID,
    data: AttributeUpdate,
    db: AsyncSession = Depends(get_db),
) -> AttributeResponse:
    """Update an attribute's name, slug, type, filterable flag or position.

    The value set is deliberately not editable here: re-pointing values would
    silently re-map every product that uses them.  Requires ``catalog:write``.
    """
    svc = AttributeService(db)
    return await svc.update(attribute_id, data)


@router.delete(
    "/attributes/{attribute_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete attribute",
    dependencies=[_require_catalog_write],
)
async def delete_attribute(
    attribute_id: uuid.UUID,
    force: bool = Query(
        False,
        description=(
            "Delete even when products use this attribute. Their specification "
            "entries are removed by the cascade."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an attribute.

    Refused with 409 and the number of affected products while any product
    still uses it; pass ``force=true`` to delete anyway.  Requires
    ``catalog:write``.
    """
    svc = AttributeService(db)
    await svc.delete(attribute_id, force=force)


@router.get(
    "/attributes/{attribute_id}/values",
    response_model=AttributeValueListResponse,
    summary="List values of an attribute",
)
async def list_attribute_values(
    attribute_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AttributeValueListResponse:
    """List every value defined for one attribute, in display order."""
    svc = AttributeService(db)
    return await svc.list_values(attribute_id)


@router.post(
    "/attributes/{attribute_id}/values",
    response_model=AttributeValueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a value to an attribute",
    dependencies=[_require_catalog_write],
)
async def create_attribute_value(
    attribute_id: uuid.UUID,
    data: AttributeValueCreate,
    db: AsyncSession = Depends(get_db),
) -> AttributeValueResponse:
    """Add a value to an existing attribute.  Requires ``catalog:write``."""
    svc = AttributeService(db)
    return await svc.create_value(attribute_id, data)


@router.delete(
    "/attributes/{attribute_id}/values/{value_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a value of an attribute",
    dependencies=[_require_catalog_write],
)
async def delete_attribute_value(
    attribute_id: uuid.UUID,
    value_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete one value.  Refused with 409 while products still use it.

    Requires ``catalog:write``.
    """
    svc = AttributeService(db)
    await svc.delete_value(attribute_id, value_id)


# ── Dynamic category order fields (Karta categoryFields, Sprint 1.7) ──────


@router.get(
    "/categories/{category_id}/custom-fields",
    response_model=list,
    summary="List dynamic order-field definitions for a category (public)",
)
async def list_category_custom_fields(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Public definitions the storefront order form renders dynamically."""
    from app.modules.inventory.application import custom_field_service
    from app.modules.inventory.schemas.digital import CategoryCustomFieldResponse

    fields = await custom_field_service.list_fields_for_category(db, category_id)
    return [CategoryCustomFieldResponse.model_validate(f).model_dump(mode="json") for f in fields]


@router.post(
    "/categories/{category_id}/custom-fields",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a dynamic order-field definition for a category (admin)",
    dependencies=[Depends(RequirePermissions("catalog:write"))],
)
async def create_category_custom_field(
    category_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.inventory.application import custom_field_service
    from app.modules.inventory.schemas.digital import CategoryCustomFieldResponse

    field = await custom_field_service.create_field(
        db,
        category_id=category_id,
        field_key=str(body.get("field_key") or ""),
        label=str(body.get("label") or ""),
        field_type=str(body.get("field_type") or "text"),
        is_required=bool(body.get("is_required", False)),
        position=int(body.get("position", 0)),
        options=body.get("options"),
    )
    return CategoryCustomFieldResponse.model_validate(field).model_dump(mode="json")


@router.delete(
    "/custom-fields/{field_id}",
    response_model=dict,
    summary="Delete a dynamic order-field definition (admin)",
    dependencies=[Depends(RequirePermissions("catalog:write"))],
)
async def delete_category_custom_field(
    field_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    from app.modules.inventory.application import custom_field_service

    await custom_field_service.delete_field(db, field_id=field_id)
    return {"deleted": True}


# ── Cross-sell / Accessories (Odoo website_sale concept, clean-room) ────────


@router.get(
    "/products/{product_id}/accessories",
    response_model=ProductAccessoryListResponse,
    summary="List a product's accessories (public, upsell rail)",
)
async def list_product_accessories(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProductAccessoryListResponse:
    """Active accessories offered alongside this product."""
    from app.modules.catalog.application import accessory_service

    accessories = await accessory_service.list_accessories(db, product_id)
    return ProductAccessoryListResponse(
        product_id=product_id,
        items=[_accessory_to_response(p) for p in accessories],
    )


@router.put(
    "/products/{product_id}/accessories",
    response_model=ProductAccessoryListResponse,
    summary="Replace a product's accessory set (admin)",
    dependencies=[_require_catalog_write],
)
async def set_product_accessories(
    product_id: uuid.UUID,
    body: ProductAccessorySetRequest,
    db: AsyncSession = Depends(get_db),
) -> ProductAccessoryListResponse:
    """Atomically replace the accessory set. Requires ``catalog:write``."""
    from app.modules.catalog.application import accessory_service

    await accessory_service.set_accessories(
        db, product_id=product_id, accessory_ids=body.accessory_ids
    )
    accessories = await accessory_service.list_accessories(db, product_id)
    return ProductAccessoryListResponse(
        product_id=product_id,
        items=[_accessory_to_response(p) for p in accessories],
    )
