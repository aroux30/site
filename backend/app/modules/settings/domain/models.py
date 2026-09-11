"""Site settings domain models."""

from typing import Any

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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
