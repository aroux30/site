"""Tax domain models for configurable taxation rules."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class TaxCategory(str, enum.Enum):
    """Product tax category classification."""

    STANDARD = "standard"        # e.g., standard 10% VAT in Iran
    REDUCED = "reduced"          # e.g., basic foodstuffs (if applicable)
    EXEMPT = "exempt"            # e.g., medical supplies, books
    ZERO = "zero"                # 0% rate


class TaxRule(BaseModel):
    """Configurable tax rule determining applied tax rates per jurisdiction."""

    __tablename__ = "tax_rules"
    __table_args__ = (
        Index("ix_tax_rules_code", "code", unique=True),
        Index("ix_tax_rules_category", "category"),
        Index("ix_tax_rules_jurisdiction", "jurisdiction"),
        Index("ix_tax_rules_is_active", "is_active"),
        Index("ix_tax_rules_effective_dates", "effective_from", "effective_to"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category: Mapped[TaxCategory] = mapped_column(
        Enum(TaxCategory, name="tax_category_enum", native_enum=False),
        default=TaxCategory.STANDARD,
        nullable=False,
    )
    jurisdiction: Mapped[str] = mapped_column(
        String(50), default="IR", nullable=False
    )
    rate_basis_points: Mapped[int] = mapped_column(
        Integer, default=1000, nullable=False
    )  # 1000 basis points = 10.00% (VAT rate in Iran)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_compound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effective_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @property
    def rate_percent(self) -> float:
        """Return rate as a percentage (e.g. 10.0 for 1000 basis points)."""
        return self.rate_basis_points / 100.0

    def is_effective_at(self, dt: datetime) -> bool:
        """Check if this rule is effective at the given timestamp."""
        if not self.is_active:
            return False
        if self.effective_from and dt < self.effective_from:
            return False
        if self.effective_to and dt > self.effective_to:
            return False
        return True

    def __repr__(self) -> str:
        return f"<TaxRule(code='{self.code}', rate={self.rate_percent}%, category='{self.category.value}')>"
