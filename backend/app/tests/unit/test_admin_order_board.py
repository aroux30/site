"""The admin board endpoints: stats, detail, and their route order.

Three silent-failure modes these tests pin down:

1. **Route order.** ``GET /admin/orders/stats`` and ``GET
   /admin/orders/{order_id}`` have the same segment count; if the parameter
   route is registered first, ``stats`` is captured as an order id and the
   board's header numbers 422. (The bulk-status route already documented
   this trap — this is the GET twin of it.)

2. **Zero-filled stats.** The board renders every column header at once; a
   status with no rows must still arrive with count=0, or the UI cannot
   tell "no orders" from "the endpoint forgot the status".

3. **Unmasked address on the admin detail route.** The customer-facing
   ``OrderResponse`` masks street-level detail. The admin route must NOT
   (an operator packing a parcel needs the full address), and the mask
   lives in a validator — a refactor that makes the admin schema inherit
   from the customer one would silently re-mask it.
"""

from __future__ import annotations

import inspect
import uuid

import pytest


def test_route_order_stats_before_order_id():
    """`/admin/orders/stats` must be registered before `/admin/orders/{order_id}`.

    Negative test: swap the two registrations in routes.py and this fails —
    FastAPI matches in registration order.
    """
    from app.modules.orders.api import routes as routes_module

    src = inspect.getsource(routes_module)
    stats_idx = src.index('"/admin/orders/stats"')
    detail_idx = src.index('"/admin/orders/{order_id}"')
    assert stats_idx < detail_idx, (
        "stats route is registered after {order_id} — the literal path would "
        "be captured as an order id"
    )


def test_admin_detail_schema_does_not_inherit_customer_schema():
    """The admin detail schema must not inherit OrderResponse's masking validator."""
    from app.modules.orders.schemas.order import AdminOrderDetailResponse, OrderResponse

    assert not issubclass(AdminOrderDetailResponse, OrderResponse), (
        "AdminOrderDetailResponse inherits OrderResponse — the address masking "
        "validator would apply and the admin drawer would show a masked address"
    )


async def test_stats_zero_fills_every_status():
    """Live DB: stats returns one entry per OrderStatus, counts are real."""
    from app.core.database.session import async_session_factory, engine
    from app.modules.orders.application.order_service import admin_get_order_stats
    from app.modules.orders.domain.models import OrderStatus

    async with async_session_factory() as db:
        stats = await admin_get_order_stats(db)

    returned = {entry.status for entry in stats.by_status}
    expected = {member.value for member in OrderStatus}
    assert returned == expected, f"missing statuses: {expected - returned}"

    for entry in stats.by_status:
        assert entry.count >= 0
        assert entry.total >= 0

    assert stats.total_orders == sum(e.count for e in stats.by_status)
    # Revenue excludes canceled/refunded; it can never exceed the sum of all.
    assert 0 <= stats.total_revenue_rials <= sum(e.total for e in stats.by_status)

    await engine.dispose()


async def test_detail_returns_unmasked_address_and_payments_list():
    """Live DB: an order with a full address comes back with the street intact."""
    from sqlalchemy import select

    from app.core.database.session import async_session_factory, engine
    from app.modules.orders.application.order_service import admin_get_order_detail
    from app.modules.orders.domain.models import Order

    async with async_session_factory() as db:
        row = (
            await db.execute(
                select(Order)
                .where(Order.shipping_address_snapshot.isnot(None))
                .limit(1)
            )
        ).scalars().first()

    if row is None:
        pytest.skip("no order with an address snapshot in the database")

    async with async_session_factory() as db:
        detail = await admin_get_order_detail(db, row.id)

    # The detail endpoint always carries a payments list (possibly empty) —
    # the old board invented "paid" because nothing ever sent payments.
    assert isinstance(detail.payments, list)

    addr = detail.shipping_address_snapshot or {}
    if addr.get("full_address"):
        # The mask replaces everything after the first two segments with ***.
        # An unmasked address from real checkout data must NOT end in "***".
        assert not str(addr["full_address"]).rstrip().endswith("***"), (
            "admin detail returned a MASKED address — the customer validator "
            "leaked into the admin schema"
        )

    await engine.dispose()


async def test_detail_missing_order_raises_not_found():
    from app.core.database.session import async_session_factory, engine
    from app.core.exceptions.handlers import NotFoundError
    from app.modules.orders.application.order_service import admin_get_order_detail

    async with async_session_factory() as db:
        with pytest.raises(NotFoundError):
            await admin_get_order_detail(db, uuid.uuid4())

    await engine.dispose()


# ── Multi-status filtering (the board's grouped lane) ────────────────────────


async def test_statuses_filter_returns_the_union_of_those_statuses():
    """`statuses=a,b` must return rows of a AND b — the board's «در حال پردازش» lane.

    The frontend groups pending+confirmed+processing+shipped+delivered into one
    column. That needs ONE query: fanning out client-side would page each
    status separately, so «نمایش بیشتر» would repeat and skip rows.
    """
    from sqlalchemy import func, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.orders.application.order_service import admin_get_orders
    from app.modules.orders.domain.models import Order, OrderStatus
    from app.modules.orders.schemas.order import OrderFilterParams, PaginationParams

    statuses = ["confirmed", "processing"]
    filters = OrderFilterParams(statuses=statuses)
    async with async_session_factory() as db:
        page = await admin_get_orders(db, filters, PaginationParams(page=1, page_size=100))

        expected_total = (
            await db.execute(
                select(func.count(Order.id)).where(Order.status.in_(statuses))
            )
        ).scalar_one()

    assert page.meta.total_items == expected_total, (
        "statuses filter counted differently from a direct IN() on the same set"
    )
    assert all(row.status in statuses for row in page.items), (
        "statuses filter leaked rows of other statuses"
    )
    # The meta the frontend actually reads (it reads total_items, not total).
    assert page.meta.total_pages >= 1

    await engine.dispose()


async def test_single_status_filter_is_not_widened_by_the_statuses_param():
    """When both are sent, `status` wins — a caller asked for one exact status."""
    from sqlalchemy import func, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.orders.application.order_service import admin_get_orders
    from app.modules.orders.domain.models import Order
    from app.modules.orders.schemas.order import OrderFilterParams, PaginationParams

    filters = OrderFilterParams(
        status="completed", statuses=["pending", "confirmed", "completed"]
    )
    async with async_session_factory() as db:
        page = await admin_get_orders(db, filters, PaginationParams(page=1, page_size=50))
        expected_total = (
            await db.execute(
                select(func.count(Order.id)).where(Order.status == "completed")
            )
        ).scalar_one()

    assert page.meta.total_items == expected_total
    assert all(row.status == "completed" for row in page.items)

    await engine.dispose()


async def test_blank_statuses_entries_are_ignored():
    """`?statuses=confirmed,` (trailing comma) must not filter on an empty string."""
    from sqlalchemy import func, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.orders.application.order_service import admin_get_orders
    from app.modules.orders.domain.models import Order
    from app.modules.orders.schemas.order import OrderFilterParams, PaginationParams

    filters = OrderFilterParams(statuses=["confirmed", "", "   "])
    async with async_session_factory() as db:
        page = await admin_get_orders(db, filters, PaginationParams(page=1, page_size=50))
        expected_total = (
            await db.execute(
                select(func.count(Order.id)).where(Order.status == "confirmed")
            )
        ).scalar_one()

    assert page.meta.total_items == expected_total
    assert all(row.status == "confirmed" for row in page.items)

    await engine.dispose()


def test_empty_statuses_list_does_not_filter_everything_out():
    """An empty list must mean "no status filter", not "match nothing"."""
    from app.modules.orders.application.order_service import _apply_filters
    from app.modules.orders.schemas.order import OrderFilterParams

    stmt = _apply_filters(select_stmt_for_test(), OrderFilterParams(statuses=[]))
    whereclause = str(stmt.whereclause)
    # No status predicate at all: a bare empty IN () would exclude every row.
    assert "status" not in whereclause.lower()


def select_stmt_for_test():  # pragma: no cover — trivial helper
    from sqlalchemy import select

    from app.modules.orders.domain.models import Order

    return select(Order)
