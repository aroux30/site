"""Support application service – ticket management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.support.domain.models import (
    SupportTicket,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Auto-incrementing counter prefix for ticket numbers
_TICKET_PREFIX = "TKT"


class SupportService:
    """Manages support tickets, messages, and ticket lifecycle."""

    # ── Ticket Number Generation ──────────────────────────────────────

    @staticmethod
    async def _generate_ticket_number(db: AsyncSession) -> str:
        """Generate a unique auto-incrementing ticket number."""
        stmt = select(func.count()).select_from(SupportTicket)
        total = (await db.execute(stmt)).scalar_one()
        number = total + 1
        return f"{_TICKET_PREFIX}-{number:06d}"

    # ── Create Ticket ─────────────────────────────────────────────────

    @staticmethod
    async def create_ticket(
        db: AsyncSession,
        user_id: uuid.UUID,
        subject: str,
        body: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
    ) -> SupportTicket:
        """Create a new support ticket with an initial message."""
        ticket_number = await SupportService._generate_ticket_number(db)

        ticket = SupportTicket(
            user_id=user_id,
            subject=subject,
            status=TicketStatus.OPEN,
            priority=priority,
            ticket_number=ticket_number,
        )
        db.add(ticket)
        await db.flush()

        # Add the initial message
        message = TicketMessage(
            ticket_id=ticket.id,
            sender_id=user_id,
            body=body,
            is_staff=False,
        )
        db.add(message)
        await db.flush()

        await logger.ainfo(
            "ticket_created",
            ticket_id=str(ticket.id),
            ticket_number=ticket_number,
            user_id=str(user_id),
        )
        return ticket

    # ── Add Message ───────────────────────────────────────────────────

    @staticmethod
    async def add_message(
        db: AsyncSession,
        ticket_id: uuid.UUID,
        sender_id: uuid.UUID,
        body: str,
        is_staff: bool = False,
    ) -> TicketMessage:
        """Add a message to an existing ticket."""
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        result = await db.execute(stmt)
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")

        if ticket.status == TicketStatus.CLOSED:
            raise ValueError("Cannot add messages to a closed ticket.")

        message = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            body=body,
            is_staff=is_staff,
        )
        db.add(message)

        # If staff replies to an open ticket, move to in_progress
        if is_staff and ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.IN_PROGRESS

        # If customer replies to a waiting ticket, move to in_progress
        if not is_staff and ticket.status == TicketStatus.WAITING:
            ticket.status = TicketStatus.IN_PROGRESS

        await db.flush()
        await logger.ainfo(
            "ticket_message_added",
            ticket_id=str(ticket_id),
            message_id=str(message.id),
            is_staff=is_staff,
        )
        return message

    # ── Close / Reopen ────────────────────────────────────────────────

    @staticmethod
    async def close_ticket(
        db: AsyncSession, ticket_id: uuid.UUID, user_id: uuid.UUID
    ) -> SupportTicket:
        """Close a support ticket."""
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        result = await db.execute(stmt)
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")

        if ticket.status == TicketStatus.CLOSED:
            raise ValueError("Ticket is already closed.")

        ticket.status = TicketStatus.CLOSED
        await db.flush()
        await logger.ainfo(
            "ticket_closed",
            ticket_id=str(ticket_id),
            closed_by=str(user_id),
        )
        return ticket

    @staticmethod
    async def reopen_ticket(
        db: AsyncSession, ticket_id: uuid.UUID, user_id: uuid.UUID
    ) -> SupportTicket:
        """Reopen a closed support ticket."""
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        result = await db.execute(stmt)
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")

        if ticket.status != TicketStatus.CLOSED:
            raise ValueError("Ticket is not closed.")

        ticket.status = TicketStatus.OPEN
        await db.flush()
        await logger.ainfo(
            "ticket_reopened",
            ticket_id=str(ticket_id),
            reopened_by=str(user_id),
        )
        return ticket

    # ── Update (Admin) ────────────────────────────────────────────────

    @staticmethod
    async def update_ticket(
        db: AsyncSession, ticket_id: uuid.UUID, **updates: Any
    ) -> SupportTicket:
        """Update ticket fields (priority, status, assignment)."""
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        result = await db.execute(stmt)
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")

        clean = {k: v for k, v in updates.items() if v is not None}
        for key, value in clean.items():
            setattr(ticket, key, value)

        await db.flush()
        await logger.ainfo("ticket_updated", ticket_id=str(ticket_id), updates=clean)
        return ticket

    # ── Queries ───────────────────────────────────────────────────────

    @staticmethod
    async def get_ticket(
        db: AsyncSession, ticket_id: uuid.UUID
    ) -> Optional[SupportTicket]:
        """Get a ticket with its messages."""
        stmt = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(SupportTicket.id == ticket_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_tickets(
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        status: Optional[TicketStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        """Return paginated tickets, optionally filtered by user and status."""
        base = select(SupportTicket)
        count_base = select(func.count()).select_from(SupportTicket)

        if user_id is not None:
            base = base.where(SupportTicket.user_id == user_id)
            count_base = count_base.where(SupportTicket.user_id == user_id)

        if status is not None:
            base = base.where(SupportTicket.status == status)
            count_base = count_base.where(SupportTicket.status == status)

        total = (await db.execute(count_base)).scalar_one()
        stmt = base.order_by(SupportTicket.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total
