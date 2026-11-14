"""Per-product add-on fields — WooCommerce Product Add-ons parity.

Where ``custom_field_service`` handles category-scoped order fields, this
service attaches buyer-input fields to ONE product (the owner's request:
addon fields are often product-specific — engraving, jersey name/number —
and meaningless store-wide). Definitions are created in the admin product
editor, rendered on the product page, validated server-side at checkout,
and persisted with the order item under ``p:``-prefixed keys.

Field types mirror the reference plugin (includes/admin/views/html-addon.php):
multiple_choice, checkbox, custom_text, custom_textarea, custom_price,
input_multiplier, heading. File upload needs a public customer-upload
endpoint this stack does not have yet — out of scope (delivery report).

Prices: DB stores Rial; the API boundary speaks Toman
(memory: money-unit-two-conventions).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.catalog.schemas.catalog import rial_to_toman, toman_to_rial
from app.modules.inventory.domain.digital_models import ProductAddonField

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

#: Reference plugin's panel type list (file_upload excluded — no public
#: customer-upload endpoint exists in this stack yet).
ALLOWED_ADDON_TYPES = {
    "multiple_choice",
    "checkbox",
    "custom_text",
    "custom_textarea",
    "custom_price",
    "input_multiplier",
    "heading",
}
_ALLOWED_PRICE_TYPES = {"flat_fee", "quantity_based", "percentage_based"}
_ALLOWED_DISPLAYS = {"select", "radio", "checkbox"}


async def list_fields_for_product(
    db: AsyncSession, product_id: uuid.UUID
) -> list[ProductAddonField]:
    """Active definitions for one product, ordered for display."""
    rows = (
        await db.execute(
            select(ProductAddonField)
            .where(ProductAddonField.product_id == product_id)
            .order_by(ProductAddonField.position.asc(), ProductAddonField.created_at.asc())
        )
    ).scalars().all()
    return list(rows)


def _clean_payload(
    *,
    field_key: str,
    label: str,
    field_type: str,
    description: str | None,
    display: str | None,
    options: list[dict[str, Any]] | None,
    is_required: bool,
    min_val: int | None,
    max_val: int | None,
    price: int | None,  # Toman in → Rial stored
    price_type: str | None,
) -> dict[str, Any]:
    """Shared shape validation for create AND update — same rules, one source."""
    key = (field_key or "").strip().lower()
    if not key or len(key) > 64 or not key.replace("_", "a").replace("-", "a").isalnum():
        raise ValidationError(
            detail="کلید فیلد باید ۱ تا ۶۴ کاراکتر انگلیسی/عدد/زیرخط باشد",
            error_code="ADDON_FIELD_KEY_INVALID",
        )
    clean_label = (label or "").strip()
    if not clean_label or len(clean_label) > 200:
        raise ValidationError(
            detail="برچسب فیلد الزامی است (حداکثر ۲۰۰ کاراکتر)",
            error_code="ADDON_FIELD_LABEL_INVALID",
        )
    if field_type not in ALLOWED_ADDON_TYPES:
        raise ValidationError(
            detail="نوع فیلد مجاز نیست",
            error_code="ADDON_FIELD_TYPE_INVALID",
        )
    if display is not None and display not in _ALLOWED_DISPLAYS:
        raise ValidationError(
            detail="نحوه نمایش فیلد مجاز نیست",
            error_code="ADDON_FIELD_DISPLAY_INVALID",
        )

    clean_options: list[dict[str, Any]] | None = None
    if field_type in ("multiple_choice", "checkbox"):
        raw_options = options or []
        if not raw_options:
            raise ValidationError(
                detail="برای این نوع فیلد حداقل یک گزینه الزامی است",
                error_code="ADDON_FIELD_OPTIONS_REQUIRED",
            )
        clean_options = []
        seen_labels: set[str] = set()
        for opt in raw_options[:100]:
            opt_label = str(opt.get("label") or "").strip()
            if not opt_label or len(opt_label) > 200:
                raise ValidationError(
                    detail="برچسب هر گزینه الزامی است (حداکثر ۲۰۰ کاراکتر)",
                    error_code="ADDON_FIELD_OPTION_INVALID",
                )
            if opt_label in seen_labels:
                raise ValidationError(
                    detail="برچسب گزینه‌های تکراری مجاز نیست",
                    error_code="ADDON_FIELD_OPTION_DUP",
                )
            seen_labels.add(opt_label)
            opt_price = opt.get("price")
            opt_price_type = opt.get("price_type")
            clean_options.append(
                {
                    "label": opt_label,
                    # option price arrives Toman, stored Rial (nullable).
                    "price": int(toman_to_rial(int(opt_price)))
                    if opt_price not in (None, "", 0)
                    else None,
                    "price_type": opt_price_type
                    if opt_price_type in _ALLOWED_PRICE_TYPES
                    else "flat_fee",
                }
            )
    elif options:
        raise ValidationError(
            detail="این نوع فیلد گزینه نمی‌پذیرد",
            error_code="ADDON_FIELD_OPTIONS_NOT_ALLOWED",
        )

    if field_type == "custom_price":
        # Buyer-defined price: min/max is the Toman price range itself.
        lo = int(min_val) if min_val is not None else None
        hi = int(max_val) if max_val is not None else None
        if lo is not None and lo < 0:
            lo = 0
        if lo is not None and hi is not None and lo > hi:
            raise ValidationError(
                detail="حداقل قیمت نمی‌تواند بیشتر از حداکثر باشد",
                error_code="ADDON_FIELD_RANGE_INVALID",
            )
        min_val, max_val = lo, hi
    elif field_type == "input_multiplier":
        lo = int(min_val) if min_val is not None else None
        hi = int(max_val) if max_val is not None else None
        if lo is not None and lo < 1:
            lo = 1
        if lo is not None and hi is not None and lo > hi:
            raise ValidationError(
                detail="حداقل تعداد نمی‌تواند بیشتر از حداکثر باشد",
                error_code="ADDON_FIELD_RANGE_INVALID",
            )
        min_val, max_val = lo, hi
    else:
        # Texts: character limits only.
        if min_val is not None and int(min_val) < 0:
            min_val = int(min_val)
        if max_val is not None and int(max_val) < 0:
            max_val = int(max_val)

    if price_type is not None and price_type not in _ALLOWED_PRICE_TYPES:
        raise ValidationError(
            detail="نوع قیمت فیلد مجاز نیست",
            error_code="ADDON_FIELD_PRICE_TYPE_INVALID",
        )

    return {
        "field_key": key,
        "label": clean_label,
        "description": (description or "").strip()[:500] or None,
        "field_type": field_type,
        "display": display if field_type == "multiple_choice" else None,
        "options_json": clean_options,
        "is_required": bool(is_required) and field_type != "heading",
        "min_val": min_val,
        "max_val": max_val,
        "price": int(toman_to_rial(int(price))) if price not in (None, "", 0) else None,
        "price_type": price_type,
    }


async def create_field(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    field_key: str,
    label: str,
    field_type: str = "custom_text",
    description: str | None = None,
    display: str | None = None,
    options: list[dict[str, Any]] | None = None,
    is_required: bool = False,
    min_val: int | None = None,
    max_val: int | None = None,
    price: int | None = None,  # Toman in → Rial stored
    price_type: str | None = None,
    position: int = 0,
) -> ProductAddonField:
    """Create one add-on definition with server-side shape validation."""
    cleaned = _clean_payload(
        field_key=field_key,
        label=label,
        field_type=field_type,
        description=description,
        display=display,
        options=options,
        is_required=is_required,
        min_val=min_val,
        max_val=max_val,
        price=price,
        price_type=price_type,
    )
    field = ProductAddonField(product_id=product_id, position=int(position), **cleaned)
    db.add(field)
    await db.flush()
    await logger.ainfo("product_addon_field_created", product_id=str(product_id), key=cleaned["field_key"])
    return field


async def update_field(
    db: AsyncSession,
    *,
    field_id: uuid.UUID,
    label: str,
    field_type: str,
    description: str | None = None,
    display: str | None = None,
    options: list[dict[str, Any]] | None = None,
    is_required: bool = False,
    min_val: int | None = None,
    max_val: int | None = None,
    price: int | None = None,
    price_type: str | None = None,
) -> ProductAddonField:
    """Edit an existing add-on definition (label, type, options, limits...).

    ``field_key`` is deliberately NOT editable: it is the key buyer answers
    round-trip on and the key already-saved orders are stored under — renaming
    it would orphan past answers.
    """
    field = await db.get(ProductAddonField, field_id)
    if field is None:
        raise NotFoundError(resource="ProductAddonField", detail=f"Field {field_id} not found")

    cleaned = _clean_payload(
        field_key=field.field_key,  # unchanged — see docstring
        label=label,
        field_type=field_type,
        description=description,
        display=display,
        options=options,
        is_required=is_required,
        min_val=min_val,
        max_val=max_val,
        price=price,
        price_type=price_type,
    )
    for attr, value in cleaned.items():
        setattr(field, attr, value)
    await db.flush()
    await logger.ainfo("product_addon_field_updated", field_id=str(field_id))
    return field


async def delete_field(db: AsyncSession, *, field_id: uuid.UUID) -> None:
    field = await db.get(ProductAddonField, field_id)
    if field is None:
        raise NotFoundError(resource="ProductAddonField", detail=f"Field {field_id} not found")
    await db.delete(field)
    await db.flush()
    await logger.ainfo("product_addon_field_deleted", field_id=str(field_id))


def _option_price_toman(option: dict[str, Any], quantity: int) -> int:
    """One option's price contribution in Toman for a given quantity."""
    price_rial = int(option.get("price") or 0)
    if price_rial <= 0:
        return 0
    ptype = option.get("price_type") or "flat_fee"
    if ptype == "quantity_based":
        return rial_to_toman(price_rial) * quantity
    if ptype == "percentage_based":
        # Percentage of the addon price acts on the buyer's item total at the
        # storefront display level; checkout keeps the flat interpretation
        # here because the order-item price composition is unchanged in this
        # phase (declared in the delivery report).
        return rial_to_toman(price_rial)
    return rial_to_toman(price_rial)


async def validate_answers(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    quantity: int,
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Validate buyer answers against the product's add-on definitions.

    Returns the cleaned answer map (safe to persist under ``p:``-prefixed
    keys on the order item) plus ``__addon_total_toman`` — the summed add-on
    price for display/audit. Unknown keys, bad options, range violations and
    missing required fields are rejected.
    """
    definitions = await list_fields_for_product(db, uuid.UUID(str(product_id)))
    qty = max(1, int(quantity or 1))

    cleaned: dict[str, Any] = {}
    addon_total = 0

    for definition in definitions:
        raw = answers.get(definition.field_key)
        empty = raw is None or (isinstance(raw, str) and not str(raw).strip())

        if definition.field_type == "heading":
            continue

        if definition.field_type == "checkbox":
            # Multi-select of priced options: list of chosen labels.
            chosen = raw if isinstance(raw, list) else ([raw] if not empty else [])
            options = {o["label"]: o for o in (definition.options_json or [])}
            values: list[str] = []
            for item in chosen:
                label = str(item).strip()
                if label not in options:
                    raise ValidationError(
                        detail=f"مقدار فیلد «{definition.label}» از گزینه‌های مجاز نیست",
                        error_code="ADDON_FIELD_INVALID",
                    )
                values.append(label)
                addon_total += _option_price_toman(options[label], qty)
            if definition.is_required and not values:
                raise ValidationError(
                    detail=f"پر کردن فیلد «{definition.label}» الزامی است",
                    error_code="ADDON_FIELD_REQUIRED",
                )
            if values:
                cleaned[definition.field_key] = values
            continue

        if empty:
            if definition.is_required:
                raise ValidationError(
                    detail=f"پر کردن فیلد «{definition.label}» الزامی است",
                    error_code="ADDON_FIELD_REQUIRED",
                )
            continue

        if definition.field_type == "multiple_choice":
            label = str(raw).strip()
            options = {o["label"]: o for o in (definition.options_json or [])}
            if label not in options:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» از گزینه‌های مجاز نیست",
                    error_code="ADDON_FIELD_INVALID",
                )
            cleaned[definition.field_key] = label
            addon_total += _option_price_toman(options[label], qty)

        elif definition.field_type == "custom_price":
            try:
                amount = int(str(raw).strip())
            except ValueError:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» باید عدد باشد",
                    error_code="ADDON_FIELD_INVALID",
                ) from None
            lo = definition.min_val
            hi = definition.max_val
            if lo is not None and amount < lo:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» نمی‌تواند کمتر از حداقل باشد",
                    error_code="ADDON_FIELD_RANGE",
                )
            if hi is not None and amount > hi:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» نمی‌تواند بیشتر از حداکثر باشد",
                    error_code="ADDON_FIELD_RANGE",
                )
            cleaned[definition.field_key] = amount
            addon_total += amount * qty

        elif definition.field_type == "input_multiplier":
            try:
                amount = int(str(raw).strip())
            except ValueError:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» باید عدد باشد",
                    error_code="ADDON_FIELD_INVALID",
                ) from None
            lo = definition.min_val
            hi = definition.max_val
            if lo is not None and amount < lo:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» کمتر از حداقل مجاز است",
                    error_code="ADDON_FIELD_RANGE",
                )
            if hi is not None and amount > hi:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» بیشتر از حداکثر مجاز است",
                    error_code="ADDON_FIELD_RANGE",
                )
            cleaned[definition.field_key] = amount
            if definition.price:
                addon_total += rial_to_toman(int(definition.price)) * amount

        elif definition.field_type == "custom_textarea":
            text = str(raw).strip()
            if definition.max_val is not None and len(text) > definition.max_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداکثر {definition.max_val} کاراکتر است",
                    error_code="ADDON_FIELD_RANGE",
                )
            if definition.min_val is not None and len(text) < definition.min_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداقل {definition.min_val} کاراکتر است",
                    error_code="ADDON_FIELD_RANGE",
                )
            cleaned[definition.field_key] = text[:2000]

        else:  # custom_text
            text = str(raw).strip()
            if definition.max_val is not None and len(text) > definition.max_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداکثر {definition.max_val} کاراکتر است",
                    error_code="ADDON_FIELD_RANGE",
                )
            if definition.min_val is not None and len(text) < definition.min_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداقل {definition.min_val} کاراکتر است",
                    error_code="ADDON_FIELD_RANGE",
                )
            cleaned[definition.field_key] = text[:500]

    unknown = set(answers) - {d.field_key for d in definitions}
    if unknown:
        raise ValidationError(
            detail=f"فیلد(های) ناشناخته: {', '.join(sorted(str(u) for u in unknown))}",
            error_code="ADDON_FIELD_UNKNOWN",
        )

    if addon_total:
        cleaned["__addon_total_toman"] = addon_total
    return cleaned
