"""Approval workflow domain models."""

import enum
import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Enum, ForeignKey, Index, String, Text
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
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    level: Mapped[ApprovalLevel] = mapped_column(
        Enum(ApprovalLevel, name="approval_level_enum", native_enum=False),
        default=ApprovalLevel.LOW,
        nullable=False,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status_enum", native_enum=False),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    requester: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[requester_id], lazy="selectin"
    )
    actions: Mapped[list["ApprovalAction"]] = relationship(
        "ApprovalAction", back_populates="request", lazy="selectin", cascade="all, delete-orphan", order_by="ApprovalAction.created_at"
    )

    @property
    def requester_name(self) -> Optional[str]:
        if self.requester:
            if hasattr(self.requester, "profile") and self.requester.profile:
                parts = [self.requester.profile.first_name, self.requester.profile.last_name]
                name = " ".join(p for p in parts if p)
                if name:
                    return name
            return self.requester.phone or self.requester.email
        return None

    @property
    def requester_email(self) -> Optional[str]:
        return self.requester.email if self.requester else None

    @property
    def requester_phone(self) -> Optional[str]:
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
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    actor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[actor_id], lazy="selectin"
    )
    request: Mapped["ApprovalRequest"] = relationship(
        "ApprovalRequest", back_populates="actions"
    )

    @property
    def actor_name(self) -> Optional[str]:
        if self.actor:
            if hasattr(self.actor, "profile") and self.actor.profile:
                parts = [self.actor.profile.first_name, self.actor.profile.last_name]
                name = " ".join(p for p in parts if p)
                if name:
                    return name
            return self.actor.phone or self.actor.email
        return None

    @property
    def actor_email(self) -> Optional[str]:
        return self.actor.email if self.actor else None

    def __repr__(self) -> str:
        return f"<ApprovalAction(id={self.id}, action={self.action})>"
