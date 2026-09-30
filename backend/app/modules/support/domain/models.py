"""Customer support ticket domain models."""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ---- Models ----


class SupportTicket(BaseModel):
    """Customer support tickets."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_user_id", "user_id"),
        Index("ix_support_tickets_status", "status"),
        Index("ix_support_tickets_priority", "priority"),
        Index("ix_support_tickets_assigned_to", "assigned_to"),
        Index("ix_support_tickets_ticket_number", "ticket_number"),
        Index("ix_support_tickets_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status_enum", native_enum=False),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority_enum", native_enum=False),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Relationships
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage", back_populates="ticket", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<SupportTicket(id={self.id}, ticket_number={self.ticket_number}, status={self.status})>"  # noqa: E501


class TicketMessage(BaseModel):
    """Messages within a support ticket thread."""

    __tablename__ = "ticket_messages"
    __table_args__ = (
        Index("ix_ticket_messages_ticket_id", "ticket_id"),
        Index("ix_ticket_messages_sender_id", "sender_id"),
        Index("ix_ticket_messages_created_at", "created_at"),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    ticket: Mapped["SupportTicket"] = relationship("SupportTicket", back_populates="messages")
    attachments: Mapped[list["TicketAttachment"]] = relationship(
        "TicketAttachment", back_populates="message", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<TicketMessage(id={self.id}, ticket_id={self.ticket_id})>"


class TicketAttachment(BaseModel):
    """File attachments on ticket messages."""

    __tablename__ = "ticket_attachments"
    __table_args__ = (Index("ix_ticket_attachments_message_id", "message_id"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ticket_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    message: Mapped["TicketMessage"] = relationship("TicketMessage", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<TicketAttachment(id={self.id}, file_name={self.file_name})>"


class ContactMessage(BaseModel):
    """Inbound message submitted through the public "Contact us" form.

    Stored separately from support tickets: the sender may be anonymous
    (the contact page is public), so there is no ``user_id`` requirement.
    """

    __tablename__ = "contact_messages"
    __table_args__ = (
        Index("ix_contact_messages_created_at", "created_at"),
        Index("ix_contact_messages_is_read", "is_read"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ContactMessage(id={self.id}, email={self.email})>"
