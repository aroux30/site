"""Dynamic per-category order fields (Karta categoryFields / Sprint 1.7).

Category-scoped field definitions (Player ID, server, region, account
email, ...) rendered on the order form and persisted with order items.

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

_ALLOWED_FIELD_TYPES = {"text", "number", "select"}


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


async def create_field(
    db: AsyncSession,
    *,
    category_id: uuid.UUID,
    field_key: str,
    label: str,
    field_type: str = "text",
    is_required: bool = False,
    position: int = 0,
    options: list[str] | None = None,
) -> CategoryCustomField:
    """Create a dynamic field definition for a category (admin)."""
    from app.modules.catalog.domain.models import Category

    safe_category = uuid.UUID(str(category_id))
    category = await db.get(Category, safe_category)
    if category is None:
        raise NotFoundError(resource="Category", detail=f"Category {safe_category} not found")

    clean_key = field_key.strip().lower().replace(" ", "_")[:64]
    if not clean_key:
        raise ValidationError("کلید فیلد الزامی است")
    if field_type not in _ALLOWED_FIELD_TYPES:
        raise ValidationError(
            f"نوع فیلد باید یکی از این‌ها باشد: {', '.join(sorted(_ALLOWED_FIELD_TYPES))}"
        )
    if field_type == "select" and not options:
        raise ValidationError("فیلد انتخابی به گزینه‌ها نیاز دارد")

    existing = await list_fields_for_category(db, safe_category)
    if any(f.field_key == clean_key for f in existing):
        raise ValidationError(f"کلید فیلد «{clean_key}» برای این دسته‌بندی تکراری است")

    field = CategoryCustomField(
        category_id=safe_category,
        field_key=clean_key,
        label=label.strip()[:200],
        field_type=field_type,
        is_required=is_required,
        position=position,
    )
    if options:
        field.options_json = [str(o).strip()[:200] for o in options if str(o).strip()]
    db.add(field)
    await db.flush()

    await logger.ainfo(
        "category_custom_field_created",
        category_id=str(safe_category),
        field_key=clean_key,
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
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            if definition.is_required:
                raise ValidationError(
                    detail=f"پر کردن فیلد «{definition.label}» الزامی است",
                    error_code="CUSTOM_FIELD_REQUIRED",
                )
            continue

        if definition.field_type == "number":
            try:
                cleaned[definition.field_key] = int(str(raw).strip())
            except ValueError:
                try:
                    cleaned[definition.field_key] = float(str(raw).strip())
                except ValueError:
                    raise ValidationError(
                        detail=f"مقدار فیلد «{definition.label}» باید عدد باشد",
                        error_code="CUSTOM_FIELD_INVALID",
                    ) from None
        elif definition.field_type == "select":
            options = set(definition.options_json or [])
            value = str(raw).strip()
            if options and value not in options:
                raise ValidationError(
                    detail=f"مقدار فیلد «{definition.label}» از گزینه‌های مجاز نیست",
                    error_code="CUSTOM_FIELD_INVALID",
                )
            cleaned[definition.field_key] = value
        else:
            cleaned[definition.field_key] = str(raw).strip()[:500]

    unknown = set(answers) - {d.field_key for d in definitions}
    if unknown:
        raise ValidationError(
            detail=f"فیلد(های) ناشناخته: {', '.join(sorted(unknown))}",
            error_code="CUSTOM_FIELD_UNKNOWN",
        )
    return cleaned
