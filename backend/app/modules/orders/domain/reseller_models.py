"""B2B Reseller API domain models (Karta Phase 4).

Implements:
- ResellerApiKey: Secure hashed API keys for partner websites and wholesale automated ordering
- IP whitelisting, rate limits, and pre-paid credit balance management
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ResellerApiKey(BaseModel):
    """B2B Partner API credentials for automated stock inquiry and wholesale purchasing."""

    __tablename__ = "reseller_api_keys"
    __table_args__ = (
        Index("ix_reseller_api_keys_user_id", "user_id"),
        Index("ix_reseller_api_keys_key_hash", "key_hash"),
        Index("ix_reseller_api_keys_is_active", "is_active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Partner or company name
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. "b2b_live_abc1"
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA-256
    ip_whitelist: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # List of allowed IPs
    credit_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # Pre-paid balance in IRR
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ResellerApiKey(id={self.id}, name={self.name}, prefix={self.key_prefix})>"
