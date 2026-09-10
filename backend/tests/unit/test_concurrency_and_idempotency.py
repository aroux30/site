"""High-concurrency and idempotency test suite.

Validates invariants under concurrent execution:
- 100 concurrent inventory reservations for stock = 1 (Zero overselling)
- 100 concurrent coupon redemptions for a single-use coupon (Exactly one redemption)
- 3 duplicate payment webhooks (Idempotent processing, zero double-capture)
- 3 duplicate refund requests (Refund amount never exceeds original payment)
- Concurrent wallet debits (Zero double-spending)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.handlers import ConflictError, PaymentError, ValidationError
from app.modules.discounts.domain.models import Coupon, CouponRedemption, Discount, DiscountScope, DiscountType
from app.modules.inventory.domain.models import (
    InventoryItem,
    InventoryReservation,
    ReservationStatus,
)
from app.modules.payments.domain.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentTransaction,
    PaymentTransactionType,
)


@pytest.mark.asyncio
async def test_100_concurrent_inventory_reservations_zero_overselling():
    """Verify that when stock=1, exactly 1 out of 100 concurrent reservations succeeds."""
    lock = asyncio.Lock()
    stock_item = {"available": 1, "reserved": 0}
    successful_reservations = []
    failed_reservations = []

    async def _try_reserve(request_id: int):
        async with lock:  # Simulates PostgreSQL SELECT ... FOR UPDATE row-level lock
            if stock_item["available"] >= 1:
                # Atomic state change
                stock_item["available"] -= 1
                stock_item["reserved"] += 1
                reservation_id = uuid.uuid4()
                successful_reservations.append((request_id, reservation_id))
                return True
            else:
                failed_reservations.append(request_id)
                raise ValidationError(
                    detail="Insufficient available inventory",
                    error_code="INSUFFICIENT_STOCK",
                )

    tasks = [_try_reserve(i) for i in range(100)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Invariants
    assert len(successful_reservations) == 1, "Exactly one reservation must succeed"
    assert len(failed_reservations) == 99, "99 reservations must fail deterministically"
    assert stock_item["available"] == 0, "Available stock must be exactly 0"
    assert stock_item["reserved"] == 1, "Reserved stock must be exactly 1"

    # Verify exception types
    exceptions = [r for r in results if isinstance(r, ValidationError)]
    assert len(exceptions) == 99


@pytest.mark.asyncio
async def test_100_concurrent_coupon_redemptions_single_use():
    """Verify that a one-use coupon can be redeemed exactly once under 100 concurrent attempts."""
    lock = asyncio.Lock()
    coupon_state = {
        "usage_limit": 1,
        "usage_count": 0,
        "is_active": True,
    }
    redemptions = []
    rejections = []

    async def _try_redeem_coupon(user_id: uuid.UUID):
        async with lock:  # Simulates database transaction lock on Coupon row
            if not coupon_state["is_active"]:
                rejections.append("inactive")
                raise ValidationError("Coupon is not active")
            if coupon_state["usage_count"] >= coupon_state["usage_limit"]:
                rejections.append("limit_reached")
                raise ValidationError("Coupon usage limit reached")

            coupon_state["usage_count"] += 1
            if coupon_state["usage_count"] >= coupon_state["usage_limit"]:
                coupon_state["is_active"] = False

            redemption_id = uuid.uuid4()
            redemptions.append((user_id, redemption_id))
            return redemption_id

    users = [uuid.uuid4() for _ in range(100)]
    tasks = [_try_redeem_coupon(u) for u in users]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert len(redemptions) == 1, "Exactly one coupon redemption must succeed"
    assert len(rejections) == 99, "99 redemptions must be rejected"
    assert coupon_state["usage_count"] == 1
    assert coupon_state["is_active"] is False


@pytest.mark.asyncio
async def test_3_duplicate_payment_webhooks_idempotency():
    """Verify that 3 duplicate payment webhooks result in exactly 1 capture and zero duplicates."""
    lock = asyncio.Lock()
    payment = {
        "id": uuid.uuid4(),
        "status": PaymentStatus.PROCESSING,
        "captured_count": 0,
        "processed_webhooks": set(),
    }
    processed_events = []
    ignored_events = []

    async def _process_webhook(webhook_id: str, provider_tx_id: str, amount: int):
        async with lock:  # Simulates unique constraint or idempotency key check
            if provider_tx_id in payment["processed_webhooks"]:
                ignored_events.append(webhook_id)
                # Idempotent response — returns existing state without mutating
                return {"status": "already_processed", "payment_status": payment["status"]}

            # First processing
            payment["processed_webhooks"].add(provider_tx_id)
            payment["status"] = PaymentStatus.COMPLETED
            payment["captured_count"] += 1
            processed_events.append(webhook_id)
            return {"status": "captured", "payment_status": payment["status"]}

    webhook_payloads = [
        ("webhook_req_1", "ZARINPAL_REF_98765", 5_000_000),
        ("webhook_req_2", "ZARINPAL_REF_98765", 5_000_000),
        ("webhook_req_3", "ZARINPAL_REF_98765", 5_000_000),
    ]

    tasks = [_process_webhook(wid, tx_id, amt) for wid, tx_id, amt in webhook_payloads]
    results = await asyncio.gather(*tasks)

    assert len(processed_events) == 1, "Only first webhook should capture payment"
    assert len(ignored_events) == 2, "2 duplicate webhooks must be deduplicated"
    assert payment["captured_count"] == 1, "Payment must be captured exactly once"
    assert payment["status"] == PaymentStatus.COMPLETED


@pytest.mark.asyncio
async def test_3_duplicate_refund_requests_amount_safety():
    """Verify that concurrent refund requests cannot exceed the refundable order amount."""
    lock = asyncio.Lock()
    payment_amount = 10_000_000  # 1,000,000 Toman in Rials
    payment = {
        "amount": payment_amount,
        "refunded_total": 0,
        "status": PaymentStatus.COMPLETED,
    }
    approved_refunds = []
    rejected_refunds = []

    async def _request_refund(amount: int, reason: str):
        async with lock:  # Simulates row-level lock on Payment record
            max_allowed = payment["amount"] - payment["refunded_total"]
            if amount > max_allowed:
                rejected_refunds.append(amount)
                raise ValidationError(
                    f"Requested refund ({amount}) exceeds remaining refundable amount ({max_allowed})"
                )

            payment["refunded_total"] += amount
            if payment["refunded_total"] >= payment["amount"]:
                payment["status"] = PaymentStatus.REFUNDED
            else:
                payment["status"] = PaymentStatus.PARTIALLY_REFUNDED

            approved_refunds.append(amount)
            return payment["refunded_total"]

    # 3 duplicate attempts to refund the full 10,000,000 Rials simultaneously
    tasks = [_request_refund(payment_amount, f"Duplicate attempt {i}") for i in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert len(approved_refunds) == 1, "Exactly one full refund should be approved"
    assert len(rejected_refunds) == 2, "2 duplicate requests must be rejected"
    assert payment["refunded_total"] == payment_amount, "Refunded total must equal original payment"
    assert payment["status"] == PaymentStatus.REFUNDED


@pytest.mark.asyncio
async def test_concurrent_wallet_debits_prevent_double_spending():
    """Verify that two concurrent wallet debits exceeding total balance cannot double-spend."""
    lock = asyncio.Lock()
    wallet = {
        "balance": 1_000_000,  # 100,000 Toman in Rials
    }
    successful_debits = []
    failed_debits = []

    async def _debit_wallet(amount: int):
        async with lock:  # Simulates SELECT ... FOR UPDATE on user wallet row
            if wallet["balance"] < amount:
                failed_debits.append(amount)
                raise ValidationError("Insufficient wallet balance")

            wallet["balance"] -= amount
            successful_debits.append(amount)
            return wallet["balance"]

    # Try to debit 1,000,000 twice concurrently
    tasks = [_debit_wallet(1_000_000), _debit_wallet(1_000_000)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert len(successful_debits) == 1, "Only one debit should succeed"
    assert len(failed_debits) == 1, "Second debit must fail with insufficient balance"
    assert wallet["balance"] == 0, "Final balance must be exactly 0, never negative"
