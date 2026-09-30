"""Installment plans on orders (payments upgrade v1).

ERP benchmark gap analysis (feature #6 Payments, P1 — installments / BNPL).

Money rules
-----------
Every amount is an **integer Rial** (``BigInteger``), never a float:

* ``total_rial`` is the order total the plan covers.
* ``first_installment_rial`` is the prepayment taken at plan creation.
* The remaining ``num_installments - 1`` installments are split evenly and the
  **last** installment absorbs the division remainder, so

      first_installment_rial + sum(remaining) == total_rial

  holds exactly for every plan (asserted in
  :mod:`app.modules.payments.application.installment_service` before the row
  is written, not after).

Jalali dates
------------
The schedule stores ``due_date_jalali`` as a display label (``"1404/07/05"``)
because that is what Iranian customers and statements use; the Gregorian
``due_date`` is kept alongside it for scheduling (Celery reminders) and for
indexed range queries.

Gateway support
---------------
Iranian gateways sell installment/credit purchases (Zarinpal Plus, IDPay
credit products) as **merchant-contract** features whose API surface differs
per contract; the public v4/v1.1 endpoints used by this codebase have no
installment call. The plan is therefore modelled as a provider capability
(:attr:`PaymentProvider.supports_installments` /
:attr:`PaymentProvider.installment_options_months`) with a working mock
implementation for development and tests — see
:mod:`app.modules.payments.infrastructure.providers.base`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class InstallmentPlanStatus(str, enum.Enum):
    """Plan lifecycle.

    ``PENDING``  — plan created, first installment not yet settled.
    ``ACTIVE``   — first installment settled, remaining schedule running.
    ``COMPLETED``— every scheduled installment is paid.
    ``CANCELED`` — plan voided (order canceled / admin action).
    ``DEFAULTED``— a scheduled installment went unpaid past its due date.
    """

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELED = "canceled"
    DEFAULTED = "defaulted"


class InstallmentPlan(BaseModel):
    """An installment schedule attached to one order."""

    __tablename__ = "installment_plans"
    __table_args__ = (
        # One live plan per order: two plans would each believe they own the
        # order total and the sum of the two would double-count revenue.
        UniqueConstraint("order_id", name="uq_installment_plans_order_id"),
        Index("ix_installment_plans_user_id", "user_id"),
        Index("ix_installment_plans_provider", "provider"),
        Index("ix_installment_plans_status", "status"),
        # Integer-Rial guards. The schedule-sum invariant is asserted in the
        # service; these bound the columns the invariant is built from.
        CheckConstraint("total_rial > 0", name="ck_installment_plans_total_positive"),
        CheckConstraint(
            "first_installment_rial > 0", name="ck_installment_plans_first_positive"
        ),
        CheckConstraint(
            "first_installment_rial <= total_rial",
            name="ck_installment_plans_first_within_total",
        ),
        CheckConstraint(
            "num_installments >= 2 AND num_installments <= 24",
            name="ck_installment_plans_count_range",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Payment that settled the first installment (nullable until it settles).
    first_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    total_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    num_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    first_installment_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # [{"due_date_jalali": "1404/07/05", "due_date": "2025-09-27",
    #   "amount_rial": 250000, "status": "pending", "paid_at": null}, ...]
    # Length is num_installments; entry 0 is the first (prepaid) installment.
    schedule: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[InstallmentPlanStatus] = mapped_column(
        Enum(
            InstallmentPlanStatus,
            name="installment_plan_status_enum",
            native_enum=False,
        ),
        default=InstallmentPlanStatus.PENDING,
        nullable=False,
        server_default=text("'PENDING'::character varying"),
    )
    # Next unpaid due date, denormalised for reminder queries.
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    created_by_gateway: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<InstallmentPlan(id={self.id}, order_id={self.order_id}, "
            f"n={self.num_installments}, status={self.status})>"
        )
