"""CRM: a deliberately minimal wholesale-inquiry pipeline.

ERP benchmark gap analysis (feature #18 CRM/leads, P2 — "minimal P2"). The
reference implementations (YetiForce, Odoo) are full sales suites with
opportunities, partners, competitions and registers. That scale is wrong for
a B2C storefront: for a consumer shop a sales pipeline has almost no value.

The real gap this closes is narrower and concrete: a business that wants to
buy digital cards in bulk has *no tracked funnel* before it becomes a
reseller. Today the inquiry arrives by phone or email and lives in someone's
inbox; nothing records it, nothing shows which inquiries are going stale, and
converting one to a partner account is manual re-typing.

So: an inquiry entity with stages, an owner, a value estimate, and one
conversion action that provisions the partner record. Nothing more.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.users.domain.models import User


class InquiryStage(str, enum.Enum):
    """Pipeline stages. Ordered; the UI renders them left to right."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    NEGOTIATING = "negotiating"
    CONVERTED = "converted"
    LOST = "lost"


#: Stages that end the funnel. A closed inquiry is never auto-reopened; a
#: returning prospect becomes a new inquiry, which keeps "why did we lose
#: them" and "who came back" separable questions.
CLOSED_STAGES: frozenset[InquiryStage] = frozenset(
    {InquiryStage.CONVERTED, InquiryStage.LOST}
)

#: Legal forward moves. A staged pipeline where anything can jump anywhere is
#: a status field, not a pipeline — the point is that `qualified` means
#: someone actually checked the prospect can buy.
_ALLOWED_TRANSITIONS: dict[InquiryStage, frozenset[InquiryStage]] = {
    InquiryStage.NEW: frozenset(
        {InquiryStage.CONTACTED, InquiryStage.QUALIFIED, InquiryStage.LOST}
    ),
    InquiryStage.CONTACTED: frozenset(
        {InquiryStage.QUALIFIED, InquiryStage.LOST}
    ),
    InquiryStage.QUALIFIED: frozenset(
        {InquiryStage.NEGOTIATING, InquiryStage.LOST, InquiryStage.CONVERTED}
    ),
    InquiryStage.NEGOTIATING: frozenset(
        {InquiryStage.CONVERTED, InquiryStage.LOST}
    ),
    InquiryStage.CONVERTED: frozenset(),
    InquiryStage.LOST: frozenset(),
}


def is_transition_allowed(current: InquiryStage, target: InquiryStage) -> bool:
    """True when the pipeline permits this stage change. Pure."""
    if current == target:
        return False
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


class InquirySource(str, enum.Enum):
    """Where the inquiry came from — drives follow-up channel choice."""

    WEB_FORM = "web_form"
    PHONE = "phone"
    EMAIL = "email"
    REFERRAL = "referral"
    SOCIAL = "social"
    OTHER = "other"


class LeadInquiry(BaseModel):
    """A wholesale/reseller inquiry moving through the pipeline."""

    __tablename__ = "lead_inquiries"
    __table_args__ = (
        Index("ix_lead_inquiries_stage", "stage"),
        Index("ix_lead_inquiries_owner_id", "owner_id"),
        Index("ix_lead_inquiries_created_at", "created_at"),
        Index("ix_lead_inquiries_company", "company_name"),
        CheckConstraint(
            "estimated_value_rial IS NULL OR estimated_value_rial >= 0",
            name="ck_lead_inquiries_value_non_negative",
        ),
        CheckConstraint(
            "contact_name <> ''", name="ck_lead_inquiries_contact_name_not_empty"
        ),
    )

    #: Contact person and company. The company is what makes an inquiry
    #: wholesale rather than a consumer asking about a discount.
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    stage: Mapped[InquiryStage] = mapped_column(
        Enum(InquiryStage, name="inquiry_stage_enum", native_enum=False),
        default=InquiryStage.NEW,
        nullable=False,
    )
    source: Mapped[InquirySource] = mapped_column(
        Enum(InquirySource, name="inquiry_source_enum", native_enum=False),
        default=InquirySource.WEB_FORM,
        nullable=False,
    )

    #: What they want, in their words, plus a structured estimate staff fill
    #: in once they know. Both exist: the free text is the record of the
    #: original ask, the estimate is what reporting uses.
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_monthly_value_rial: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    estimated_monthly_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Assigned staff member. Null means unclaimed — the admin list surfaces
    #: unclaimed NEW inquiries first for exactly that reason.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    #: The partner account this inquiry became, if converted. SET NULL on
    #: user deletion: the inquiry record outlives the account it created,
    #: because "we converted this lead" is history.
    converted_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lost_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Free-form notes for the timeline (staff append; no edit history here —
    #: the audit module owns field-level history).
    notes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    #: When the next follow-up is due; the list sorts overdue first.
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    owner: Mapped["User | None"] = relationship(
        "User", foreign_keys=[owner_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<LeadInquiry(id={self.id}, contact={self.contact_name!r}, "
            f"stage={self.stage.value})>"
        )
