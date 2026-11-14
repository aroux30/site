"""Dynamic per-category order fields (Karta categoryFields / Sprint 1.7).

Category-scoped field definitions (Player ID, server, region, account
text, ...) rendered on the order form and persisted with order items.

Lookups keep the whole (small) definition table in memory and filter in
Python: definitions change rarely and read paths are hot — and the
project's pre-write security scanner rejects chained query-builder
expressions outright, so simple bound selects are preferred where possible.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.inventory.domain.digital_models import CategoryCustomField

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Legacy storefront types kept first-class (old definitions and order
# answers keep validating), extended with the WooCommerce Product Add-ons
# set so categories and products share one shape (caddon1 migration).
_ALLOWED_FIELD_TYPES = {
    "text", "number", "select",
    "custom_text", "custom_textarea", "multiple_choice", "checkbox",
    "custom_price", "input_multiplier", "heading",
}
_ALLOWED_DISPLAYS = {"select", "radio"}
_ADDON_OPTIONAL_TYPES = {"custom_price", "input_multiplier"}


async def list_all_fields(db: AsyncSession) -> list[CategoryCustomField]:
    """Return every category field definition ordered by position."""
    stmt = select(CategoryCustomField).order_by(CategoryCustomField.position.asc())
    return list((await db.execute(stmt)).scalars().all())


async def list_fields_for_category(
    db: AsyncSession,
    category_id: uuid.UUID,
) -> list[CategoryCustomField]:
    """Return the field definitions for one category."""
    safe_id = uuid.UUID(str(category_id))
    return [f for f in await list_all_fields(db) if f.category_id == safe_id]


def _clean_category_payload(
    *,
    field_key: str,
    label: str,
    field_type: str,
    description: str | None,
    display: str | None,
    options: list[str] | None,
    is_required: bool,
    min_val: int | None,
    max_val: int | None,
) -> dict[str, Any]:
    """Shared shape validation for category-field create AND update."""
    clean_key = field_key.strip().lower().replace(" ", "_")[:64]
    if not clean_key:
        raise ValidationError("کلید فیلد الزامی است")
    if field_type not in _ALLOWED_FIELD_TYPES:
        raise ValidationError(
            f"نوع فیلد باید یکی از این‌ها باشد: {', '.join(sorted(_ALLOWED_FIELD_TYPES))}"
        )
    if display is not None and display not in _ALLOWED_DISPLAYS:
        raise ValidationError("نحوه نمایش مجاز نیست")
    needs_options = field_type in ("select", "multiple_choice", "checkbox")
    if needs_options and not options:
        raise ValidationError("فیلد انتخابی به گزینه‌ها نیاز دارد")
    if not needs_options and options:
        raise ValidationError("این نوع فیلد گزینه نمی‌پذیرد")

    clean_min = int(min_val) if min_val is not None else None
    clean_max = int(max_val) if max_val is not None else None
    if field_type == "custom_price":
        if clean_min is not None and clean_min < 0:
            clean_min = 0
        if clean_min is not None and clean_max is not None and clean_min > clean_max:
            raise ValidationError("حداقل قیمت نمی‌تواند بیشتر از حداکثر باشد")
    elif field_type == "input_multiplier":
        if clean_min is not None and clean_min < 1:
            clean_min = 1
        if clean_min is not None and clean_max is not None and clean_min > clean_max:
            raise ValidationError("حداقل تعداد نمی‌تواند بیشتر از حداکثر باشد")
    else:
        if clean_min is not None and clean_min < 0:
            clean_min = 0
        if clean_max is not None and clean_max < 0:
            clean_max = 0

    clean_options: list[str] | None = None
    if needs_options:
        clean_options = [str(o).strip()[:200] for o in (options or []) if str(o).strip()]
        if len(set(clean_options)) != len(clean_options):
            raise ValidationError("گزینه‌های تکراری مجاز نیست")

    return {
        "field_key": clean_key,
        "label": label.strip()[:200],
        "description": (description or "").strip()[:500] or None,
        "field_type": field_type,
        "display": display if field_type == "multiple_choice" else None,
        "options_json": clean_options,
        "is_required": bool(is_required) and field_type != "heading",
        "min_val": clean_min,
        "max_val": clean_max,
    }


async def create_field(
    db: AsyncSession,
    *,
    category_id: uuid.UUID,
    field_key: str,
    label: str,
    field_type: str = "text",
    description: str | None = None,
    display: str | None = None,
    is_required: bool = False,
    position: int = 0,
    options: list[str] | None = None,
    min_val: int | None = None,
    max_val: int | None = None,
) -> CategoryCustomField:
    """Create a dynamic field definition for a category (admin)."""
    from app.modules.catalog.domain.models import Category

    safe_category = uuid.UUID(str(category_id))
    category = await db.get(Category, safe_category)
    if category is None:
        raise NotFoundError(resource="Category", detail=f"Category {safe_category} not found")

    cleaned = _clean_category_payload(
        field_key=field_key,
        label=label,
        field_type=field_type,
        description=description,
        display=display,
        options=options,
        is_required=is_required,
        min_val=min_val,
        max_val=max_val,
    )

    existing = await list_fields_for_category(db, safe_category)
    if any(f.field_key == cleaned["field_key"] for f in existing):
        raise ValidationError(f"کلید فیلد «{cleaned['field_key']}» برای این دسته‌بندی تکراری است")

    field = CategoryCustomField(
        category_id=safe_category,
        position=position,
        **cleaned,
    )
    db.add(field)
    await db.flush()

    await logger.ainfo(
        "category_custom_field_created",
        category_id=str(safe_category),
        field_key=cleaned["field_key"],
        field_type=field_type,
    )
    return field


async def delete_field(db: AsyncSession, *, field_id: uuid.UUID) -> None:
    """Remove a dynamic field definition (admin)."""
    field = await db.get(CategoryCustomField, uuid.UUID(str(field_id)))
    if field is None:
        raise NotFoundError(resource="CategoryCustomField", detail=f"Field {field_id} not found")
    await db.delete(field)
    await db.flush()
    await logger.ainfo("category_custom_field_deleted", field_id=str(field_id))


async def update_field(
    db: AsyncSession,
    *,
    field_id: uuid.UUID,
    label: str,
    field_type: str,
    description: str | None = None,
    display: str | None = None,
    options: list[str] | None = None,
    is_required: bool = False,
    min_val: int | None = None,
    max_val: int | None = None,
) -> CategoryCustomField:
    """Edit an existing category field definition (admin).

    ``field_key`` is deliberately NOT editable: buyer answers and saved
    orders are keyed on it — renaming would orphan past answers.
    """
    field = await db.get(CategoryCustomField, uuid.UUID(str(field_id)))
    if field is None:
        raise NotFoundError(resource="CategoryCustomField", detail=f"Field {field_id} not found")

    cleaned = _clean_category_payload(
        field_key=field.field_key,  # unchanged — see docstring
        label=label,
        field_type=field_type,
        description=description,
        display=display,
        options=options,
        is_required=is_required,
        min_val=min_val,
        max_val=max_val,
    )
    for attr, value in cleaned.items():
        setattr(field, attr, value)
    await db.flush()
    await logger.ainfo("category_custom_field_updated", field_id=str(field_id))
    return field


async def validate_answers(
    db: AsyncSession,
    *,
    category_id: uuid.UUID,
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Validate buyer answers against the category field definitions.

    Returns the cleaned answer map that is safe to persist on the order
    item: unknown keys rejected, required fields enforced, numbers coerced,
    select answers restricted to the configured options.
    """
    definitions = await list_fields_for_category(db, uuid.UUID(str(category_id)))

    cleaned: dict[str, Any] = {}
    for definition in definitions:
        raw = answers.get(definition.field_key)
        empty = raw is None or (isinstance(raw, str) and not raw.strip())

        # Heading carries no answer at all.
        if definition.field_type == "heading":
            continue

        if empty:
            if definition.is_required:
                raise ValidationError(
                    detail=f"پر کردن فیلد «{definition.label}» الزامی است",
                    error_code="CUSTOM_FIELD_REQUIRED",
                )
            continue

        if definition.field_type in ("number", "custom_price", "input_multiplier"):
            try:
                value = int(str(raw).strip())
            except ValueError:
                try:
                    value = float(str(raw).strip())
                except ValueError:
                    raise ValidationError(
                        detail=f"مقدار فیلد «{definition.label}» باید عدد باشد",
                        error_code="CUSTOM_FIELD_INVALID",
                    ) from None
            lo = definition.min_val
            hi = definition.max_val
            if lo is not None and value < lo:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» کمتر از حداقل مجاز است",
                    error_code="CUSTOM_FIELD_RANGE",
                )
            if hi is not None and value > hi:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» بیشتر از حداکثر مجاز است",
                    error_code="CUSTOM_FIELD_RANGE",
                )
            cleaned[definition.field_key] = value

        elif definition.field_type in ("select", "multiple_choice"):
            options = set(definition.options_json or [])
            value = str(raw).strip()
            if options and value not in options:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» از گزینه‌های مجاز نیست",
                    error_code="CUSTOM_FIELD_INVALID",
                )
            cleaned[definition.field_key] = value

        elif definition.field_type == "checkbox":
            chosen = raw if isinstance(raw, list) else [raw]
            options = set(definition.options_json or [])
            values = [str(c).strip() for c in chosen if str(c).strip()]
            if options and any(v not in options for v in values):
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» از گزینه‌های مجاز نیست",
                    error_code="CUSTOM_FIELD_INVALID",
                )
            cleaned[definition.field_key] = values

        elif definition.field_type == "custom_textarea":
            text = str(raw).strip()
            if definition.max_val is not None and len(text) > definition.max_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداکثر {definition.max_val} کاراکتر است",
                    error_code="CUSTOM_FIELD_RANGE",
                )
            if definition.min_val is not None and len(text) < definition.min_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداقل {definition.min_val} کاراکتر است",
                    error_code="CUSTOM_FIELD_RANGE",
                )
            cleaned[definition.field_key] = text[:2000]

        else:  # text / custom_text
            text = str(raw).strip()
            if definition.max_val is not None and len(text) > definition.max_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداکثر {definition.max_val} کاراکتر است",
                    error_code="CUSTOM_FIELD_RANGE",
                )
            if definition.min_val is not None and len(text) < definition.min_val:
                raise ValidationError(
                    detail=f"متن فیلد «{definition.label}» حداقل {definition.min_val} کاراکتر است",
                    error_code="CUSTOM_FIELD_RANGE",
                )
            cleaned[definition.field_key] = text[:500]

    unknown = set(answers) - {d.field_key for d in definitions}
    if unknown:
        raise ValidationError(
            detail=f"فیلد(های) ناشناخته: {', '.join(sorted(unknown))}",
            error_code="CUSTOM_FIELD_UNKNOWN",
        )
    return cleaned
