"""User domain models."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.rbac.domain.models import UserRole


class User(BaseModel):
    """Platform user account."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_phone", "phone"),
        Index("ix_users_email", "email"),
        Index("ix_users_is_active", "is_active"),
        # Soft-delete lookup index; created by migration c2d3e4f5a6b7.
        Index("ix_users_deleted_at", "deleted_at"),
        # Author-archive slugs; created by migration a1b2c3d4e5f6.
        Index("ix_users_author_slug", "author_slug"),
    )

    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Public identity for author archives (/author/<slug>). Nullable: a user
    # created before this column has none, and a null slug simply means "no
    # public archive yet" — it must not be derived on read, because a
    # display-name edit would then change an already-published URL.
    author_slug: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # TOTP MFA: secret is stored while enrollment is pending; enforcement
    # happens only once totp_enabled is True (set after a successful code
    # confirmation, so a half-finished setup can never lock the user out).
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile", back_populates="user", uselist=False, lazy="joined"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", lazy="select"
    )
    addresses: Mapped[list["Address"]] = relationship(
        "Address", back_populates="user", lazy="select"
    )
    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, phone={self.phone})>"


class UserProfile(BaseModel):
    """Extended user profile information."""

    __tablename__ = "user_profiles"
    __table_args__ = (Index("ix_user_profiles_national_code", "national_code"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    national_code: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # ── B2B / مالیات تکلیفی (tax engine v1, additive) ────────────────────
    # Business buyers with a registered tax-exemption certificate are subject
    # to withholding rules instead of VAT at checkout.
    is_b2b: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_exemption_certificate_no: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, user_id={self.user_id})>"


class UserSession(BaseModel):
    """User authentication sessions for token management."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_refresh_token", "refresh_token"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    refresh_token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id})>"


class OTPRequest(BaseModel):
    """One-time password requests for phone verification."""

    __tablename__ = "otp_requests"
    __table_args__ = (
        Index("ix_otp_requests_phone_purpose", "phone", "purpose"),
        Index("ix_otp_requests_expires_at", "expires_at"),
    )

    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<OTPRequest(id={self.id}, phone={self.phone}, purpose={self.purpose})>"


class PasswordResetToken(BaseModel):
    """Single-use, hashed password-reset tokens (WordPress parity).

    Only the SHA-256 of the token is stored: the plaintext exists solely in the
    reset email, so a database leak cannot be replayed against /reset-password.
    """

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_token_hash", "token_hash", unique=True),
        Index("ix_password_reset_tokens_user_id", "user_id"),
        Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when a reset is issued so the UI can say "you already have a pending
    # request" without re-sending, and so a later request can void the earlier.
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<PasswordResetToken(user_id={self.user_id}, used={self.used_at is not None})>"


class EmailChangeRequest(BaseModel):
    """Single-use, hashed tokens confirming an email change.

    Same shape and same reasoning as :class:`PasswordResetToken`: only the
    SHA-256 of the token is stored, and it exists solely in the confirmation
    email. A database leak therefore cannot be replayed to take over an
    account by confirming someone else's address.

    The new address lives here rather than on ``User.pending_email`` because a
    request is a first-class thing that can be listed, expired and refused; a
    column on the user could not record *which* of several simultaneous
    requests a confirmation refers to.
    """

    __tablename__ = "email_change_requests"
    __table_args__ = (
        # Hash rather than token: the plaintext is single-use and only ever
        # travels by email, so an index on it would be an attack surface.
        Index("ix_email_change_requests_token_hash", "token_hash", unique=True),
        Index("ix_email_change_requests_user_id", "user_id"),
        Index("ix_email_change_requests_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # Named explicitly to match the migration. Under Postgres's 63-byte
        # identifier cap an auto-generated name would be truncated silently,
        # and the two would then drift apart in the constraint catalogue.
        ForeignKey("users.id", name="fk_email_change_requests_user_id_users", ondelete="CASCADE"),
        nullable=False,
    )
    #: The address being moved *to*. The user's current `email` is untouched
    #: until the token is redeemed, so a password reset issued before the
    #: confirmation still goes to the address the account really owns.
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Kept so the confirmation can be matched against the account it was sent
    #: for even if the user logs in through a different session.
    current_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: When the account's own address changed after this request was issued, the
    #: request is stale: the user has since moved the account elsewhere and this
    #: confirmation should not silently take it back.
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EmailChangeRequest(user_id={self.user_id}, "
            f"used={self.used_at is not None})>"
        )


class Address(BaseModel):
    """User delivery addresses."""

    __tablename__ = "addresses"
    __table_args__ = (
        Index("ix_addresses_user_id", "user_id"),
        Index("ix_addresses_province_city", "province", "city"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    full_address: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="addresses")

    def __repr__(self) -> str:
        return f"<Address(id={self.id}, title={self.title}, city={self.city})>"


class ApplicationPassword(BaseModel):
    """A named, revocable credential for a personal API client.

    WordPress parity: a phone or script that needs to read/write on the user's
    behalf authenticates with one of these instead of the account password, so
    the real password never leaves the password field and each client can be
    revoked on its own.

    Only a SHA-256 of the secret is stored, exactly like the reseller API key
    and the password-reset token. The plaintext is returned once at creation
    and is unrecoverable afterwards — that is the point.
    """

    __tablename__ = "application_passwords"
    __table_args__ = (
        Index("ix_application_passwords_user_id", "user_id"),
        Index("ix_application_passwords_token_hash", "token_hash", unique=True),
        Index("ix_application_passwords_is_active", "is_active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # What the user calls this credential ("گوشی من", "اسکریپت گزارش"). A
    # revocation screen full of undifferentiated tokens is unusable.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # First characters of the secret, stored so the UI can show which token is
    # which without being able to reconstruct it.
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Scopes this credential may use. Empty means "everything the user can do",
    # which is the WordPress default; a non-empty list is a strict subset, so a
    # read-only client cannot post even if it is compromised.
    scopes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )
    # When the credential was last used, so the user can spot one they forgot
    # about and revoke it.
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ApplicationPassword(user_id={self.user_id}, name={self.name})>"
