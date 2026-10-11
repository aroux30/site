"""The payment-waiting statuses, proven against the real transition path.

Complements `test_order_status_vocabulary.py` (which pins the table's SHAPE).
This file pins that the transitions an operator actually performs behave as
the owner's rule requires:

  - a gateway order can be moved into the operator's lane,
  - a card-to-card order can be moved into the operator's lane,
  - and neither of those moves is reachable in the WRONG direction (you cannot
    drag an already-paid order back into "waiting for payment").

`admin_update_status` is the same function the board's PATCH endpoint calls, so
these exercise the shipped path rather than a hand-rolled approximation.
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select

from app.core.database.session import async_session_factory, engine
from app.modules.orders.application.order_service import (
    admin_update_status,
    _validate_transition,
)
from app.modules.orders.domain.models import Order, OrderStatus


async def _any_user_id() -> uuid.UUID:
    """`changed_by` is a real FK to users — a fake actor 500s the write.

    This is the same trap that made a board verification report a 500 that
    looked like a product bug: the token was minted for a UUID with no row.
    """
    from app.modules.users.domain.models import User

    async with async_session_factory() as session:
        return (await session.execute(select(User.id).limit(1))).scalar_one()


async def _seed_order(status: OrderStatus) -> uuid.UUID:
    """Insert a throwaway order in a given status, to transition for real."""
    from app.modules.users.domain.models import User

    async with async_session_factory() as session:
        user_id = (await session.execute(select(User.id).limit(1))).scalar_one()
        order = Order(
            user_id=user_id,
            order_number=f"TEST-{uuid.uuid4().hex[:16]}",
            status=status,
            subtotal=10000,
            shipping_cost=0,
            tax=0,
            discount_amount=0,
            total=10000,
            idempotency_key=uuid.uuid4().hex,
        )
        session.add(order)
        await session.commit()
        return order.id


async def _cleanup(order_id: uuid.UUID) -> None:
    """Remove the throwaway order and its history rows.

    The history row must go first: `order_status_history.order_id` is NOT NULL
    with a CASCADE delete, but the row is inserted by a DIFFERENT session than
    the one that created the order, so deleting the order alone can race the
    insert and surface as a NOT NULL violation rather than a clean cleanup.
    """
    from sqlalchemy import text

    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM order_status_history WHERE order_id = :oid"),
            {"oid": order_id},
        )
        order = await session.get(Order, order_id)
        if order is not None:
            await session.delete(order)
        await session.commit()


@pytest.mark.parametrize(
    "waiting",
    [OrderStatus.WAITING_PAYMENT_GATEWAY, OrderStatus.WAITING_PAYMENT_CARD],
)
async def test_both_payment_waiting_states_can_enter_the_operators_lane(waiting):
    """Both a gateway callback and an admin approval land on PENDING."""
    order_id = await _seed_order(waiting)
    try:
        async with async_session_factory() as db:
            before = (await db.get(Order, order_id)).status
            assert before is waiting

            response = await admin_update_status(
                db,
                order_id=order_id,
                new_status=OrderStatus.PENDING.value,
                actor_id=await _any_user_id(),
            )
            await db.commit()

        assert response.status == OrderStatus.PENDING.value
        async with async_session_factory() as db:
            after = (await db.get(Order, order_id)).status
        assert after is OrderStatus.PENDING, (
            f"{waiting} did not actually move — a transition that silently "
            "does nothing is the most likely bug of all"
        )
    finally:
        await _cleanup(order_id)
        # pytest-asyncio gives every test its own event loop, but the module
        # engine is shared. Connections created on a closed loop surface as
        # "Event loop is closed" on the NEXT test, which reads as a product
        # bug rather than a test-harness one. Disposing here keeps each test's
        # pool bound to its own loop.
        await engine.dispose()


def test_a_paid_order_cannot_go_back_to_waiting_for_payment():
    """The board must not offer a paid order back into the payment wait.

    Otherwise an operator could drag a completed sale back into the column the
    auto-cancel sweep targets, and the sweep would cancel a paid order.
    """
    with pytest.raises(Exception):
        _validate_transition(OrderStatus.PENDING, OrderStatus.WAITING_PAYMENT_GATEWAY)
    with pytest.raises(Exception):
        _validate_transition(OrderStatus.PENDING, OrderStatus.WAITING_PAYMENT_CARD)


def test_completed_and_refunded_are_final():
    """Nothing leaves the two terminal money states — not even an admin."""
    for terminal in (OrderStatus.COMPLETED, OrderStatus.REFUNDED):
        for target in OrderStatus:
            with pytest.raises(Exception):
                _validate_transition(terminal, target)


def test_processing_can_reach_completed_but_not_skip_past_it():
    """The chain is short and linear; there is no jump from PENDING to COMPLETED."""
    _validate_transition(OrderStatus.PROCESSING, OrderStatus.COMPLETED)
    with pytest.raises(Exception):
        _validate_transition(OrderStatus.PENDING, OrderStatus.COMPLETED)