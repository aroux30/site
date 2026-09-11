"""Transactional Outbox application service.

Provides transactional enqueueing and concurrent claiming of outbox events
using PostgreSQL's SELECT FOR UPDATE SKIP LOCKED.
"""

from __future__ import annotations

import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import and_, or_, select, update

from app.shared.events.outbox_models import OutboxMessage, OutboxStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OutboxService:
    """Handles publishing and dispatching outbox messages."""

    @staticmethod
    async def publish(
        db: AsyncSession,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        causation_id: str | None = None,
        available_at: datetime | None = None,
    ) -> OutboxMessage:
        """Atomically append an event to the outbox within caller's transaction."""
        now = datetime.now(UTC)
        message = OutboxMessage(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
            status=OutboxStatus.PENDING,
            available_at=available_at or now,
        )
        db.add(message)
        await db.flush()
        await logger.adebug(
            "outbox_message_enqueued",
            message_id=str(message.id),
            event_type=event_type,
            aggregate=f"{aggregate_type}:{aggregate_id}",
        )
        return message

    @staticmethod
    async def claim_batch(
        db: AsyncSession,
        batch_size: int = 50,
        worker_id: str | None = None,
        lease_timeout_seconds: int = 300,
    ) -> list[OutboxMessage]:
        """Claim a batch of pending/failed messages using SELECT FOR UPDATE SKIP LOCKED.

        Includes messages stuck in PROCESSING whose lease has expired (worker crash recovery).
        Guarantees zero contention between concurrent worker processes.
        """
        now = datetime.now(UTC)
        lease_cutoff = now - timedelta(seconds=lease_timeout_seconds)
        resolved_worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

        # Claim messages that are either PENDING, FAILED with retries remaining,
        # OR PROCESSING with expired lease (worker crashed/timed out)
        stmt = (
            select(OutboxMessage)
            .where(
                or_(
                    and_(
                        OutboxMessage.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                        OutboxMessage.available_at <= now,
                    ),
                    and_(
                        OutboxMessage.status == OutboxStatus.PROCESSING,
                        OutboxMessage.locked_at <= lease_cutoff,
                    ),
                ),
                OutboxMessage.retry_count < OutboxMessage.max_retries,
            )
            .order_by(OutboxMessage.available_at.asc(), OutboxMessage.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        messages = list(result.scalars().all())

        for msg in messages:
            msg.status = OutboxStatus.PROCESSING
            msg.locked_at = now
            msg.worker_id = resolved_worker_id

        await db.flush()
        return messages

    @staticmethod
    async def mark_processed(
        db: AsyncSession,
        message_id: uuid.UUID,
    ) -> None:
        """Mark an outbox message as successfully processed."""
        now = datetime.now(UTC)
        stmt = (
            update(OutboxMessage)
            .where(OutboxMessage.id == message_id)
            .values(
                status=OutboxStatus.PROCESSED,
                processed_at=now,
                locked_at=None,
            )
        )
        await db.execute(stmt)
        await logger.ainfo("outbox_message_processed", message_id=str(message_id))

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        message_id: uuid.UUID,
        error: str,
        backoff_seconds: int = 60,
    ) -> None:
        """Record a failure on an outbox message, schedule retry or send to DEAD_LETTER."""
        now = datetime.now(UTC)
        stmt = select(OutboxMessage).where(OutboxMessage.id == message_id).with_for_update()
        result = await db.execute(stmt)
        msg = result.scalar_one_or_none()

        if not msg:
            return

        msg.retry_count += 1
        msg.last_error = error[:2000]
        msg.locked_at = None

        if msg.retry_count >= msg.max_retries:
            msg.status = OutboxStatus.DEAD_LETTER
            await logger.aerror(
                "outbox_message_dead_letter",
                message_id=str(message_id),
                retry_count=msg.retry_count,
                error=error,
            )
        else:
            msg.status = OutboxStatus.FAILED
            # Exponential backoff: base_seconds * (2 ** retry_count)
            delay = backoff_seconds * (2 ** (msg.retry_count - 1))
            msg.available_at = now + timedelta(seconds=min(delay, 3600))
            await logger.awarning(
                "outbox_message_retry_scheduled",
                message_id=str(message_id),
                retry_count=msg.retry_count,
                retry_at=msg.available_at.isoformat(),
            )

        await db.flush()
