"""Newsletter domain models (خبرنامه با تأیید دوعاملی عضویت)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, BaseModel, TimestampMixin


class NewsletterStatus(enum.StrEnum):
    """Lifecycle of a newsletter subscription (double opt-in)."""

    PENDING = "pending"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"


class NewsletterSubscriber(Base, TimestampMixin):
    """One email address on the newsletter list.

    The email address IS the primary key: a subscription's identity is the
    address, re-subscribing updates the same row, and every lifecycle lookup
    (confirm/unsubscribe) resolves the row through a server-computed token
    (HMAC of the address) without a secondary query. Only a ``subscribed``
    row may be mailed campaigns; ``pending`` holds an unconfirmed signup and
    ``unsubscribed`` keeps the row for history while clearing membership.
    """

    __tablename__ = "newsletter_subscribers"
    __table_args__ = (
        Index("ix_newsletter_subscribers_status", "status"),
        Index("ix_newsletter_subscribers_created_at", "created_at"),
    )

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[NewsletterStatus] = mapped_column(
        Enum(NewsletterStatus, name="newsletter_status_enum", native_enum=False),
        default=NewsletterStatus.PENDING,
        nullable=False,
    )
    confirm_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Where the signup came from (footer widget, blog sidebar, ...) so the
    # admin can see which placement converts.
    source: Mapped[str] = mapped_column(
        String(50), default="footer", nullable=False, server_default=text("'footer'")
    )

    def __repr__(self) -> str:
        return f"<NewsletterSubscriber(email={self.email!r}, status='{self.status}')>"


class CampaignStatus(enum.StrEnum):
    """Lifecycle of a newsletter campaign send."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class RecipientStatus(enum.StrEnum):
    """Per-recipient delivery state inside one campaign."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NewsletterCampaign(BaseModel, TimestampMixin):
    """One mailout to the confirmed newsletter list.

    Content is stored as raw HTML + a plain-text fallback; the unsubscribe
    footer (and the per-recipient unsubscribe link) is injected at render
    time by the campaign service, never stored. ``status`` follows
    draft → scheduled → sending → sent/failed and is transitioned only by
    the campaign service (the API never writes ``sending`` directly).
    """

    __tablename__ = "newsletter_campaigns"
    __table_args__ = (
        Index("ix_newsletter_campaigns_status", "status"),
        Index("ix_newsletter_campaigns_scheduled_at", "scheduled_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional preview text rendered as a hidden <div> right after <body>.
    preheader: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(
            CampaignStatus,
            name="newsletter_campaign_status_enum",
            native_enum=False,
        ),
        default=CampaignStatus.DRAFT,
        nullable=False,
        # The column stores member NAMES ("DRAFT"), not values ("draft").
        server_default=text("'DRAFT'::character varying"),
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Snapshot counters kept on the campaign so the admin list never has to
    # aggregate the recipients table. total_recipients counts the recipient
    # rows created at send time (confirmed subscribers minus mid-send
    # unsubscribes, which remove their row entirely).
    total_recipients: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("'0'")
    )
    total_sent: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("'0'")
    )
    total_failed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("'0'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<NewsletterCampaign(id={self.id}, name={self.name!r}, status='{self.status}')>"


class NewsletterCampaignRecipient(BaseModel, TimestampMixin):
    """Per-(campaign, subscriber) delivery record.

    ``subscriber_id`` is the subscriber's primary key — the email address
    itself. The unique pair makes recipient snapshotting idempotent (a
    re-run of the send task cannot duplicate a recipient) and lets the send
    loop page through pending rows with stable keys.
    """

    __tablename__ = "newsletter_campaign_recipients"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "subscriber_id",
            name="uq_newsletter_campaign_recipients_campaign_id_subscriber_id",
        ),
        Index("ix_newsletter_campaign_recipients_subscriber_id", "subscriber_id"),
    )

    # Explicit short constraint names: the naming convention would produce
    # fk_newsletter_campaign_recipients_subscriber_id_newsletter_subscribers
    # (71 chars) and ..._campaign_id_newsletter_campaigns (65), both past
    # PostgreSQL's 63-character identifier limit — the migration cannot run
    # under the convention-generated names.
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "newsletter_campaigns.id",
            ondelete="CASCADE",
            name="fk_newsletter_recipients_campaign_id",
        ),
        nullable=False,
    )
    subscriber_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey(
            "newsletter_subscribers.email",
            ondelete="CASCADE",
            name="fk_newsletter_recipients_subscriber_id",
        ),
        nullable=False,
    )
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(
            RecipientStatus,
            name="newsletter_campaign_recipient_status_enum",
            native_enum=False,
        ),
        default=RecipientStatus.PENDING,
        nullable=False,
        # Same contract as the campaign status above.
        server_default=text("'PENDING'::character varying"),
    )
    # SMTP refusal / transport error for failed rows, truncated to what fits
    # a delivery audit (the full response lives in email_delivery_logs).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def email(self) -> str:
        """The address this row mails — the subscriber primary key itself."""
        return self.subscriber_id

    def __repr__(self) -> str:
        return (
            f"<NewsletterCampaignRecipient(campaign_id={self.campaign_id}, "
            f"subscriber_id={self.subscriber_id!r}, status='{self.status}')>"
        )
