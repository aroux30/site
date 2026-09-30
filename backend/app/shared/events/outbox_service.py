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
from sqlalchemy import and_, func, or_, select, update

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

    async def list_by_status(
        db: AsyncSession,
        status: OutboxStatus,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[OutboxMessage], int]:
        """Newest-first page of messages in *status*, plus the total count.

        The admin dead-letter screen needs the count as well as the page: an
        operator asking "how much is broken?" wants the number, and a page of
        50 rows cannot answer it.
        """
        count_stmt = select(func.count()).select_from(OutboxMessage).where(
            OutboxMessage.status == status
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.status == status)
            .order_by(OutboxMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def requeue(
        db: AsyncSession,
        message_id: uuid.UUID,
        *,
        reset_retries: bool = True,
    ) -> OutboxMessage | None:
        """Put a DEAD_LETTER (or FAILED) message back on the queue.

        Without this a dead letter is a write-only state: the message is in a
        terminal condition no operator can see or act on, so the event is lost.
        ``reset_retries`` is the default because the usual reason to replay is
        that the *cause* was fixed — a handler registered late, a downstream
        service restored — and carrying the exhausted counter forward would
        dead-letter it again on the first new failure.

        Returns None when the message does not exist, or is still in flight
        (PENDING/CLAIMED/PROCESSED), which must not be replayed.
        """
        stmt = select(OutboxMessage).where(OutboxMessage.id == message_id).with_for_update()
        msg = (await db.execute(stmt)).scalar_one_or_none()
        if msg is None:
            return None

        replayable = {OutboxStatus.DEAD_LETTER, OutboxStatus.FAILED}
        if msg.status not in replayable:
            raise ValueError(
                f"message is {msg.status.value}, which is not replayable"
            )

        msg.status = OutboxStatus.PENDING
        msg.available_at = datetime.now(UTC)
        msg.locked_at = None
        msg.worker_id = None
        msg.processed_at = None
        if reset_retries:
            msg.retry_count = 0

        await db.commit()
        await db.refresh(msg)
        await logger.awarning(
            "outbox_message_requeued",
            message_id=str(message_id),
            event_type=msg.event_type,
            previous_status=OutboxStatus.DEAD_LETTER.value,
        )
        return msg

    async def purge(
        db: AsyncSession,
        message_id: uuid.UUID,
    ) -> bool:
        """Delete a dead letter for good. Returns False when absent."""
        stmt = select(OutboxMessage).where(OutboxMessage.id == message_id)
        msg = (await db.execute(stmt)).scalar_one_or_none()
        if msg is None:
            return False
        await db.delete(msg)
        await db.commit()
        await logger.awarning("outbox_message_purged", message_id=str(message_id))
        return True
