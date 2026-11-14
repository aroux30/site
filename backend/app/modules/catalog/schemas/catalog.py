"""Pydantic v2 schemas for the Catalog module.

All monetary values are stored as BigInteger (Rial) in the database but
exposed as Toman in API responses (1 Toman = 10 Rial).  Input schemas
accept values in Toman; the service layer converts to Rial before persisting.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationInfo,
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
    slug: str | None = Field(
        None, max_length=250, description="Auto-generated from name if not provided"
    )
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
    parent_name: str | None = None
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
    products_count: int = 0
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
    # Swatch payloads (woo-variation-swatches parity): COLOR values carry a
    # hex, IMAGE values a thumbnail URL, any value an optional tooltip.
    color: str | None = Field(None, max_length=30, description="Hex like #22c55e")
    image_url: str | None = Field(None, max_length=500)
    tooltip: str | None = Field(None, max_length=300)


class AttributeValueUpdate(BaseModel):
    """Schema for updating one attribute value (swatch payloads included)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    value: str | None = Field(None, min_length=1, max_length=200)
    position: int | None = Field(None, ge=0)
    color: str | None = Field(None, max_length=30, description="Hex like #22c55e")
    image_url: str | None = Field(None, max_length=500)
    tooltip: str | None = Field(None, max_length=300)


class AttributeValueResponse(BaseModel):
    """Attribute value API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attribute_id: uuid.UUID
    value: str
    slug: str
    position: int = 0
    color: str | None = None
    image_url: str | None = None
    tooltip: str | None = None


class AttributeCreate(BaseModel):
    """Schema for creating an attribute."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=120)
    type: AttributeType = AttributeType.TEXT
    filterable: bool = False
    position: int = Field(0, ge=0)
    values: list[AttributeValueCreate] = Field(default_factory=list)


class AttributeUpdate(BaseModel):
    """Schema for updating an attribute.  All fields optional.

    ``values`` is a create-only convenience on :class:`AttributeCreate`; an
    update never rewrites the value set, because re-pointing values would
    silently re-map every product that uses them.  Use the dedicated value
    routes to add values.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=120)
    type: AttributeType | None = None
    filterable: bool | None = None
    position: int | None = Field(None, ge=0)


class AttributeValueListResponse(BaseModel):
    """List of values belonging to one attribute."""

    items: list[AttributeValueResponse]


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


def _blank_sku_to_none(v: Any) -> Any:
    """An empty/blank warehouse code means "no code" (owner directive:
    «کد انبار اختیاری — بزار باشه»). Clients that submit "" must clear the
    SKU, not trip a length rule — the DB column is nullable exactly for
    this, and the service layer already treats a submitted null as "clear".
    """
    if isinstance(v, str) and not v.strip():
        return None
    return v


#: SKU fields accept "" as "clear", mirroring the nullable DB column.
SkuField = Annotated[str | None, BeforeValidator(_blank_sku_to_none)]


class VariantCreate(BaseModel):
    """Schema for creating a product variant.  Prices in Toman."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # Optional: digital goods (subscriptions, codes) have no warehouse code.
    # When omitted the service auto-generates a unique internal SKU.
    sku: SkuField = Field(None, max_length=100)
    barcode: str | None = Field(None, max_length=100)
    price: int = Field(..., gt=0, description="Price in Toman")
    compare_at_price: int | None = Field(None, gt=0, description="Original price in Toman")
    cost: int | None = Field(None, gt=0, description="Cost in Toman")
    # USD-denominated source prices (Nobitex price updater): when set, the
    # currency sweep derives price/compare_at_price from these. Up to two
    # decimals; JSON numbers are accepted (pydantic parses to Decimal).
    usd_price: Decimal | None = Field(
        None, ge=0, le=Decimal("9999999999.99"), description="Base price in USD"
    )
    usd_sale_price: Decimal | None = Field(
        None, ge=0, le=Decimal("9999999999.99"), description="Sale price in USD"
    )
    weight: float | None = Field(None, gt=0)
    is_active: bool = True
    position: int = Field(0, ge=0)
    stock: int | None = Field(None, ge=0, description="Initial stock quantity")
    # WooCommerce "Low stock threshold" parity: when set, the admin gets a
    # low-stock alert at this count instead of the store-wide default (5).
    # None = use the store default.
    low_stock_threshold: int | None = Field(None, ge=0)
    # WooCommerce "Allow backorders?" parity: when True, a tracked variant
    # stays buyable after its stock reaches zero.
    backorder_allowed: bool | None = None
    attributes: dict[str, Any] | None = Field(
        None, description="Variant-specific attributes as JSON"
    )

    @model_validator(mode="after")
    def validate_compare_price(self) -> VariantCreate:
        if self.compare_at_price is not None and self.compare_at_price <= self.price:
            raise ValueError("compare_at_price must be greater than price")
        return self


class VariantUpdate(BaseModel):
    """Schema for updating a product variant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # "" normalizes to None = "clear the code" — never a length error.
    sku: SkuField = Field(None, max_length=100)
    barcode: str | None = Field(None, max_length=100)
    price: int | None = Field(None, gt=0, description="Price in Toman")
    compare_at_price: int | None = Field(
        None, description="Original price in Toman; set 0 to clear"
    )
    cost: int | None = Field(None, description="Cost in Toman; set 0 to clear")
    # None leaves the USD price untouched; 0 (like compare_at_price) clears it
    # and takes the variant out of the automatic USD sweep.
    usd_price: Decimal | None = Field(
        None, ge=0, le=Decimal("9999999999.99"), description="Base price in USD; set 0 to clear"
    )
    usd_sale_price: Decimal | None = Field(
        None, ge=0, le=Decimal("9999999999.99"), description="Sale price in USD"
    )
    # Low-stock alert threshold; None leaves the current value untouched.
    low_stock_threshold: int | None = Field(None, ge=0)
    # WooCommerce stock editing: a submitted `stock` re-points the inventory
    # ledger (track_inventory ON). `original_stock` carries the quantity the
    # editor was opened with — if the ledger moved since then, the update is
    # rejected instead of clobbering someone else's change (WooCommerce's
    # `_original_stock` concurrent-edit guard).
    stock: int | None = Field(None, ge=0)
    original_stock: int | None = Field(None, ge=0)
    # WooCommerce "Allow backorders?" parity; None leaves the value untouched.
    backorder_allowed: bool | None = None
    weight: float | None = None
    is_active: bool | None = None
    position: int | None = Field(None, ge=0)
    attributes: dict[str, Any] | None = None


class VariantResponse(BaseModel):
    """Variant API response.  All monetary values in Toman."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    # Truly optional (owner directive): null = the product has no code.
    sku: str | None = None
    barcode: str | None = None
    price: int = Field(description="Price in Toman")
    compare_at_price: int | None = Field(None, description="Original price in Toman")
    cost: int | None = Field(None, description="Cost in Toman")
    # USD source prices, NOT converted by the Toman validators below — they
    # are USD, not Rial. A variant with usd_price is managed by the currency
    # sweep; the admin editor shows these fields for such variants.
    usd_price: Decimal | None = None
    usd_sale_price: Decimal | None = None
    weight: float | None = None
    is_active: bool = True
    position: int = 0
    attributes: dict[str, Any] | None = None
    # Real-time availability (Odoo "free_qty" concept): the sellable on-hand
    # count, so the storefront can distinguish "active but out of stock" from
    # "active and in stock" — is_active alone is not an availability signal.
    available: int | None = None
    # WooCommerce "Low stock threshold" parity; filled by the detail mapper
    # from the inventory ledger (None = store default in use).
    low_stock_threshold: int | None = None
    # Inventory tracking flags for the admin editor's "manage stock" switch;
    # None = no ledger row was found (availability unknown).
    track_inventory: bool | None = None
    backorder_allowed: bool | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("price", mode="before")
    @classmethod
    def convert_price(cls, v: int | None, info: ValidationInfo) -> int | None:
        # context={"already_toman": True} marks values that came back from
        # our own cache (serialized AFTER conversion) — re-running the
        # Rial→Toman conversion on them divided prices by 10 a second time
        # on every cache hit.
        if info.context and info.context.get("already_toman"):
            return v
        return rial_to_toman(v)

    @field_validator("compare_at_price", mode="before")
    @classmethod
    def convert_compare_price(cls, v: int | None, info: ValidationInfo) -> int | None:
        if info.context and info.context.get("already_toman"):
            return v
        return rial_to_toman(v)

    @field_validator("cost", mode="before")
    @classmethod
    def convert_cost(cls, v: int | None, info: ValidationInfo) -> int | None:
        if info.context and info.context.get("already_toman"):
            return v
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


class VariationAttributeOption(BaseModel):
    """One selectable swatch inside a variation attribute group."""

    value_id: uuid.UUID
    value: str
    slug: str
    color: str | None = None
    image_url: str | None = None
    tooltip: str | None = None


class VariationAttributeGroup(BaseModel):
    """A selectable attribute group for the PDP's swatch selector.

    woo-variation-swatches parity: the PDP renders one swatch row per group —
    ``type`` decides the swatch style (color circle / image thumbnail / label
    button) — and the shopper's combination picks the variant.
    """

    attribute_id: uuid.UUID
    name: str
    slug: str
    type: AttributeType
    options: list[VariationAttributeOption] = Field(default_factory=list)


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
    # WooCommerce "Stock status" parity: manual availability when stock is
    # not counted. "onbackorder" is derived at runtime from the ledger.
    stock_status: str = Field("instock", pattern="^(instock|outofstock)$")
    min_order_quantity: int = Field(1, ge=1, description="Minimum quantity per invoice")
    max_order_quantity: int | None = Field(None, ge=1, description="Maximum quantity per invoice")
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
    # WooCommerce "Stock status" parity: manual availability when stock is
    # not counted. Was missing here entirely — the admin form sent it on
    # every edit and Pydantic silently dropped it, so flipping a product
    # between موجود / ناموجود never persisted.
    stock_status: str | None = Field(None, pattern="^(instock|outofstock)$")
    min_order_quantity: int | None = Field(None, ge=1)
    max_order_quantity: int | None = Field(None, ge=1)
    weight: float | None = None
    dimensions_json: dict[str, Any] | None = None
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=500)
    meta_keywords: str | None = Field(None, max_length=500)
    #: Full replacement set, mirroring ProductCreate. Omit the field entirely to
    #: leave attributes untouched; send an empty list to clear them. Sending
    #: tags but not attributes (or the reverse) was impossible before, so an
    #: edit always dropped the attributes the editor could not see.
    tag_ids: list[uuid.UUID] | None = None
    attributes: list[ProductAttributeCreate] | None = None
    #: Variation sync (woo-variation-swatches parity). Omit the field to leave
    #: variants untouched. Rows WITH ``id`` patch that variant; rows without
    #: one create a new variant; existing variants absent from the payload are
    #: soft-retired (is_active=False) instead of deleted — order and cart rows
    #: reference variants, so a hard delete would break purchase history.
    variants: list[VariantSyncItem] | None = None


class VariantSyncItem(BaseModel):
    """One variant row in the admin product editor's variation manager.

    Field parity with a simple product's editor (WooCommerce variation-row
    parity): a variant carries the same commercial knobs the single-product
    form offers — USD-managed prices (Nobitex sweep), low-stock threshold,
    backorders — not just price/stock.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID | None = None
    sku: SkuField = Field(None, max_length=100)
    price: int | None = Field(None, gt=0, description="Price in Toman")
    compare_at_price: int | None = Field(
        None, ge=0, description="Original price in Toman; 0 clears"
    )
    is_active: bool = True
    position: int = Field(0, ge=0)
    # {attribute_slug: value_slug} — how the swatch selector matches options.
    attributes: dict[str, Any] | None = None
    # When set, the inventory ledger is (re)pointed at this sellable count.
    stock: int | None = Field(None, ge=0)
    # USD source prices (Nobitex sweep), same convention as VariantUpdate:
    # omitted/None leaves untouched, 0 clears and takes the variant out of
    # the automatic sweep.
    usd_price: Decimal | None = Field(
        None, ge=0, le=Decimal("9999999999.99"), description="Base price in USD"
    )
    usd_sale_price: Decimal | None = Field(
        None, ge=0, le=Decimal("9999999999.99"), description="Sale price in USD"
    )
    # Low-stock alert threshold (None = leave untouched; store default in use).
    low_stock_threshold: int | None = Field(None, ge=0)
    # Allow backorders: after the count hits zero the variant stays buyable.
    backorder_allowed: bool | None = None
    # Manage-stock switch per variant (the simple-product editor's «مدیریت
    # موجودی»): True = counted stock, False = untracked/unlimited. None leaves
    # the ledger's current mode untouched.
    manage_stock: bool | None = None
    # Physical-goods-only knobs (hidden for digital products by the admin UI,
    # still accepted here so one payload shape serves both types).
    barcode: str | None = Field(None, max_length=100)
    weight: float | None = Field(None, gt=0)
    # Per-option gallery image (Woo variation-image parity): a URL upserts the
    # variant-scoped primary image; an empty string clears it; omitted leaves
    # the images untouched.
    image_url: str | None = Field(None, max_length=500)


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
    category_name: str | None = None
    category_slug: str | None = None
    brand_id: uuid.UUID | None = None
    short_description: str | None = None
    product_type: ProductType
    status: ProductStatus
    is_active: bool = True
    is_featured: bool = False
    # WooCommerce "Stock status" parity — the admin table's "وضعیت موجودی"
    # column and the storefront availability read this for untracked products
    # (whose ledger stock is None = unlimited). Omitted, the list answered
    # null and the table flagged every manually-available product ناموجود.
    stock_status: str = "instock"
    min_order_quantity: int = 1
    max_order_quantity: int | None = None
    primary_image_url: str | None = None
    min_price: int | None = Field(None, description="Lowest variant price in Toman")
    max_price: int | None = Field(None, description="Highest variant price in Toman")
    variant_count: int = 0
    # Real stock of the product's first active variant, populated by the list
    # mapper from the inventory ledger. Without it the admin table showed
    # EVERY product as out of stock (the field it read was always null).
    stock: int | None = None
    # The variant's low-stock threshold — so the admin badge "رو به اتمام"
    # uses the SAME threshold as the low-stock banner/filter, not a hardcode.
    low_stock_threshold: int | None = None
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
    # WooCommerce "Stock status" parity (see ProductCreate).
    stock_status: str = "instock"
    min_order_quantity: int = 1
    max_order_quantity: int | None = None
    weight: float | None = None
    dimensions_json: dict[str, Any] | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    meta_keywords: str | None = None
    # The PDP reads this for og:image and the Product JSON-LD image. The
    # list schema always had it; the detail schema did not, so every product
    # page shipped no share image (found live 2026-10-10, SEO audit).
    # Filled by `_to_detail_response` from the eagerly-loaded images.
    primary_image_url: str | None = None
    # Price range from active variants, in Toman at the boundary (same
    # convention as ProductResponse). The PDP's Product JSON-LD builds its
    # Offer price from min_price; without these fields the schema shipped
    # "price": 0 on every product (Google rejects a zero-priced offer) while
    # the page displayed the real price.
    min_price: int | None = None
    max_price: int | None = None
    created_at: datetime
    updated_at: datetime
    # Related objects
    category: CategoryResponse | None = None
    brand: BrandResponse | None = None
    variants: list[VariantResponse] = Field(default_factory=list)
    images: list[ProductImageResponse] = Field(default_factory=list)
    tags: list[TagResponse] = Field(default_factory=list)
    product_attributes: list[ProductAttributeResponse] = Field(default_factory=list)
    # Selectable swatch groups for the PDP (woo-variation-swatches parity):
    # one entry per attribute the product varies on, with the display type
    # and each option's swatch payload. Empty for simple products.
    variation_attributes: list[VariationAttributeGroup] = Field(
        default_factory=list
    )


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
    in_stock_only: bool = Field(False, description="Only products with available stock")
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


# ── Cross-sell / Accessories (Odoo website_sale concept, clean-room) ───────


class ProductAccessorySetRequest(BaseModel):
    """Replace a product's accessory set (admin)."""

    accessory_ids: list[uuid.UUID] = []


class ProductAccessoryResponse(BaseModel):
    """One accessory product as offered in the upsell rail."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    # Enriched for the storefront rail: lowest active variant price in Toman
    # and the primary image, so the PDP/cart can render a buyable card without
    # a second round-trip. Integer math only — no floats for money.
    price: int | None = None
    image_url: str | None = None


class ProductAccessoryListResponse(BaseModel):
    """A product's accessories."""

    product_id: uuid.UUID
    items: list[ProductAccessoryResponse] = []
