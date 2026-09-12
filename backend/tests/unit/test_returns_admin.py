"""Regression tests for RMA persistence and admin processing (TASK BE-20)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.handlers import ValidationError
from app.modules.orders.domain.return_models import (
    OrderReturn,
    OrderReturnItem,
)


def _make_rma_row(*, status: str = "requested", outcomes: list[str | None] | None = None):
    """Build an OrderReturn row with two items (variants v1, v2)."""
    v1, v2 = uuid.uuid4(), uuid.uuid4()
    row = OrderReturn(
        id=uuid.uuid4(),
        rma_number="RMA-TEST-0001",
        order_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=status,
        refund_amount=0,
        created_at=datetime.now(UTC),
    )
    specs = outcomes or [None, None]
    reasons = ["defective", "customer_remorse"]
    for variant, qty, outcome, reason in zip((v1, v2), (2, 1), specs, reasons, strict=False):
        row.items.append(
            OrderReturnItem(
                return_id=row.id,
                order_item_id=uuid.uuid4(),
                variant_id=variant,
                quantity=qty,
                reason=reason,
                inspection_outcome=outcome,
            )
        )
    return row, v1, v2


def _mock_db(row):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def _get(model, pk, **kwargs):
        return row if model is OrderReturn else None

    db.get = AsyncMock(side_effect=_get)
    return db


@pytest.mark.asyncio
async def test_rma_approve_transition_persists_and_publishes():
    """BE-20: approving an RMA persists the status and publishes the event."""
    from app.modules.orders.application import order_service

    row, _v1, _v2 = _make_rma_row(status="requested")
    db = _mock_db(row)
    publish = AsyncMock()

    with patch("app.shared.events.outbox_service.OutboxService.publish", new=publish):
        response = await order_service.admin_transition_return(
            db,
            return_id=row.id,
            target="approved",
            actor_id=uuid.uuid4(),
            notes="accepted",
        )

    assert response.status == "approved"
    assert row.status == "approved"
    assert row.approved_at is not None
    assert row.admin_notes == "accepted"
    published = [c.kwargs["event_type"] for c in publish.await_args_list]
    assert "ReturnApproved" in published


@pytest.mark.asyncio
async def test_rma_invalid_transition_rejected_by_domain_machine():
    """The domain state machine, not the caller, decides valid moves."""
    from app.modules.orders.application import order_service

    row, _v1, _v2 = _make_rma_row(status="requested")  # requested → refunded is illegal
    db = _mock_db(row)

    with pytest.raises(ValidationError):
        await order_service.admin_transition_return(
            db,
            return_id=row.id,
            target="refunded",
            actor_id=uuid.uuid4(),
            refund_amount=10_000,
        )
    assert row.status == "requested"  # unchanged


@pytest.mark.asyncio
async def test_rma_unknown_target_rejected():
    from app.modules.orders.application import order_service

    row, _v1, _v2 = _make_rma_row(status="requested")
    db = _mock_db(row)

    with pytest.raises(ValidationError):
        await order_service.admin_transition_return(
            db,
            return_id=row.id,
            target="teleported",
            actor_id=uuid.uuid4(),
        )


def _make_paid_order(*, paid_amount: int = 100_000, refunded: int = 0):
    """Build a fake Order with one completed payment and prior refunds."""
    from unittest.mock import MagicMock

    from app.modules.orders.domain.models import Order
    from app.modules.payments.domain.models import PaymentStatus

    payment = MagicMock(status=PaymentStatus.COMPLETED, amount=paid_amount, id=uuid.uuid4())
    payment.refunds = []
    if refunded:
        prior = MagicMock(status=MagicMock(), amount=refunded)
        from app.modules.payments.domain.models import RefundStatus

        prior.status = RefundStatus.PROCESSED
        payment.refunds.append(prior)
    order = MagicMock(
        spec=Order,
        id=uuid.uuid4(),
        order_number="ORD-TEST-0001",
        payments=[payment],
    )
    return order, payment


def _mock_db_with_order(row, order):
    db = _mock_db(row)

    async def _get(model, pk, **kwargs):
        from app.modules.orders.domain.models import Order
        from app.modules.orders.domain.return_models import OrderReturn

        if model is OrderReturn or model is Order:
            if model is OrderReturn:
                return row
            return order
        return None

    db.get = AsyncMock(side_effect=_get)
    return db


@pytest.mark.asyncio
async def test_rma_refund_restocks_only_passed_items():
    """P3-01: on refund, only PASSED inspection items return to stock."""
    from app.modules.orders.application import order_service

    row, v1, _v2 = _make_rma_row(status="inspected", outcomes=["passed", "damaged_by_customer"])
    order, _payment = _make_paid_order()
    db = _mock_db_with_order(row, order)
    restock = AsyncMock(return_value=2)

    with (
        patch(
            "app.modules.inventory.application.inventory_service.restock_returned_items",
            new=restock,
        ),
        patch("app.shared.events.outbox_service.OutboxService.publish", new=AsyncMock()),
        patch("app.modules.wallet.application.wallet_service.credit", new=AsyncMock()),
    ):
        await order_service.admin_transition_return(
            db,
            return_id=row.id,
            target="refunded",
            actor_id=uuid.uuid4(),
            refund_amount=30_000,
        )

    assert row.status == "refunded"
    assert row.refunded_at is not None
    assert row.refund_amount == 30_000
    restock.assert_awaited_once()
    entries = restock.await_args.args[1]
    assert entries == [(v1, 2)]  # only the passed variant, damaged one excluded


@pytest.mark.asyncio
async def test_rma_refund_rejects_amount_above_refundable():
    """Refund amount must never exceed what is actually refundable."""
    from app.modules.orders.application import order_service

    row, _v1, _v2 = _make_rma_row(status="inspected", outcomes=["passed", "passed"])
    order, _payment = _make_paid_order(paid_amount=50_000, refunded=20_000)
    db = _mock_db_with_order(row, order)

    with pytest.raises(ValidationError):
        await order_service.admin_transition_return(
            db,
            return_id=row.id,
            target="refunded",
            actor_id=uuid.uuid4(),
            refund_amount=31_000,  # refundable ceiling is 30_000
        )


@pytest.mark.asyncio
async def test_rma_refund_rejects_zero_amount():
    """A zero/absent refund amount must not close the RMA as refunded."""
    from app.modules.orders.application import order_service

    row, _v1, _v2 = _make_rma_row(status="inspected", outcomes=["passed"])
    order, _payment = _make_paid_order()
    db = _mock_db_with_order(row, order)

    with pytest.raises(ValidationError):
        await order_service.admin_transition_return(
            db,
            return_id=row.id,
            target="refunded",
            actor_id=uuid.uuid4(),
            refund_amount=0,
        )


@pytest.mark.asyncio
async def test_restock_returned_items_moves_committed_stock():
    """restock_returned_items moves committed units back to available."""
    from app.modules.inventory.application import inventory_service

    variant_id = uuid.uuid4()
    item = MagicMock(id=uuid.uuid4(), committed=5, available=1)
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock(return_value=item)

    restocked = await inventory_service.restock_returned_items(db, [(variant_id, 2)])

    assert restocked == 2
    assert item.committed == 3
    assert item.available == 3
