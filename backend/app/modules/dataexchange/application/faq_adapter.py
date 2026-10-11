"""FAQ-item adapter for the generic import/export framework.

FAQ items have no DB-level unique key; the content transfer service already
treats ``(question, category)`` as the de-facto one
(``content/application/transfer_service.py``: "upsert pages by slug; append
missing FAQs by (question, category)"). This adapter uses the same composite
key so a CSV re-import skips what exists and updates what changed instead of
appending duplicates — the failure mode a store owner hits on the second
upload of the same spreadsheet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.content.domain.models import FAQItem
from app.modules.dataexchange.application.adapters import (
    ColumnSpec,
    EntityAdapter,
    register_adapter,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _validate_question(value: str) -> str | None:
    if len(value) > 300:
        return "پرسش بیش از ۳۰۰ کاراکتر است"
    return None


FAQ_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="question",
        label="پرسش",
        required=True,
        type="string",
        aliases=("سوال", "عنوان", "question", "title"),
        extra_validator=_validate_question,
    ),
    ColumnSpec(
        key="answer_html",
        label="پاسخ (HTML)",
        required=True,
        type="string",
        aliases=("پاسخ", "جواب", "answer"),
    ),
    ColumnSpec(
        key="category",
        label="دسته",
        required=False,
        type="string",
        aliases=("دسته‌بندی", "گروه", "category"),
    ),
    ColumnSpec(
        key="position",
        label="ترتیب",
        required=False,
        type="integer",
        aliases=("ردیف", "order", "sort"),
    ),
    ColumnSpec(
        key="is_active",
        label="فعال",
        required=False,
        type="boolean",
        aliases=("وضعیت فعال", "active", "enabled"),
    ),
)


async def upsert_faq_row(db: Any, row: dict[str, Any]) -> str:
    """Create or update an FAQ item matched by (question, category)."""
    question = str(row["question"]).strip()
    category = str(row.get("category") or "عمومی").strip() or "عمومی"

    existing = (
        await db.execute(
            select(FAQItem).where(
                FAQItem.question == question, FAQItem.category == category
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.answer_html = row["answer_html"]
        if row.get("position") is not None:
            existing.position = row["position"]
        if "is_active" in row:
            existing.is_active = row["is_active"]
        return "updated"

    db.add(
        FAQItem(
            question=question,
            answer_html=row["answer_html"],
            category=category,
            position=row.get("position") or 0,
            is_active=row.get("is_active", True),
        )
    )
    await db.flush()
    return "created"


async def export_faq_rows(
    db: Any, filters: dict[str, Any]
) -> "AsyncIterator[dict[str, Any]]":
    """Yield one export row per FAQ item."""
    rows = (
        await db.execute(
            select(FAQItem).order_by(FAQItem.category, FAQItem.position)
        )
    ).scalars().all()
    for f in rows:
        yield {
            "id": str(f.id),
            "question": f.question,
            "answer_html": f.answer_html,
            "category": f.category,
            "position": f.position,
            "is_active": f.is_active,
            "created_at": f.created_at.isoformat() if f.created_at else "",
        }


register_adapter(
    EntityAdapter(
        entity_type="faq",
        label="پرسش‌های متداول",
        columns=FAQ_COLUMNS,
        upsert_row=upsert_faq_row,
        export_rows=export_faq_rows,
        business_key="question",
    )
)
