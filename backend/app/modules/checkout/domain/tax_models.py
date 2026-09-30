"""Tax engine v1 domain models (additive upgrade).

Extends the legacy single-rule :class:`~app.modules.checkout.domain.models.TaxRule`
machinery with:

* effective-dated, priority-ordered rules of several types (VAT, exempt,
  compound, withholding / مالیات تکلیفی);
* per-category and per-product override scopes (product > category > default);
* per-order persisted tax observations (immutable, one row per order) so the
  fiscal data needed for سامانه مودیان reporting is captured at checkout time.

All monetary values and rates are integers: Rials for amounts, basis points
for rates (900 = 9.00%). No floats, no Decimal.

The legacy ``tax_rules`` table is intentionally left untouched — existing
checkout callers keep working against it.
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
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class TaxRuleType(str, enum.Enum):
    """Supported tax rule kinds."""

    VAT = "vat"  # ارزش افزوده — percentage added on top of the taxable base
    EXEMPT = "exempt"  # معاف — no tax charged; the reason is recorded
    COMPOUND = "compound"  # tax-on-tax: rate applies to (base + prior VAT)
    WITHHOLDING = "withholding"  # مالیات تکلیفی — withheld from the seller


class TaxRuleScope(str, enum.Enum):
    """Resolution scope. Priority: PRODUCT > CATEGORY > DEFAULT."""

    DEFAULT = "default"
    CATEGORY = "category"
    PRODUCT = "product"


class TaxRuleV2(BaseModel):
    """Effective-dated tax rule with optional category/product override scope.

    Rules are immutable once effective: instead of editing a live rule, a new
    row with a later ``effective_from`` is created (versioning by insertion).
    Exactly one active DEFAULT rule must exist at any point in time; the
    healthcheck endpoint warns when that invariant is broken.
    """

    __tablename__ = "tax_rules_v2"
    __table_args__ = (
        Index("ix_tax_rules_v2_code", "code", unique=True),
        Index("ix_tax_rules_v2_scope", "scope"),
        Index("ix_tax_rules_v2_category_id", "category_id"),
        Index("ix_tax_rules_v2_product_id", "product_id"),
        Index("ix_tax_rules_v2_is_active", "is_active"),
        Index("ix_tax_rules_v2_effective_dates", "effective_from", "effective_to"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    rule_type: Mapped[TaxRuleType] = mapped_column(
        Enum(TaxRuleType, name="tax_rule_type_enum", native_enum=False),
        default=TaxRuleType.VAT,
        nullable=False,
    )
    scope: Mapped[TaxRuleScope] = mapped_column(
        Enum(TaxRuleScope, name="tax_rule_scope_enum", native_enum=False),
        default=TaxRuleScope.DEFAULT,
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Integer basis points: 900 = 9.00%. Zero for EXEMPT rules.
    rate_basis_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Higher priority wins inside the same scope bucket.
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Human-readable reason recorded on exempt lines (e.g. «معافیت موضوع ماده ۱۲»).
    exempt_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def rate_percent(self) -> float:
        """Rate as a percentage (e.g. 9.0 for 900 basis points). Display only."""
        return self.rate_basis_points / 100.0

    def is_effective_at(self, dt: datetime) -> bool:
        """True when the rule is active and ``dt`` falls inside its window."""
        if not self.is_active:
            return False
        if self.effective_from and dt < self.effective_from:
            return False
        return not (self.effective_to and dt > self.effective_to)

    def __repr__(self) -> str:
        return (
            f"<TaxRuleV2(code='{self.code}', type='{self.rule_type.value}', "
            f"scope='{self.scope.value}', rate={self.rate_percent}%)>"
        )


class OrderTaxObservation(BaseModel):
    """Immutable per-order tax observation produced by the v1 engine.

    One row per order, written inside the same transaction as the order and
    its price snapshot. Holds the per-line tax breakdown (JSONB) plus the
    header totals — all integer Rials. Append-only: the ``before_update``
    listener below mirrors the price-snapshot immutability guard.

    This row is the fiscal source of truth feeding the VAT report and, later,
    سامانه مودیان submissions.
    """

    __tablename__ = "order_tax_observations"
    __table_args__ = (
        Index("ix_order_tax_observations_order_id", "order_id", unique=True),
        Index("ix_order_tax_observations_created_at", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="IRR", server_default="IRR", nullable=False
    )

    # Buyer context captured at calculation time (B2B withholding decisions
    # must be auditable against the certificate state at that moment).
    customer_is_b2b: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    exemption_certificate_ref: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # Per-line breakdown — each element:
    #   variant_id / product_id / category_id : str | null
    #   taxable_amount_rial  : int  (line total after proportional discount)
    #   rule_id / rule_code  : str | null
    #   rule_type            : str  (vat|exempt|compound|withholding)
    #   rate_basis_points    : int
    #   tax_amount_rial      : int  (vat + compound for the line)
    #   vat_amount_rial      : int
    #   compound_amount_rial : int
    #   withholding_amount_rial : int
    #   exempt_reason        : str | null
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    # Header totals (all integer Rials).
    vat_total_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    withholding_total_rial: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    tax_total_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    grand_total_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<OrderTaxObservation(order_id={self.order_id}, "
            f"vat_total_rial={self.vat_total_rial}, "
            f"withholding_total_rial={self.withholding_total_rial})>"
        )


@event.listens_for(OrderTaxObservation, "before_update")
def _block_observation_update(
    mapper: Any, connection: Any, target: OrderTaxObservation
) -> None:  # noqa: ARG001
    """Tax observations are append-only, like the price snapshot."""
    from app.core.exceptions.handlers import ValidationError

    raise ValidationError(
        "OrderTaxObservation is immutable — updates are forbidden. "
        f"Attempted to modify observation for order_id={target.order_id}"
    )
