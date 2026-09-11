"""Product catalog domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class ProductType(str, enum.Enum):
    SIMPLE = "simple"
    VARIABLE = "variable"
    DIGITAL = "digital"


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AttributeType(str, enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    COLOR = "color"
    SIZE = "size"


class SettlementStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


# ---- Models ----


class Category(BaseModel):
    """Hierarchical product categories with materialized path."""

    __tablename__ = "categories"
    __table_args__ = (
        Index("ix_categories_slug", "slug"),
        Index("ix_categories_parent_id", "parent_id"),
        Index("ix_categories_path", "path"),
        Index("ix_categories_is_active", "is_active"),
        Index("ix_categories_position", "position"),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    path: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )  # materialized path e.g. "root/electronics/phones"
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side="Category.id", back_populates="children", lazy="select"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent", lazy="select"
    )
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="category", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, slug={self.slug})>"


class Brand(BaseModel):
    """Product brands."""

    __tablename__ = "brands"
    __table_args__ = (
        Index("ix_brands_slug", "slug"),
        Index("ix_brands_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="brand", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Brand(id={self.id}, slug={self.slug})>"


class Vendor(BaseModel):
    """Marketplace vendor / independent seller entity."""

    __tablename__ = "vendors"
    __table_args__ = (
        Index("ix_vendors_user_id", "user_id"),
        Index("ix_vendors_slug", "slug"),
        Index("ix_vendors_is_active", "is_active"),
        Index("ix_vendors_is_verified", "is_verified"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    commission_rate: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    iban_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    total_sales_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="vendor", lazy="select"
    )
    settlements: Mapped[list["VendorSettlement"]] = relationship(
        "VendorSettlement", back_populates="vendor", cascade="all, delete-orphan", lazy="select"
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("commission_rate", 1000)
        kw.setdefault("is_verified", False)
        kw.setdefault("is_active", True)
        kw.setdefault("rating", 5.0)
        kw.setdefault("total_sales_count", 0)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<Vendor(id={self.id}, store_name={self.store_name}, slug={self.slug})>"


class VendorSettlement(BaseModel):
    """Vendor payout / settlement record."""

    __tablename__ = "vendor_settlements"
    __table_args__ = (
        Index("ix_vendor_settlements_vendor_id", "vendor_id"),
        Index("ix_vendor_settlements_status", "status"),
        Index("ix_vendor_settlements_created_at", "created_at"),
    )

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus, name="settlement_status_enum", native_enum=False),
        default=SettlementStatus.PENDING,
        nullable=False,
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="settlements")

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("status", SettlementStatus.PENDING)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<VendorSettlement(id={self.id}, vendor_id={self.vendor_id}, amount={self.amount}, status={self.status})>"  # noqa: E501


class Product(BaseModel):
    """Core product entity."""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_slug", "slug"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_brand_id", "brand_id"),
        Index("ix_products_vendor_id", "vendor_id"),
        Index("ix_products_status", "status"),
        Index("ix_products_is_active", "is_active"),
        Index("ix_products_is_featured", "is_featured"),
        Index("ix_products_created_at", "created_at"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(550), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, name="product_type_enum", native_enum=False),
        default=ProductType.SIMPLE,
        nullable=False,
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status_enum", native_enum=False),
        default=ProductStatus.DRAFT,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimensions_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    category: Mapped["Category"] = relationship(
        "Category", back_populates="products", lazy="joined"
    )
    brand: Mapped[Optional["Brand"]] = relationship(
        "Brand", back_populates="products", lazy="joined"
    )
    vendor: Mapped[Optional["Vendor"]] = relationship(
        "Vendor", back_populates="products", lazy="select"
    )
    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", lazy="select"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage", back_populates="product", lazy="select"
    )
    product_tags: Mapped[list["ProductTag"]] = relationship(
        "ProductTag", back_populates="product", lazy="select"
    )
    product_attributes: Mapped[list["ProductAttribute"]] = relationship(
        "ProductAttribute", back_populates="product", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, slug={self.slug})>"


class ProductVariant(BaseModel):
    """Product SKU-level variants with pricing."""

    __tablename__ = "product_variants"
    __table_args__ = (
        Index("ix_product_variants_product_id", "product_id"),
        Index("ix_product_variants_vendor_id", "vendor_id"),
        Index("ix_product_variants_sku", "sku"),
        Index("ix_product_variants_is_active", "is_active"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compare_at_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="variants", lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage", back_populates="variant", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<ProductVariant(id={self.id}, sku={self.sku})>"


class ProductImage(BaseModel):
    """Product and variant images."""

    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_product_id", "product_id"),
        Index("ix_product_images_variant_id", "variant_id"),
        Index("ix_product_images_position", "position"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="images")
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="images"
    )

    def __repr__(self) -> str:
        return f"<ProductImage(id={self.id}, product_id={self.product_id})>"


class Tag(BaseModel):
    """Content tags for products."""

    __tablename__ = "tags"
    __table_args__ = (Index("ix_tags_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    # Relationships
    product_tags: Mapped[list["ProductTag"]] = relationship(
        "ProductTag", back_populates="tag", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, slug={self.slug})>"


class ProductTag(BaseModel):
    """Many-to-many association between products and tags."""

    __tablename__ = "product_tags"
    __table_args__ = (
        UniqueConstraint("product_id", "tag_id", name="uq_product_tags_product_tag"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="product_tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="product_tags")

    def __repr__(self) -> str:
        return f"<ProductTag(product_id={self.product_id}, tag_id={self.tag_id})>"


class Attribute(BaseModel):
    """Product attribute definitions (e.g., Color, Size)."""

    __tablename__ = "attributes"
    __table_args__ = (Index("ix_attributes_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    type: Mapped[AttributeType] = mapped_column(
        Enum(AttributeType, name="attribute_type_enum", native_enum=False),
        nullable=False,
    )
    filterable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    values: Mapped[list["AttributeValue"]] = relationship(
        "AttributeValue", back_populates="attribute", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Attribute(id={self.id}, slug={self.slug})>"


class AttributeValue(BaseModel):
    """Possible values for an attribute."""

    __tablename__ = "attribute_values"
    __table_args__ = (
        Index("ix_attribute_values_attribute_id", "attribute_id"),
        UniqueConstraint("attribute_id", "slug", name="uq_attribute_values_attribute_slug"),
    )

    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attributes.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    attribute: Mapped["Attribute"] = relationship("Attribute", back_populates="values")

    def __repr__(self) -> str:
        return f"<AttributeValue(id={self.id}, value={self.value})>"


class ProductAttribute(BaseModel):
    """Association of specific attribute values to products."""

    __tablename__ = "product_attributes"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "attribute_id",
            "attribute_value_id",
            name="uq_product_attributes_product_attr_val",
        ),
        Index("ix_product_attributes_product_id", "product_id"),
        Index("ix_product_attributes_attribute_id", "attribute_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attributes.id", ondelete="CASCADE"),
        nullable=False,
    )
    attribute_value_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attribute_values.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="product_attributes")
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped["AttributeValue"] = relationship("AttributeValue")

    def __repr__(self) -> str:
        return (
            f"<ProductAttribute(product_id={self.product_id}, attribute_id={self.attribute_id})>"
        )
