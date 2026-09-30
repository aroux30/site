"""Pydantic schemas for installment plans.

Amounts are integer Rials; dates carry both the Gregorian value (``due_date``)
and the Jalali display label (``due_date_jalali``) so the frontend needs no
date-conversion library.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.domain.installment_models import InstallmentPlanStatus


class InstallmentScheduleEntry(BaseModel):
    """One installment on a plan's schedule."""

    model_config = ConfigDict(from_attributes=True)

    due_date_jalali: str
    due_date: date | None = None
    amount_rial: int
    status: str
    paid_at: datetime | None = None
    is_prepayment: bool = False


class InstallmentPlanResponse(BaseModel):
    """Client-facing installment plan with its full schedule."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    total_rial: int
    num_installments: int
    first_installment_rial: int
    remaining_rial: int
    schedule: list[InstallmentScheduleEntry]
    status: InstallmentPlanStatus
    next_due_date: date | None = None
    paid_count: int
    created_at: datetime
    updated_at: datetime


class InstallmentPlanListResponse(BaseModel):
    """List wrapper for the account page."""

    items: list[InstallmentPlanResponse]
    total: int


class CreateInstallmentPlanRequest(BaseModel):
    """Customer's installment choice at checkout.

    ``total_rial`` is deliberately absent: the plan is always built from the
    order's own total, so a client cannot propose a total it likes.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: uuid.UUID
    provider: str = Field(..., max_length=50)
    num_installments: int = Field(..., ge=2, le=24)
    first_installment_rial: int = Field(
        ...,
        gt=0,
        description="Prepayment taken now, in IRR (remainder is split monthly)",
    )


class InstallmentOption(BaseModel):
    """One duration a gateway offers, with the customer's monthly breakdown."""

    num_installments: int
    first_installment_rial: int
    monthly_installment_rial: int
    remaining_rial: int
    schedule: list[InstallmentScheduleEntry]


class InstallmentOptionsResponse(BaseModel):
    """Installment options for an order at one gateway.

    Computed server-side so the checkout UI never reimplements the rounding
    rule; every option's schedule sums exactly to the order total.
    """

    provider: str
    supported: bool
    order_total_rial: int
    months: list[int]
    options: list[InstallmentOption]
