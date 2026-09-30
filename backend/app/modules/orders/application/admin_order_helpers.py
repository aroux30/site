"""Pure-Python enrichment helpers for the admin order list.

The Order model loads ``items`` and ``user`` eagerly (selectin), so the
admin listing can compute item counts and customer identity in plain
Python without issuing any extra statements here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.modules.orders.schemas.order import OrderListItem

if TYPE_CHECKING:
    from collections.abc import Sequence


def enrich_admin_order_rows(orders: Sequence[Any]) -> list[OrderListItem]:
    """Map Order rows to OrderListItem with items_count and customer fields."""
    from app.modules.orders.schemas.order import OrderItemResponse

    enriched: list[OrderListItem] = []
    for order in orders:
        entry = OrderListItem.model_validate(order)
        order_items = order.items or []
        entry.items_count = sum(item.quantity for item in order_items)
        # Line-item briefs ride along for free — ``items`` is eagerly loaded
        # on the model, so this adds no extra statements (QA B20: kanban
        # used to fabricate a placeholder line when this list was absent).
        entry.items = [OrderItemResponse.model_validate(item) for item in order_items]
        user = getattr(order, "user", None)
        if user is not None:
            names = [getattr(user, "first_name", None), getattr(user, "last_name", None)]
            entry.customer_name = " ".join(n for n in names if n).strip() or None
            entry.customer_phone = getattr(user, "phone", None)
        enriched.append(entry)
    return enriched
