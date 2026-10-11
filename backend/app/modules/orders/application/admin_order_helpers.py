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
            entry.customer_phone = getattr(user, "phone", None)
            # Names live on the joined profile, not the user row. The old
            # mapper read user.first_name/last_name, attributes User does not
            # have — so customer_name was ALWAYS None and every admin screen
            # fell back to a placeholder or "—" (verified against live data:
            # 18 profiles carry names, and not one reached this field).
            # ``profile`` is lazy="joined", so this read is statement-free.
            profile = getattr(user, "profile", None)
            if profile is not None:
                names = [
                    getattr(profile, "first_name", None),
                    getattr(profile, "last_name", None),
                ]
                entry.customer_name = " ".join(n for n in names if n).strip() or None
                if not entry.customer_name:
                    entry.customer_name = getattr(profile, "display_name", None) or None
        enriched.append(entry)
    return enriched
