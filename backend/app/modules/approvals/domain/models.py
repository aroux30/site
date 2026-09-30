"""Approval workflow domain models."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.users.domain.models import User


# ---- Enums ----


class ApprovalLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    #: A multi-step request part-way through its chain: at least one step
    #: approved, further steps outstanding. Distinct from PENDING so the
    #: admin queue can tell "waiting for the first reviewer" apart from
    #: "waiting for the second signature".
    IN_REVIEW = "in_review"


class ApprovalStepStatus(str, enum.Enum):
    """State of one step in a multi-step chain."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class ApprovalActionType(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"


# ---- Models ----


class ApprovalRequest(BaseModel):
    """Requests requiring human approval before execution."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_requester_id", "requester_id"),
        Index("ix_approval_requests_type", "type"),
        Index("ix_approval_requests_status", "status"),
        Index("ix_approval_requests_resource", "resource"),
        Index("ix_approval_requests_created_at", "created_at"),
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    level: Mapped[ApprovalLevel] = mapped_column(
        Enum(ApprovalLevel, name="approval_level_enum", native_enum=False),
        default=ApprovalLevel.LOW,
        nullable=False,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        # `length` is explicit: SQLAlchemy derives a native_enum=False column's
        # width from the longest member *name* (IN_REVIEW, 8) while the longest
        # *value* is "in_review" (9), so the derived column is too narrow and a
        # multi-step approval overflows at flush. Pin it so adding a member
        # cannot silently retighten the column.
        Enum(
            ApprovalStatus,
            name="approval_status_enum",
            native_enum=False,
            length=20,
        ),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    requester: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[requester_id], lazy="selectin"
    )
    actions: Mapped[list["ApprovalAction"]] = relationship(
        "ApprovalAction",
        back_populates="request",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ApprovalAction.created_at",
    )
    #: Ordered signature chain. Empty for single-step (legacy) requests — the
    #: review path treats a request with no steps as one implicit step.
    steps: Mapped[list["ApprovalStep"]] = relationship(
        "ApprovalStep",
        back_populates="request",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ApprovalStep.step_order",
    )

    @property
    def current_step(self) -> "ApprovalStep | None":
        """The lowest-order PENDING step, or None when the chain is done."""
        pending = [s for s in (self.steps or []) if s.status == ApprovalStepStatus.PENDING]
        return pending[0] if pending else None

    @property
    def is_multi_step(self) -> bool:
        return bool(self.steps)

    @property
    def requester_name(self) -> str | None:
        if self.requester:
            if hasattr(self.requester, "profile") and self.requester.profile:
                parts = [self.requester.profile.first_name, self.requester.profile.last_name]
                name = " ".join(p for p in parts if p)
                if name:
                    return name
            return self.requester.phone or self.requester.email
        return None

    @property
    def requester_email(self) -> str | None:
        return self.requester.email if self.requester else None

    @property
    def requester_phone(self) -> str | None:
        return self.requester.phone if self.requester else None

    def __repr__(self) -> str:
        return f"<ApprovalRequest(id={self.id}, type={self.type}, status={self.status})>"


class ApprovalAction(BaseModel):
    """Individual approve/reject actions on an approval request."""

    __tablename__ = "approval_actions"
    __table_args__ = (
        Index("ix_approval_actions_request_id", "request_id"),
        Index("ix_approval_actions_actor_id", "actor_id"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[ApprovalActionType] = mapped_column(
        Enum(ApprovalActionType, name="approval_action_type_enum", native_enum=False),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    actor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[actor_id], lazy="selectin"
    )
    request: Mapped["ApprovalRequest"] = relationship("ApprovalRequest", back_populates="actions")

    @property
    def actor_name(self) -> str | None:
        if self.actor:
            if hasattr(self.actor, "profile") and self.actor.profile:
                parts = [self.actor.profile.first_name, self.actor.profile.last_name]
                name = " ".join(p for p in parts if p)
                if name:
                    return name
            return self.actor.phone or self.actor.email
        return None

    @property
    def actor_email(self) -> str | None:
        return self.actor.email if self.actor else None

    def __repr__(self) -> str:
        return f"<ApprovalAction(id={self.id}, action={self.action})>"


# ---- Multi-step chains and money policies (ERP feature #23, P1) ----
#
# The v1 engine was single-step: one review action closed a request. The
# chains below add ordered steps and a policy table that decides, from the
# request's own facts, how many signatures a money-moving action needs.
#
# Design notes
# ------------
# * A chain is materialised at submission (``ApprovalStep`` rows), not
#   computed at review time: the rule that applied when the request was made
#   is what the request is judged by, even if a policy changes mid-flight.
# * ``ApprovalPolicy`` is data, not code — operators tune thresholds without
#   a deployment, and the tests cover the matching logic directly.
# * Money thresholds are integer Rials, snapshot-compared in Python (see
#   ``policy_service``), never SQL-side floats.


class ApprovalStep(BaseModel):
    """One ordered signature requirement of a multi-step approval chain."""

    __tablename__ = "approval_steps"
    __table_args__ = (
        Index("ix_approval_steps_request_id", "request_id"),
        Index("ix_approval_steps_status", "status"),
        UniqueConstraint(
            "request_id",
            "step_order",
            name="uq_approval_steps_request_order",
        ),
        CheckConstraint("step_order >= 0", name="ck_approval_steps_order_non_negative"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: 0-based position; steps are approved in ascending order.
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Role slug whose holders may act on this step ("finance", "manager",
    #: "super_admin"…). Null means "any reviewer with approvals:write".
    required_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ApprovalStepStatus] = mapped_column(
        Enum(ApprovalStepStatus, name="approval_step_status_enum", native_enum=False),
        default=ApprovalStepStatus.PENDING,
        nullable=False,
    )
    acted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Persian label shown in the admin UI ("تایید مالی", "تایید مدیر").
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    request: Mapped["ApprovalRequest"] = relationship(
        "ApprovalRequest", back_populates="steps"
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalStep(request={self.request_id}, order={self.step_order}, "
            f"status={self.status.value})>"
        )


class ApprovalPolicy(BaseModel):
    """A rule mapping (resource, optional amount range) to a chain of steps.

    Matching is most-specific-first: an exact ``resource`` match beats the
    wildcard ``"*"``, and among same-resource rules the one with the highest
    ``min_amount_rial`` that is ``<=`` the request amount wins. A policy with
    ``min_amount_rial`` NULL applies to any amount below the next tier.
    """

    __tablename__ = "approval_policies"
    __table_args__ = (
        Index("ix_approval_policies_resource", "resource"),
        Index("ix_approval_policies_active", "is_active"),
        CheckConstraint(
            "min_amount_rial IS NULL OR min_amount_rial >= 0",
            name="ck_approval_policies_min_amount_non_negative",
        ),
    )

    #: Machine name ("refund", "wallet_withdrawal", "vendor_settlement", "*").
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Lower bound (inclusive) of the amount band this policy covers, Rials.
    min_amount_rial: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: Upper bound (exclusive); NULL means open-ended.
    max_amount_rial: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: Ordered chain definition:
    #: ``[{"role": "finance", "label": "تایید مالی"}, …]``.
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    #: Higher wins ties between overlapping same-resource bands.
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="ACTIVE"
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ApprovalPolicy(resource={self.resource!r}, "
            f"min={self.min_amount_rial}, steps={len(self.steps or [])})>"
        )
