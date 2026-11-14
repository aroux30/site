"""User-verification domain models.

Ports the WordPress plugin ``user-verification-orders`` (uv_*) into the
site backend:

- ``UserVerificationLog`` — the plugin's ``wp_uv_verification_logs`` table:
  one row per admin verify/unverify flip, with the acting admin, IP and
  timestamp. This is the audit surface the plugin's "گزارش لاگ‌ها" tab showed.

The verified flag itself lives on ``users.is_verified`` (it already exists and
the admin users API exposes it); the verified order status is
``OrderStatus.DOING_VERIFIED``. This module owns only what did NOT exist.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class UserVerificationLog(BaseModel):
    """One manual verification decision by an admin (plugin: uv_verification_logs)."""

    __tablename__ = "user_verification_logs"
    __table_args__ = (
        Index("ix_user_verification_logs_user_id", "user_id"),
        Index("ix_user_verification_logs_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    #: True = verified, False = unverified (the plugin's TINYINT status).
    status: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
