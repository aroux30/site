"""Pydantic v2 schemas for the Catalog module.

All monetary values are stored as BigInteger (Rial) in the database but
exposed as Toman in API responses (1 Toman = 10 Rial).  Input schemas
accept values in Toman; the service layer converts to Rial before persisting.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.modules.catalog.domain.models import (
    AttributeType,
    ProductStatus,
    ProductType,
)


# ============================================================================
# Helpers
# ============================================================================

RIAL_TO_TOMAN = 10


def rial_to_toman(value: int | None) -> int | None:
    """Convert Rial (DB) to Toman (API)."""
    if value is None:
        return None
    return value // RIAL_TO_TOMAN


def toman_to_rial(value: int | None) -> int | None:
    """Convert Toman (API) to Rial (DB)."""
    if value is None:
        return None
    return value * RIAL_TO_TOMAN


# ============================================================================
# Pagination
# ============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    model_config = ConfigDict(from_attributes=True)

    total: int = Field(ge=0, description="Total number of records")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total pages")
    has_next: bool = False
    has_prev: bool = False
    next_cursor: str | None = None


# ============================================================================
# Category Schemas
# ============================================================================


class CategoryCreate(BaseModel):
    """Schema for creating a new category."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=250, description="Auto-generated from name if not provided")
    parent_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=5000)
    image_url: str | None = Field(None, max_length=500)
    position: int = Field(0, ge=0)
    is_active: bool = True
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)


class CategoryUpdate(BaseModel):
    """Schema for updating a category.  All fields optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=250)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=5000)
    image_url: str | None = Field(None, max_length=500)
    position: int | None = Field(None, ge=0)
    is_active: bool | None = None
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)


class CategoryResponse(BaseModel):
    """Flat category response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    path: str | None = None
    depth: int = 0
    position: int = 0
    is_active: bool = True
    seo_title: str | None = None
    seo_description: str | None = None
    created_at: datetime
    updated_at: datetime


class CategoryTreeResponse(BaseModel):
    """Recursive tree node for category hierarchy."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    path: str | None = None
    depth: int = 0
    position: int = 0
    is_active: bool = True
    children: list[CategoryTreeResponse] = Field(default_factory=list)


class CategoryListResponse(BaseModel):
    """Paginated list of categories."""

    items: list[CategoryResponse]
    meta: PaginationMeta


class CategoryReorderItem(BaseModel):
    """Single item in a reorder request."""

    id: uuid.UUID
    position: int = Field(ge=0)


class CategoryReorderRequest(BaseModel):
    """Bulk reorder categories."""

    items: list[CategoryReorderItem] = Field(..., min_length=1)


# ============================================================================
# Brand Schemas
# ============================================================================


class BrandCreate(BaseModel):
    """Schema for creating a brand."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=250)
    logo_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=5000)
    is_active: bool = True


class BrandUpdate(BaseModel):
    """Schema for updating a brand."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=250)
    logo_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=5000)
    is_active: bool | None = None


class BrandResponse(BaseModel):
    """Brand API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class BrandListResponse(BaseModel):
    """Paginated list of brands."""

    items: list[BrandResponse]
    meta: PaginationMeta


# ============================================================================
# Tag Schemas
# ============================================================================


class TagCreate(BaseModel):
    """Schema for creating a tag."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=120)


class TagResponse(BaseModel):
    """Tag API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class TagListResponse(BaseModel):
    """List of tags."""

    items: list[TagResponse]
    meta: PaginationMeta


class TagAssignRequest(BaseModel):
    """Assign tags to a product."""

    tag_ids: list[uuid.UUID] = Field(..., min_length=1)


# ============================================================================
# Attribute Schemas
# ============================================================================


class AttributeValueCreate(BaseModel):
    """Schema for creating an attribute value."""

    model_config = ConfigDict(str_strip_whitespace=True)

    value: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=220)
    position: int = Field(0, ge=0)


class AttributeValueResponse(BaseModel):
    """Attribute value API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attribute_id: uuid.UUID
    value: str
    slug: str
    position: int = 0


class AttributeCreate(BaseModel):
    """Schema for creating an attribute."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=120)
    type: AttributeType = AttributeType.TEXT
    filterable: bool = False
    position: int = Field(0, ge=0)
    values: list[AttributeValueCreate] = Field(default_factory=list)


class AttributeResponse(BaseModel):
    """Attribute API response with nested values."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    type: AttributeType
    filterable: bool = False
    position: int = 0
    values: list[AttributeValueResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AttributeListResponse(BaseModel):
    """List of attributes."""

    items: list[AttributeResponse]
    meta: PaginationMeta


# ============================================================================
# Product Image Schemas
# ============================================================================


class ProductImageCreate(BaseModel):
    """Schema for adding an image to a product."""

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(..., min_length=1, max_length=500)
    alt_text: str | None = Field(None, max_length=300)
    variant_id: uuid.UUID | None = None
    position: int = Field(0, ge=0)
    is_primary: bool = False


class ProductImageResponse(BaseModel):
    """Product image API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    url: str
    alt_text: str | None = None
    position: int = 0
    is_primary: bool = False
    created_at: datetime
    updated_at: datetime


class ImageReorderItem(BaseModel):
    """Single item in an image reorder request."""

    id: uuid.UUID
    position: int = Field(ge=0)


class ImageReorderRequest(BaseModel):
    """Bulk reorder images."""

    items: list[ImageReorderItem] = Field(..., min_length=1)


# ============================================================================
# Variant Schemas
# ============================================================================


class VariantCreate(BaseModel):
    """Schema for creating a product variant.  Prices in Toman."""

    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str = Field(..., min_length=1, max_length=100)
    barcode: str | None = Field(None, max_length=100)
    price: int = Field(..., gt=0, description="Price in Toman")
    compare_at_price: int | None = Field(None, gt=0, description="Original price in Toman")
    cost: int | None = Field(None, gt=0, description="Cost in Toman")
    weight: float | None = Field(None, gt=0)
    is_active: bool = True
    position: int = Field(0, ge=0)
    attributes: dict[str, Any] | None = Field(None, description="Variant-specific attributes as JSON")

    @model_validator(mode="after")
    def validate_compare_price(self) -> VariantCreate:
        if self.compare_at_price is not None and self.compare_at_price <= self.price:
            raise ValueError("compare_at_price must be greater than price")
        return self


class VariantUpdate(BaseModel):
    """Schema for updating a product variant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str | None = Field(None, min_length=1, max_length=100)
    barcode: str | None = Field(None, max_length=100)
    price: int | None = Field(None, gt=0, description="Price in Toman")
    compare_at_price: int | None = Field(None, description="Original price in Toman; set 0 to clear")
    cost: int | None = Field(None, description="Cost in Toman; set 0 to clear")
    weight: float | None = None
    is_active: bool | None = None
    position: int | None = Field(None, ge=0)
    attributes: dict[str, Any] | None = None


class VariantResponse(BaseModel):
    """Variant API response.  All monetary values in Toman."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    barcode: str | None = None
    price: int = Field(description="Price in Toman")
    compare_at_price: int | None = Field(None, description="Original price in Toman")
    cost: int | None = Field(None, description="Cost in Toman")
    weight: float | None = None
    is_active: bool = True
    position: int = 0
    attributes: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("price", mode="before")
    @classmethod
    def convert_price(cls, v: int | None) -> int | None:
        return rial_to_toman(v)

    @field_validator("compare_at_price", mode="before")
    @classmethod
    def convert_compare_price(cls, v: int | None) -> int | None:
        return rial_to_toman(v)

    @field_validator("cost", mode="before")
    @classmethod
    def convert_cost(cls, v: int | None) -> int | None:
        return rial_to_toman(v)


# ============================================================================
# Product Attribute Schemas
# ============================================================================


class ProductAttributeCreate(BaseModel):
    """Assign an attribute value to a product."""

    attribute_id: uuid.UUID
    attribute_value_id: uuid.UUID


class ProductAttributeResponse(BaseModel):
    """Product attribute association response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    attribute_id: uuid.UUID
    attribute_value_id: uuid.UUID
    attribute_name: str | None = None
    attribute_value: str | None = None


# ============================================================================
# Product Schemas
# ============================================================================


class ProductCreate(BaseModel):
    """Schema for creating a product."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=500)
    slug: str | None = Field(None, max_length=550)
    category_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    description: str | None = None
    short_description: str | None = Field(None, max_length=1000)
    product_type: ProductType = ProductType.SIMPLE
    status: ProductStatus = ProductStatus.DRAFT
    is_active: bool = True
    is_featured: bool = False
    weight: float | None = Field(None, gt=0)
    dimensions_json: dict[str, Any] | None = None
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)
    meta_keywords: str | None = Field(None, max_length=500)
    # Nested creation
    variants: list[VariantCreate] = Field(default_factory=list)
    images: list[ProductImageCreate] = Field(default_factory=list)
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    attributes: list[ProductAttributeCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Schema for updating a product.  All fields optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=500)
    slug: str | None = Field(None, max_length=550)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    description: str | None = None
    short_description: str | None = Field(None, max_length=1000)
    product_type: ProductType | None = None
    status: ProductStatus | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    weight: float | None = None
    dimensions_json: dict[str, Any] | None = None
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)
    meta_keywords: str | None = Field(None, max_length=500)


class ProductBulkUpdateItem(BaseModel):
    """Single product update in a bulk operation."""

    id: uuid.UUID
    status: ProductStatus | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    category_id: uuid.UUID | None = None


class ProductBulkUpdateRequest(BaseModel):
    """Bulk update for multiple products."""

    items: list[ProductBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class ProductBulkDeleteRequest(BaseModel):
    """Bulk delete products."""

    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class ProductResponse(BaseModel):
    """Compact product response for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    category_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    short_description: str | None = None
    product_type: ProductType
    status: ProductStatus
    is_active: bool = True
    is_featured: bool = False
    primary_image_url: str | None = None
    min_price: int | None = Field(None, description="Lowest variant price in Toman")
    max_price: int | None = Field(None, description="Highest variant price in Toman")
    variant_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated list of products."""

    items: list[ProductResponse]
    meta: PaginationMeta


class ProductDetailResponse(BaseModel):
    """Full product response with all relations."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    category_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    description: str | None = None
    short_description: str | None = None
    product_type: ProductType
    status: ProductStatus
    is_active: bool = True
    is_featured: bool = False
    weight: float | None = None
    dimensions_json: dict[str, Any] | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    meta_keywords: str | None = None
    created_at: datetime
    updated_at: datetime
    # Related objects
    category: CategoryResponse | None = None
    brand: BrandResponse | None = None
    variants: list[VariantResponse] = Field(default_factory=list)
    images: list[ProductImageResponse] = Field(default_factory=list)
    tags: list[TagResponse] = Field(default_factory=list)
    product_attributes: list[ProductAttributeResponse] = Field(default_factory=list)


# ============================================================================
# Product Filters
# ============================================================================


class ProductFilterParams(BaseModel):
    """Query parameters for filtering products."""

    model_config = ConfigDict(str_strip_whitespace=True)

    q: str | None = Field(None, description="Search query (name, description)")
    category_id: uuid.UUID | None = None
    category_slug: str | None = None
    brand_id: uuid.UUID | None = None
    brand_slug: str | None = None
    status: ProductStatus | None = None
    product_type: ProductType | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    min_price: int | None = Field(None, ge=0, description="Min price filter in Toman")
    max_price: int | None = Field(None, ge=0, description="Max price filter in Toman")
    tag_ids: list[uuid.UUID] | None = None
    attribute_values: list[uuid.UUID] | None = Field(
        None, description="Filter by attribute value IDs"
    )
    # Sorting
    sort_by: str = Field("created_at", pattern=r"^(name|price|created_at|updated_at|position)$")
    sort_order: str = Field("desc", pattern=r"^(asc|desc)$")
    # Pagination
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="Cursor for cursor-based pagination")
