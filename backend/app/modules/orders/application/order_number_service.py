"""Sequential numeric order-number generation (WordPress-style #1, #2, …).

Kept in its own module so the checkout path depends on one small, testable
unit instead of the full order service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError
from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# site_settings row backing the counter. Every writer locks this row (FOR
# UPDATE) before taking a number, so concurrent checkouts serialize instead
# of colliding on the unique orders.order_number constraint. Created and
# seeded by the ``orders_numeric_order_number`` migration.
COUNTER_SETTING_KEY = "orders.order_number_counter"


async def next_order_number(db: AsyncSession) -> str:
    """Return the next sequential numeric order number: ``1``, ``2``, ``3``, …

    Numbers come from a counter row in ``site_settings`` that every writer
    locks with ``FOR UPDATE`` before taking a value, so concurrent checkouts
    cannot collide on the unique ``orders.order_number`` constraint. The
    increment commits with the order itself, so a rolled-back checkout
    doesn't burn a number.
    """
    counter = (
        await db.execute(
            select(SiteSetting)
            .where(SiteSetting.key == COUNTER_SETTING_KEY)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if counter is None:
        # The migration seeds this row on every database; reaching here means
        # it was never applied (or the row was deleted by hand).
        raise ConflictError(
            error_code="ORDER_NUMBER_COUNTER_MISSING",
            detail="شمارندهٔ شمارهٔ سفارش یافت نشد؛ مایگریشن‌های دیتابیس را اجرا کنید.",
        )
    value = dict(counter.value or {})
    number = int(value.get("next", 1))
    value["next"] = number + 1
    counter.value = value
    return str(number)
