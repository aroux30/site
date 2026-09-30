"""Site settings domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class SiteSetting(BaseModel):
    """Key-value configuration store for runtime site settings."""

    __tablename__ = "site_settings"
    __table_args__ = (
        Index("ix_site_settings_key", "key"),
        Index("ix_site_settings_group", "group"),
        Index("ix_site_settings_is_public", "is_public"),
    )

    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<SiteSetting(id={self.id}, key={self.key})>"


class SiteTheme(BaseModel):
    """A switchable storefront theme (WordPress theme parity, token-based).

    Each row is a named token set (colors, radius, dark-mode default) in the
    exact shape the ``theme`` single type consumes. Activation copies the
    tokens into that single type, so the storefront consumer
    (``lib/theme.ts``) applies them with zero deploy. Builtin rows are the
    factory presets; operators can save their current look as new themes and
    switch between them.
    """

    __tablename__ = "site_themes"
    __table_args__ = (
        Index("ix_site_themes_slug", "slug"),
        Index("ix_site_themes_is_active", "is_active"),
    )

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<SiteTheme(id={self.id}, slug={self.slug}, active={self.is_active})>"


class LocalizationString(BaseModel):
    """One UI string translation (backend i18n catalogue, gap 17c).

    Keys are dotted paths shared with the storefront catalogue
    (``frontend/lib/i18n.ts``): ``common.save``, ``email.order_subject``, …
    One row per (key, locale); the admin UI edits rows and the storefront
    fetches a locale via the public ``/settings/public/i18n`` endpoint with
    the fallback chain ``locale → default_locale site option → key``.
    """

    __tablename__ = "localization_strings"
    __table_args__ = (
        UniqueConstraint("key", "locale", name="uq_localization_strings_key_locale"),
        Index("ix_localization_strings_locale", "locale"),
        Index("ix_localization_strings_group", "group"),
    )

    key: Mapped[str] = mapped_column(String(200), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<LocalizationString(id={self.id}, key={self.key}, locale={self.locale})>"


# ── GDPR data-subject requests ───────────────────────────────────────────────


class PrivacyRequestType(str, enum.Enum):
    """Which GDPR right the subject exercised."""

    EXPORT = "export"
    ERASE = "erase"


class PrivacyRequestStatus(str, enum.Enum):
    """Lifecycle of a data-subject request.

    ``pending`` is the state a customer request rests in until an operator
    acts. ``processing`` marks a claim on the row so a second operator cannot
    run the same erasure twice — erasure is destructive and non-idempotent in
    effect, even if the operation itself is.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    #: Erasure ran but at least one registered source failed. Distinct from
    #: ``completed`` because the subject's data is not actually all gone, and
    #: distinct from ``pending`` because the work was attempted and the
    #: per-source report exists for an operator to act on. Reporting either of
    #: those two would be a lie in one direction or the other.
    PARTIAL = "partial"
    REJECTED = "rejected"


class PrivacyRequest(BaseModel):
    """A data subject's own GDPR request, raised from their account.

    ``PrivacyService.export_user_data`` / ``erase_user_data`` were reachable
    only by an operator typing a UUID, which is not what GDPR asks for: the
    data subject must be able to make the request themselves. This table is
    that queue.

    Two safety properties are encoded here rather than left to route code:

    * ``user_id`` is the *requester* and is the account the work is performed
      on. There is no "target user" column, so no handler can be pointed at
      somebody else's data by a request parameter.
    * The export payload is stored in ``result_payload`` and read back only
      through an authenticated owner-scoped endpoint; there is no static file
      URL to guess. GDPR Article 15 gives the subject a copy "in a commonly
      used form" — the account page it lives in IS that form, so the copy is
      served inline rather than as an unguessable download link. A download
      ticket would add a second credential to leak, and the one-hour expiry
      would expire while the subject is still reading their own page.
    """

    __tablename__ = "privacy_requests"
    __table_args__ = (
        # The customer list and the operator queue both filter on this pair;
        # without it every read is a sequential scan of the whole table.
        Index("ix_privacy_requests_user_id_status", "user_id", "status"),
        # The admin queue's default view is "unhandled first, oldest first".
        Index("ix_privacy_requests_status_created_at", "status", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[PrivacyRequestType] = mapped_column(
        Enum(
            PrivacyRequestType,
            name="privacy_request_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    status: Mapped[PrivacyRequestStatus] = mapped_column(
        Enum(
            PrivacyRequestStatus,
            name="privacy_request_status_enum",
            native_enum=False,
        ),
        default=PrivacyRequestStatus.PENDING,
        nullable=False,
    )

    #: Why the subject is asking, in their own words. Shown to the operator
    #: queue so triage does not have to open a support ticket to know why.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Re-authentication proof. The subject restates their account password at
    #: submit time; only the *outcome* is stored, never the password, so a
    #: dump of this table cannot be replayed as a credential.
    #: ``None`` until confirmed; the account's own verified session is not
    #: enough for an irreversible erase.
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    #: True once the subject confirmed the request with a second factor/OTP in
    #: the account UI. Kept separate from ``verified_at`` because the two are
    #: not the same step: password re-entry proves possession of the account,
    #: the OTP proves the person is at the device that owns it.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    #: Operator-only free text. Never rendered to the subject verbatim — a
    #: rejection reason is often internal ("identity not confirmed by phone").
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Who resolved it, and when. Set together or not at all.
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    #: The completed work product. For an export this is the JSON document the
    #: subject downloads; for an erase it is the action list the service
    #: returns. Never populated for a rejected request.
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    #: Retention deadline for ``result_payload``. An export is a full copy of
    #: the subject's PII sitting in a table an operator can read — it is
    #: deleted on read-after-expiry and by the purge endpoint, so the copy the
    #: GDPR obliged us to make does not become the next breach.
    result_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship("User", lazy="noload")

    def __repr__(self) -> str:
        return (
            f"<PrivacyRequest(id={self.id}, user_id={self.user_id}, "
            f"type={self.type}, status={self.status})>"
        )


# Imported for the type annotation on ``PrivacyRequest.user``; the settings
# module otherwise never touches the users domain.
from app.modules.users.domain.models import User  # noqa: E402
