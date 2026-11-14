"""Live-chat domain models.

Ports the WordPress "N8n Custom Chat Widget" plugin (v6.5.5) into the modular
monolith. Three tables mirror the plugin's three wp_ tables:

* ``chat_sessions``   ← ``n8n_chat_sessions`` (per-conversation identity + form)
* ``chat_messages``   ← ``n8n_chat_history``  (the message log)
* ``chat_presence``   ← ``n8n_chat_online``   (5s heartbeat / online monitor)

Enums are stored as NAMES (``native_enum=False``), the repo-wide contract.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, BaseModel, TimestampMixin


class ChatRole(enum.StrEnum):
    """Who authored a message.

    ``USER``   — the visitor (guest or logged-in customer).
    ``AI``     — the n8n-powered bot reply.
    ``ADMIN``  — a human support agent (in the live console or via Telegram).
    ``SYSTEM`` — an automatic notice (hand-off confirmation, etc.).
    """

    USER = "user"
    AI = "ai"
    ADMIN = "admin"
    SYSTEM = "system"


class ChatSession(BaseModel):
    """One conversation thread (guest or customer).

    ``session_key`` is a client-generated opaque id (the plugin's ``session_id``)
    that survives across page loads via localStorage. ``handoff_until`` mirrors
    the plugin's ``n8n_handoff_<sid>`` option: while it is in the future the AI
    is muted and a human owns the thread.
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_session_key", "session_key"),
        Index("ix_chat_sessions_user_id", "user_id"),
        Index("ix_chat_sessions_last_activity_at", "last_activity_at"),
        UniqueConstraint("session_key", name="uq_chat_sessions_session_key"),
    )

    session_key: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    user_email: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    user_phone: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    #: The pre-chat form values, keyed by field key (the plugin's ``user_data``).
    user_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    #: Telegram forum-topic id once a human hand-off opens a topic for this thread.
    tg_topic_id: Mapped[int | None] = mapped_column(nullable=True)
    #: While ``now() < handoff_until`` the AI is muted (plugin parity).
    handoff_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, key={self.session_key!r})>"


class ChatMessage(Base, TimestampMixin):
    """A single message in a chat thread.

    Uses a **bigint** primary key rather than the shared UUID ``BaseModel`` id:
    the whole client protocol is ``id > last_id`` polling (the plugin's
    ``n8n_chat_history`` was an AUTO_INCREMENT bigint), and a UUID cannot be
    ordered or compared that way. The id is monotonic, so "messages since" is a
    single indexed range scan.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
        Index("ix_chat_messages_role", "role"),
        Index("ix_chat_messages_is_read", "is_read"),
        Index("ix_chat_messages_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[ChatRole] = mapped_column(
        Enum(ChatRole, name="chat_role_enum", native_enum=False),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: Display name for an admin/Telegram sender ("پشتیبان|@username" in the
    #: plugin; stored verbatim here and split client-side).
    sender_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role})>"


class ChatPresence(BaseModel):
    """A live heartbeat row for the online-users monitor.

    One row per (session, browser tab) — the plugin appended ``|<tab_id>`` to the
    session id for the same reason: a visitor with three tabs open is one person
    but three "online" surfaces, grouped by name in the admin view.
    """

    __tablename__ = "chat_presence"
    __table_args__ = (
        Index("ix_chat_presence_session_key", "session_key"),
        Index("ix_chat_presence_last_seen", "last_seen"),
        UniqueConstraint("session_key", name="uq_chat_presence_session_key"),
    )

    #: ``<session_key>|<tab_id>`` — unique per tab, grouped by name downstream.
    session_key: Mapped[str] = mapped_column(String(140), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    user_ip: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    page_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    page_title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ChatPresence(key={self.session_key!r})>"
