"""Product entity adapter — the first adapter of the import/export framework.

Import upserts a ``Product`` plus its primary ``ProductVariant`` matched by
SKU (``product_variants.sku`` is globally unique). Prices are **Toman
integers** at the file boundary and are converted to Rial for storage with
the same ``toman_to_rial`` helper the catalog service uses, so the import
path can never introduce float money.

Stock quantity (when the column is mapped) sets ``inventory_items.available``
at the default warehouse via an ADJUSTED inventory transaction — the same
audited path the admin inventory UI uses.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import ValidationError
from app.modules.catalog.domain.models import (
    Category,
    Product,
    ProductStatus,
    ProductVariant,
)
from app.modules.catalog.schemas.catalog import toman_to_rial
from app.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE_ID,
    InventoryItem,
    TransactionType,
)
from app.modules.inventory.application import inventory_service
from app.shared.domain.slug import generate_slug

from app.modules.dataexchange.application.adapters import (
    ColumnSpec,
    EntityAdapter,
    coerce_bool,
    coerce_int,
    is_valid_slug,
    register_adapter,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Column-level validators (return a Persian error message or None)
# ---------------------------------------------------------------------------


def _validate_price(value: int) -> str | None:
    if value < 0:
        return "قیمت نمی‌تواند منفی باشد"
    return None


def _validate_stock(value: int) -> str | None:
    if value < 0:
        return "موجودی نمی‌تواند منفی باشد"
    return None


def _validate_slug(value: str) -> str | None:
    if value and not is_valid_slug(value):
        return f"نامک «{value}» معتبر نیست (فقط حروف، اعداد و خط تیره)"
    return None


def _validate_name(value: str) -> str | None:
    if not value or not value.strip():
        return "نام محصول الزامی است"
    if len(value) > 500:
        return "نام محصول بیش از ۵۰۰ کاراکتر است"
    return None


PRODUCT_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="sku",
        label="کد کالا (SKU)",
        required=True,
        type="string",
        aliases=("کد کالا", "کد محصول", "شناسه", "code", "product_code"),
    ),
    ColumnSpec(
        key="name",
        label="نام محصول",
        required=True,
        type="string",
        aliases=("نام", "عنوان", "title"),
        extra_validator=_validate_name,
    ),
    ColumnSpec(
        key="slug",
        label="نامک",
        required=False,
        type="string",
        aliases=("نامک محصول", "slug"),
        extra_validator=_validate_slug,
    ),
    ColumnSpec(
        key="price",
        label="قیمت (تومان)",
        required=True,
        type="integer",
        aliases=("قیمت", "قیمت تومان", "price_toman"),
        extra_validator=_validate_price,
    ),
    ColumnSpec(
        key="stock_quantity",
        label="موجودی",
        required=False,
        type="integer",
        aliases=("موجودی انبار", "تعداد", "stock", "quantity", "qty"),
        extra_validator=_validate_stock,
    ),
    ColumnSpec(
        key="category",
        label="دسته‌بندی",
        required=False,
        type="string",
        aliases=("دسته", "دسته‌بندی محصول", "category_slug", "category_id"),
    ),
    ColumnSpec(
        key="description",
        label="توضیحات",
        required=False,
        type="string",
        aliases=("توضیح", "شرح", "desc"),
    ),
    ColumnSpec(
        key="is_active",
        label="فعال",
        required=False,
        type="boolean",
        aliases=("وضعیت فعال", "active", "enabled"),
    ),
)


# ---------------------------------------------------------------------------
# Row -> model mapping helpers (kept small so tests can exercise them)
# ---------------------------------------------------------------------------


def coerce_row(
    raw: dict[str, Any],
    columns: tuple[ColumnSpec, ...] = PRODUCT_COLUMNS,
) -> dict[str, Any]:
    """Type-coerce one mapped row to its column types.

    ``raw`` is keyed by column *key* (mapping already applied). Missing
    optional values are dropped; missing/blank required values are left for
    the validator to report so a single pass surfaces every problem.
    Raises nothing — callers use :func:`validate_row` for messages.
    """
    out: dict[str, Any] = {}
    for col in columns:
        value = raw.get(col.key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if col.type == "integer":
            try:
                out[col.key] = coerce_int(value)
            except ValueError:
                out[col.key] = value  # keep raw; validator reports it
        elif col.type == "boolean":
            try:
                out[col.key] = coerce_bool(value)
            except ValueError:
                out[col.key] = value
        else:
            out[col.key] = str(value).strip()
    return out


def validate_row(
    raw: dict[str, Any],
    columns: tuple[ColumnSpec, ...] = PRODUCT_COLUMNS,
) -> list[tuple[str, str]]:
    """Validate one coerced-attempt row; returns ``(column_key, message)`` pairs."""
    problems: list[tuple[str, str]] = []
    for col in columns:
        value = raw.get(col.key)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if col.required:
                problems.append((col.key, f"ستون «{col.label}» الزامی است"))
            continue
        if col.type == "integer" and not isinstance(value, int):
            problems.append((col.key, f"ستون «{col.label}» باید عدد صحیح باشد"))
            continue
        if col.type == "boolean" and not isinstance(value, bool):
            problems.append((col.key, f"ستون «{col.label}» باید فعال/غیرفعال باشد"))
            continue
        if col.extra_validator is not None and isinstance(value, (int, str, bool)):
            message = col.extra_validator(value)
            if message:
                problems.append((col.key, message))
    return problems


async def _resolve_category(db: Any, ref: str) -> Category | None:
    """Resolve a category reference: UUID id first, then slug."""
    try:
        category_id = uuid.UUID(ref)
    except (ValueError, AttributeError):
        category_id = None
    if category_id is not None:
        found = (await db.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
        if found is not None:
            return found
    return (
        await db.execute(select(Category).where(Category.slug == ref.strip()))
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Upsert (idempotent by SKU)
# ---------------------------------------------------------------------------


async def upsert_product_row(db: Any, row: dict[str, Any]) -> str:
    """Create or update product + default variant matched by SKU.

    Returns ``"created"`` or ``"updated"``. Per-row savepoints are the
    caller's responsibility (the pipeline wraps each row in
    ``db.begin_nested()`` so one bad row cannot poison the batch).
    """
    sku = str(row["sku"]).strip()
    variant = (
        await db.execute(select(ProductVariant).where(ProductVariant.sku == sku))
    ).scalar_one_or_none()

    category_id: uuid.UUID | None = None
    if row.get("category"):
        category = await _resolve_category(db, str(row["category"]))
        if category is None:
            raise ValidationError(f"دسته‌بندی «{row['category']}» یافت نشد")
        category_id = category.id

    if variant is not None:
        product = (
            await db.execute(select(Product).where(Product.id == variant.product_id))
        ).scalar_one_or_none()
        if product is None:  # pragma: no cover — FK guarantees the parent
            raise ValidationError(f"محصول متصل به SKU «{sku}» یافت نشد")

        if row.get("name"):
            product.name = row["name"]
        if row.get("slug"):
            product.slug = row["slug"]
        if category_id is not None:
            product.category_id = category_id
        if row.get("description") is not None:
            product.description = row["description"]
        if "is_active" in row:
            product.is_active = row["is_active"]
            variant.is_active = row["is_active"]
        product.status = ProductStatus.ACTIVE if product.is_active else ProductStatus.DRAFT

        variant.price = toman_to_rial(row["price"])
        action = "updated"
    else:
        if category_id is None:
            raise ValidationError("برای محصول جدید، دسته‌بندی الزامی است")
        slug = row.get("slug") or generate_slug(row["name"])
        product = Product(
            name=row["name"],
            slug=slug,
            category_id=category_id,
            description=row.get("description"),
            status=ProductStatus.ACTIVE if row.get("is_active", True) else ProductStatus.DRAFT,
            is_active=row.get("is_active", True),
        )
        db.add(product)
        await db.flush()
        variant = ProductVariant(
            product_id=product.id,
            sku=sku,
            price=toman_to_rial(row["price"]),
            is_active=row.get("is_active", True),
        )
        db.add(variant)
        await db.flush()
        action = "created"

    if "stock_quantity" in row:
        await _set_stock(db, variant.id, row["stock_quantity"])

    return action


async def _set_stock(db: Any, variant_id: uuid.UUID, target: int) -> None:
    """Set available stock at the default warehouse via an audited adjustment."""
    item = (
        await db.execute(
            select(InventoryItem).where(
                InventoryItem.variant_id == variant_id,
                InventoryItem.warehouse_id == DEFAULT_WAREHOUSE_ID,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        item = InventoryItem(
            variant_id=variant_id,
            warehouse_id=DEFAULT_WAREHOUSE_ID,
            available=0,
        )
        db.add(item)
        await db.flush()
    delta = target - item.available
    if delta != 0:
        await inventory_service.adjust_stock(
            db,
            variant_id=variant_id,
            quantity=delta,
            tx_type=TransactionType.ADJUSTED,
            reference_type="import_job",
            notes="ویرایش موجودی از طریق import",
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def export_product_rows(
    db: Any, filters: dict[str, Any]
) -> "AsyncIterator[dict[str, Any]]":
    """Yield one export row per default variant (Toman price at the boundary)."""
    from app.modules.catalog.schemas.catalog import rial_to_toman

    conditions = []
    category_ref = filters.get("category")
    if category_ref:
        category = await _resolve_category(db, str(category_ref))
        if category is None:
            raise ValidationError(f"دسته‌بندی «{category_ref}» یافت نشد")
        conditions.append(Product.category_id == category.id)
    if filters.get("is_active") is not None:
        conditions.append(Product.is_active == bool(filters["is_active"]))

    stmt = (
        select(Product, ProductVariant)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .where(*conditions)
        .order_by(Product.created_at.desc())
    )
    result = await db.execute(stmt)
    for product, variant in result.all():
        stock = (
            await db.execute(
                select(func.coalesce(InventoryItem.available, 0)).where(
                    InventoryItem.variant_id == variant.id,
                    InventoryItem.warehouse_id == DEFAULT_WAREHOUSE_ID,
                )
            )
        ).scalar() or 0
        yield {
            "id": str(product.id),
            "sku": variant.sku,
            "name": product.name,
            "slug": product.slug,
            "price": rial_to_toman(variant.price),
            "stock_quantity": stock,
            "category": product.category.slug if product.category else "",
            "description": product.description or "",
            "is_active": product.is_active,
            "created_at": product.created_at.isoformat() if product.created_at else "",
        }


PRODUCT_EXPORT_EXTRA_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(key="id", label="شناسه"),
    ColumnSpec(key="created_at", label="تاریخ ایجاد"),
)


register_adapter(
    EntityAdapter(
        entity_type="product",
        label="محصولات",
        columns=PRODUCT_COLUMNS,
        upsert_row=upsert_product_row,
        export_rows=export_product_rows,
    )
)
