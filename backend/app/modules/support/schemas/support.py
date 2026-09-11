"""Pydantic v2 schemas for the support module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.support.domain.models import TicketPriority, TicketStatus

# ── Ticket ────────────────────────────────────────────────────────────────


class TicketCreate(BaseModel):
    """Payload to create a new support ticket."""

    subject: str = Field(..., max_length=500)
    body: str = Field(..., min_length=1)
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketResponse(BaseModel):
    """Single support ticket response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    subject: str
    status: TicketStatus
    priority: TicketPriority
    assigned_to: uuid.UUID | None = None
    ticket_number: str
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(BaseModel):
    """Detailed ticket response with messages."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    subject: str
    status: TicketStatus
    priority: TicketPriority
    assigned_to: uuid.UUID | None = None
    ticket_number: str
    messages: list[TicketMessageResponse]
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    """Paginated ticket list."""

    items: list[TicketResponse]
    total: int


class TicketUpdateRequest(BaseModel):
    """Payload to update a ticket (admin)."""

    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: uuid.UUID | None = None


# ── Messages ──────────────────────────────────────────────────────────────


class TicketMessageCreate(BaseModel):
    """Payload to add a message to a ticket."""

    body: str = Field(..., min_length=1)


class TicketMessageResponse(BaseModel):
    """Single ticket message response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    is_staff: bool
    created_at: datetime


# ── Attachments ───────────────────────────────────────────────────────────


class TicketAttachmentResponse(BaseModel):
    """Single ticket attachment response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    file_url: str
    file_name: str
    file_size: int
    created_at: datetime


# Rebuild forward refs
TicketDetailResponse.model_rebuild()
