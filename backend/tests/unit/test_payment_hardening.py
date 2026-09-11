"""Regression tests for the payment / wallet / inventory hardening fixes.

Covers the P0 integration defects found in the end-to-end audit:

- PAY-01: payment amount was never validated against the order total
- PAY-02: payments could be created/verified for orders the caller does not own
- PAY-03: internal wallet payments never debited the wallet (free orders)
- WAL-01: ``POST /wallet/deposit`` minted balance without any payment
- INV-01: cancelled / unpaid orders never returned stock to inventory
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.modules.inventory.application import inventory_service
from app.modules.inventory.domain.models import (
    InventoryItem,
    InventoryReservation,
    ReservationStatus,
)
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.payments.application import payment_service
from app.modules.payments.domain.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
)


def _make_order(
    *,
    user_id: uuid.UUID,
    total: int = 500_000,
    status: OrderStatus = OrderStatus.PENDING,
    order_id: uuid.UUID | None = None,
) -> Order:
    return Order(
        id=order_id or uuid.uuid4(),
        user_id=user_id,
        order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
        status=status,
        subtotal=total,
        shipping_cost=0,
        tax=0,
        discount_amount=0,
        total=total,
    )


# ── create_payment validation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_rejects_amount_mismatch():
    """PAY-01: client-supplied amount must equal the order total."""
    user_id = uuid.uuid4()
    order = _make_order(user_id=user_id, total=1_000_000)

    db = MagicMock()
    db.get = AsyncMock(return_value=order)

    with pytest.raises(ValidationError) as exc:
        await payment_service.create_payment(
            db,
            user_id=user_id,
            order_id=order.id,
            provider="zarinpal",
            amount=100,
        )
    assert "does not match" in exc.value.detail


@pytest.mark.asyncio
async def test_create_payment_rejects_foreign_order():
    """PAY-02: a user cannot create a payment for someone else's order."""
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    order = _make_order(user_id=owner_id)

    db = MagicMock()
    db.get = AsyncMock(return_value=order)

    with pytest.raises(NotFoundError):
        await payment_service.create_payment(
            db,
            user_id=attacker_id,
            order_id=order.id,
            provider="zarinpal",
            amount=500_000,
        )


@pytest.mark.asyncio
async def test_create_payment_rejects_non_pending_order():
    """Only PENDING orders are payable — no double payment of confirmed orders."""
    user_id = uuid.uuid4()
    order = _make_order(user_id=user_id, status=OrderStatus.CONFIRMED)

    db = MagicMock()
    db.get = AsyncMock(return_value=order)

    with pytest.raises(ConflictError):
        await payment_service.create_payment(
            db,
            user_id=user_id,
            order_id=order.id,
            provider="zarinpal",
            amount=500_000,
        )


@pytest.mark.asyncio
async def test_create_payment_rejects_wallet_insufficient_balance():
    """Wallet payments fail fast when the balance cannot cover the total."""
    user_id = uuid.uuid4()
    order = _make_order(user_id=user_id, total=1_000_000)

    db = MagicMock()
    db.get = AsyncMock(return_value=order)

    with (
        patch(
            "app.modules.wallet.application.wallet_service.get_balance",
            new=AsyncMock(return_value=100),
        ),
        pytest.raises(PaymentError) as exc,
    ):
        await payment_service.create_payment(
            db,
            user_id=user_id,
            order_id=order.id,
            provider="wallet",
            amount=1_000_000,
        )
    assert exc.value.detail is not None


# ── wallet payment debit inside verify ───────────────────────────────────


def _wallet_verify_fixtures(user_id: uuid.UUID, amount: int = 500_000):
    """Build the mock session graph for a wallet payment verification."""
    order = _make_order(user_id=user_id, total=amount)
    payment = Payment(
        id=uuid.uuid4(),
        order_id=order.id,
        amount=amount,
        currency="IRR",
        provider=PaymentProvider.WALLET,
        status=PaymentStatus.PROCESSING,
        authority="WALLET-TESTAUTH01",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def _get(model, pk, **kwargs):
        if model is Payment:
            return payment
        if model is Order:
            return order
        return None

    db.get = AsyncMock(side_effect=_get)

    # The order-transition SELECT ... FOR UPDATE inside verify_payment
    transition_result = MagicMock(scalar_one_or_none=MagicMock(return_value=order))
    db.execute = AsyncMock(return_value=transition_result)

    return db, payment, order


@pytest.mark.asyncio
async def test_wallet_verify_debits_wallet_exactly_once():
    """PAY-03: wallet verification must debit the wallet before completing."""
    user_id = uuid.uuid4()
    db, payment, order = _wallet_verify_fixtures(user_id)

    debit = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    publish = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

    with (
        patch("app.modules.wallet.application.wallet_service.debit", new=debit),
        patch("app.shared.events.outbox_service.OutboxService.publish", new=publish),
    ):
        response = await payment_service.verify_payment(
            db,
            payment_id=payment.id,
            authority=payment.authority or "",
            status="OK",
        )

    assert response.status == PaymentStatus.COMPLETED
    debit.assert_awaited_once()
    assert debit.await_args.kwargs["user_id"] == user_id
    assert debit.await_args.kwargs["amount"] == payment.amount
    # The wallet debit and the order confirmation happen in one transaction
    assert order.status == OrderStatus.CONFIRMED
    # Domain events are published through the outbox
    assert publish.await_count == 2
    published_types = [c.kwargs["event_type"] for c in publish.await_args_list]
    assert "PaymentCompleted" in published_types
    assert "OrderConfirmed" in published_types


@pytest.mark.asyncio
async def test_wallet_verify_insufficient_balance_fails_payment():
    """PAY-03: a failed debit must fail the payment, never confirm the order."""
    user_id = uuid.uuid4()
    db, payment, order = _wallet_verify_fixtures(user_id)

    failing_debit = AsyncMock(side_effect=ValidationError("Insufficient balance"))

    with (
        patch("app.modules.wallet.application.wallet_service.debit", new=failing_debit),
        patch("app.shared.events.outbox_service.OutboxService.publish", new=AsyncMock()),
        pytest.raises(PaymentError),
    ):
        await payment_service.verify_payment(
            db,
            payment_id=payment.id,
            authority=payment.authority or "",
            status="OK",
        )

    assert payment.status == PaymentStatus.FAILED
    assert order.status == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_verify_rejects_non_owner():
    """PAY-02: the verify endpoint is restricted to the order owner."""
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    db, payment, _order = _wallet_verify_fixtures(owner_id, amount=100)

    with pytest.raises(NotFoundError):
        await payment_service.verify_payment(
            db,
            payment_id=payment.id,
            authority=payment.authority or "",
            status="OK",
            user_id=attacker_id,
        )


# ── wallet deposit fail-closed ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_wallet_deposit_disabled_in_production():
    """WAL-01: direct deposits must be rejected in production."""
    from app.modules.wallet.api.routes import deposit
    from app.modules.wallet.schemas.wallet import WalletDepositRequest

    production_settings = SimpleNamespace(ENVIRONMENT="production")

    with (
        patch(
            "app.modules.wallet.api.routes.get_settings",
            return_value=production_settings,
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await deposit(
            WalletDepositRequest(amount=100_000),
            user_id=uuid.uuid4(),
            db=MagicMock(),
        )
    assert exc.value.status_code == 403


# ── inventory restock on cancellation ────────────────────────────────────


@pytest.mark.asyncio
async def test_restock_order_releases_committed_stock():
    """INV-01: cancelling an order returns committed stock to available."""
    order_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    item = InventoryItem(
        id=uuid.uuid4(),
        variant_id=variant_id,
        available=0,
        reserved=0,
        committed=3,
    )
    reservation = InventoryReservation(
        id=uuid.uuid4(),
        inventory_item_id=item.id,
        order_id=order_id,
        quantity=3,
        status=ReservationStatus.CONFIRMED,
    )
    order_item = OrderItem(
        order_id=order_id,
        variant_id=variant_id,
        product_name="Test",
        quantity=3,
        unit_price=10_000,
        total_price=30_000,
    )

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalars = AsyncMock(
        side_effect=[
            MagicMock(all=MagicMock(return_value=[reservation])),  # reservations
            MagicMock(all=MagicMock(return_value=[order_item])),  # order items
        ]
    )
    db.scalar = AsyncMock(return_value=item)

    restocked = await inventory_service.restock_order(db, order_id)

    assert restocked == 3
    assert item.available == 3
    assert item.committed == 0
    assert reservation.status == ReservationStatus.RELEASED


# ── stale unpaid-order auto-cancel ───────────────────────────────────────


class _FakeSessionCtx:
    """Minimal async context manager standing in for async_session_factory."""

    def __init__(self, db: MagicMock) -> None:
        self._db = db

    async def __aenter__(self) -> MagicMock:
        return self._db

    async def __aexit__(self, *exc_info) -> None:
        return None


@pytest.mark.asyncio
async def test_stale_pending_orders_are_cancelled_and_restocked():
    """INV-01: unpaid PENDING orders past the TTL are cancelled, stock freed."""
    from app.modules.orders.application import tasks as order_tasks

    stale_order = _make_order(user_id=uuid.uuid4())
    stale_order.created_at = datetime.now(UTC) - timedelta(minutes=120)
    fresh_order = _make_order(user_id=uuid.uuid4())
    fresh_order.created_at = datetime.now(UTC)

    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.scalars = AsyncMock(
        side_effect=[
            MagicMock(all=MagicMock(return_value=[stale_order, fresh_order])),
        ]
    )

    restock = AsyncMock(return_value=2)

    with (
        patch(
            "app.modules.orders.application.tasks.async_session_factory",
            lambda: _FakeSessionCtx(db),
        ),
        patch(
            "app.modules.inventory.application.inventory_service.restock_order",
            new=restock,
        ),
    ):
        result = await order_tasks._cancel_stale_pending_orders_async()

    assert result["status"] == "success"
    assert result["cancelled"] == 1
    assert stale_order.status == OrderStatus.CANCELED
    assert fresh_order.status == OrderStatus.PENDING
    restock.assert_awaited_once_with(db, stale_order.id)
    # A status-history entry is recorded for the auto-cancel
    history_added = [
        c.args[0]
        for c in db.add.call_args_list
        if c.args and c.args[0].__class__.__name__ == "OrderStatusHistory"
    ]
    assert len(history_added) == 1
    assert history_added[0].to_status == OrderStatus.CANCELED.value
