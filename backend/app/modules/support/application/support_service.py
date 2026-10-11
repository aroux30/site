"""Support application service – ticket management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.modules.support.domain.models import (
    ContactMessage,
    SupportTicket,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Prefix for ticket numbers
_TICKET_PREFIX = "TKT"


class SupportService:
    """Manages support tickets, messages, and ticket lifecycle."""

    # ── Ticket Number Generation ──────────────────────────────────────

    @staticmethod
    async def _generate_ticket_number(db: AsyncSession) -> str:
        """Generate an opaque ticket number independent of existing row counts."""
        return f"{_TICKET_PREFIX}-{uuid.uuid4().hex}"

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
    async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> SupportTicket | None:
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
        user_id: uuid.UUID | None = None,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        """Return paginated tickets, optionally filtered by user/status/priority.

        ``search`` matches the ticket number or the subject (server-side —
        the old admin page filtered only the current page in the browser,
        so a ticket on page 2 was unfindable).
        """
        base = select(SupportTicket)
        count_base = select(func.count()).select_from(SupportTicket)

        if user_id is not None:
            base = base.where(SupportTicket.user_id == user_id)
            count_base = count_base.where(SupportTicket.user_id == user_id)

        if status is not None:
            base = base.where(SupportTicket.status == status)
            count_base = count_base.where(SupportTicket.status == status)

        if priority is not None:
            base = base.where(SupportTicket.priority == priority)
            count_base = count_base.where(SupportTicket.priority == priority)

        if search and search.strip():
            term = f"%{search.strip()}%"
            condition = SupportTicket.ticket_number.ilike(term) | SupportTicket.subject.ilike(term)
            base = base.where(condition)
            count_base = count_base.where(condition)

        total = (await db.execute(count_base)).scalar_one()
        stmt = base.order_by(SupportTicket.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def admin_ticket_stats(db: AsyncSession) -> dict[str, Any]:
        """Whole-table per-status counts + urgency/ownership extras.

        One GROUP BY per dimension (not one query per status): the admin
        board renders every column header at once. Zero-fill the enum so the
        UI receives every status even when no ticket carries it.
        """
        status_rows = await db.execute(
            select(SupportTicket.status, func.count(SupportTicket.id)).group_by(
                SupportTicket.status
            )
        )
        by_status = {status.value: int(count) for status, count in status_rows}

        urgent_open = (
            await db.execute(
                select(func.count())
                .select_from(SupportTicket)
                .where(
                    SupportTicket.priority == TicketPriority.URGENT,
                    SupportTicket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
                )
            )
        ).scalar_one()
        unassigned = (
            await db.execute(
                select(func.count())
                .select_from(SupportTicket)
                .where(
                    SupportTicket.assigned_to.is_(None),
                    SupportTicket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
                )
            )
        ).scalar_one()

        statuses = [
            {"status": member.value, "count": by_status.get(member.value, 0)}
            for member in TicketStatus
        ]
        return {
            "by_status": statuses,
            "total_tickets": sum(entry["count"] for entry in statuses),
            "urgent_open": int(urgent_open),
            "unassigned": int(unassigned),
        }

    @staticmethod
    async def enrich_admin_ticket_rows(db: AsyncSession, tickets: list[SupportTicket]) -> list[dict[str, Any]]:
        """Attach customer identity and thread stats to admin list rows.

        The admin list previously showed a raw user UUID and nothing else —
        an operator could not tell who was writing. Two batched queries (no
        N+1): one for the users' phones + profiles, one for per-ticket
        message counts + the newest message preview.
        """
        from app.modules.users.domain.models import User, UserProfile

        if not tickets:
            return []

        ticket_ids = [t.id for t in tickets]
        user_ids = {t.user_id for t in tickets}

        # Customer identity: phone from users, name from the joined profile
        # (names do NOT live on the user row — the same bug the orders admin
        # had: reading user.first_name returned None forever).
        user_rows = await db.execute(
            select(User.id, User.phone, UserProfile.first_name, UserProfile.last_name, UserProfile.display_name)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.id.in_(user_ids))
        )
        identity: dict[uuid.UUID, tuple[str | None, str | None]] = {}
        for uid, phone, first, last, display in user_rows:
            name = " ".join(n for n in (first, last) if n).strip() or display or None
            identity[uid] = (name, phone)

        # Thread stats: count per ticket + newest message per ticket.
        counts_rows = await db.execute(
            select(TicketMessage.ticket_id, func.count(TicketMessage.id))
            .where(TicketMessage.ticket_id.in_(ticket_ids))
            .group_by(TicketMessage.ticket_id)
        )
        counts = {tid: int(c) for tid, c in counts_rows}

        # Newest message per ticket: window function keeps it to one query.
        from sqlalchemy import desc

        newest_rows = await db.execute(
            select(TicketMessage.ticket_id, TicketMessage.body, TicketMessage.created_at)
            .where(TicketMessage.ticket_id.in_(ticket_ids))
            .order_by(TicketMessage.ticket_id, desc(TicketMessage.created_at))
            .distinct(TicketMessage.ticket_id)
        )
        newest: dict[uuid.UUID, tuple[str, Any]] = {}
        for tid, body, created in newest_rows:
            newest[tid] = (body, created)

        enriched: list[dict[str, Any]] = []
        for ticket in tickets:
            name, phone = identity.get(ticket.user_id, (None, None))
            last = newest.get(ticket.id)
            enriched.append(
                {
                    "id": ticket.id,
                    "user_id": ticket.user_id,
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "assigned_to": ticket.assigned_to,
                    "ticket_number": ticket.ticket_number,
                    "created_at": ticket.created_at,
                    "updated_at": ticket.updated_at,
                    "customer_name": name,
                    "customer_phone": phone,
                    "messages_count": counts.get(ticket.id, 0),
                    "last_message_preview": (last[0][:120] if last and last[0] else None),
                    "last_message_at": last[1] if last else None,
                }
            )
        return enriched

    # ── Public Contact Form ───────────────────────────────────────────

    @staticmethod
    async def create_contact_message(
        db: AsyncSession,
        *,
        name: str,
        subject: str,
        message: str,
    ) -> ContactMessage:
        """Persist a message from the public "Contact us" form.

        The form is unauthenticated, so no user account is required; the
        stored message is reviewed from the admin back office.
        """
        contact = ContactMessage(
            name=name.strip(),
            subject=subject.strip(),
            message=message.strip(),
            is_read=False,
        )
        db.add(contact)
        await db.flush()

        await logger.ainfo(
            "contact_message_created",
            contact_id=str(contact.id),
        )
        return contact
