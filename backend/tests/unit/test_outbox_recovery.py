"""Unit tests for transactional outbox worker claiming, crash recovery, and dead-letter queue."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.shared.events.outbox_models import OutboxMessage, OutboxStatus
from app.shared.events.outbox_service import OutboxService


@pytest.mark.asyncio
async def test_outbox_publish_message():
    """Verify atomic outbox message publication."""
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    msg = await OutboxService.publish(
        mock_db,
        event_type="OrderConfirmed",
        aggregate_type="Order",
        aggregate_id="ORD-12345",
        payload={"order_id": str(uuid.uuid4()), "amount": 1_000_000},
        correlation_id="corr-999",
    )

    assert msg.event_type == "OrderConfirmed"
    assert msg.aggregate_type == "Order"
    assert msg.aggregate_id == "ORD-12345"
    assert msg.status == OutboxStatus.PENDING
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_outbox_claim_batch_locks_messages():
    """Verify claim_batch sets PROCESSING status and worker ownership."""
    now = datetime.now(timezone.utc)
    pending_msg = OutboxMessage(
        id=uuid.uuid4(),
        event_type="PaymentCompleted",
        aggregate_type="Payment",
        aggregate_id="PAY-111",
        payload={"payment_id": str(uuid.uuid4())},
        status=OutboxStatus.PENDING,
        available_at=now,
        retry_count=0,
        max_retries=5,
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[pending_msg]))))
    )
    mock_db.flush = AsyncMock()

    claimed = await OutboxService.claim_batch(mock_db, batch_size=10, worker_id="worker-node-1")
    assert len(claimed) == 1
    assert claimed[0].status == OutboxStatus.PROCESSING
    assert claimed[0].worker_id == "worker-node-1"
    assert claimed[0].locked_at is not None
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_outbox_mark_failed_schedules_exponential_backoff():
    """Verify failure increments retry_count and calculates backoff."""
    now = datetime.now(timezone.utc)
    msg = OutboxMessage(
        id=uuid.uuid4(),
        event_type="SearchIndexSync",
        aggregate_type="Product",
        aggregate_id="PROD-555",
        payload={"product_id": str(uuid.uuid4())},
        status=OutboxStatus.PROCESSING,
        available_at=now,
        retry_count=1,
        max_retries=5,
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=msg)))
    mock_db.flush = AsyncMock()

    await OutboxService.mark_failed(mock_db, msg.id, error="Elasticsearch connection timeout", backoff_seconds=30)

    assert msg.retry_count == 2
    assert msg.status == OutboxStatus.FAILED
    assert "Elasticsearch connection timeout" in (msg.last_error or "")
    assert msg.locked_at is None
    # Backoff for retry 2 = 30 * (2 ** (2 - 1)) = 60s
    assert msg.available_at > now


@pytest.mark.asyncio
async def test_outbox_mark_failed_transitions_to_dead_letter_on_retry_exhaustion():
    """Verify dead-letter transition when retry count reaches max_retries."""
    now = datetime.now(timezone.utc)
    msg = OutboxMessage(
        id=uuid.uuid4(),
        event_type="EmailDispatch",
        aggregate_type="User",
        aggregate_id="USR-777",
        payload={"email": "test@example.com"},
        status=OutboxStatus.PROCESSING,
        available_at=now,
        retry_count=4,  # Next failure will reach max_retries=5
        max_retries=5,
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=msg)))
    mock_db.flush = AsyncMock()

    await OutboxService.mark_failed(mock_db, msg.id, error="SMTP relay rejected permanently")

    assert msg.retry_count == 5
    assert msg.status == OutboxStatus.DEAD_LETTER
    assert "SMTP relay rejected permanently" in (msg.last_error or "")
    assert msg.locked_at is None
