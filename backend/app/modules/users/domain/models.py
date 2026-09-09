"""User domain models."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
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
    )

    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    __table_args__ = (
        Index("ix_user_profiles_national_code", "national_code"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    national_code: Mapped[Optional[str]] = mapped_column(
        String(10), unique=True, nullable=True
    )
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

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
    refresh_token: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False
    )
    device_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
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
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<OTPRequest(id={self.id}, phone={self.phone}, purpose={self.purpose})>"


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
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    full_address: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="addresses")

    def __repr__(self) -> str:
        return f"<Address(id={self.id}, title={self.title}, city={self.city})>"
