"""Field-level change log for arbitrary tracked entities (ERP feature #9).

The existing :class:`~app.modules.audit.domain.models.AuditLog` records
*actions* ("admin updated product X"). It cannot answer the ERP-grade question
*"who changed this product's price from 1,200,000 to 950,000, and when?"* —
the action row carries no per-field before/after pair.

``EntityChangeLog`` is that missing row: one row per (flush, entity) that
changed at least one tracked field, carrying the field-level diff as JSONB.

Design notes
------------
* **Additive and observation-only.** The capture hook (see
  ``application.change_tracking``) runs inside ``after_flush`` and never
  mutates the business object; a capture failure is logged and swallowed so it
  can never roll back or block the business transaction.
* **Money stays integer.** ``changed_fields`` holds raw JSON-safe values —
  integer Rial amounts stay Python ``int`` (no float coercion), matching the
  platform-wide integer-money invariant.
* **Low-cardinality identity.** ``entity_type`` is a stable short string
  (``"product"``, ``"wallet"``, …) from :data:`TRACKED_ENTITIES`;
  ``entity_id`` is a UUID for ORM-tracked rows and a free string otherwise.
* **Anonymous actors are legitimate.** ``actor_id`` is nullable with
  ``ondelete=SET NULL``: a change made by a Celery task or a seed script has
  no user, and deleting a user must not erase the evidence of what they did.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ChangeActorType(str, enum.Enum):
    """Who performed the change. ``user`` carries an ``actor_id``."""

    USER = "user"
    SYSTEM = "system"
    CELERY = "celery"


class ChangeSource(str, enum.Enum):
    """How the change entered the system."""

    API = "api"
    ADMIN = "admin"
    SERVICE = "service"
    SEED = "seed"


class ChangeOperation(str, enum.Enum):
    """What happened to the row.

    Creation is logged with empty ``old_value``\\ s and deletion with empty
    ``new_value``\\ s — the ERPNext traceback rule: a deleted financial record
    must leave a readable trace of what it held, not vanish.
    """

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class EntityChangeLog(BaseModel):
    """One flush's worth of field-level changes to one tracked entity row."""

    __tablename__ = "entity_change_logs"
    __table_args__ = (
        Index("ix_entity_change_logs_entity", "entity_type", "entity_id"),
        Index("ix_entity_change_logs_entity_type", "entity_type"),
        Index("ix_entity_change_logs_actor_id", "actor_id"),
        Index("ix_entity_change_logs_occurred_at", "occurred_at"),
        Index("ix_entity_change_logs_request_id", "request_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[ChangeOperation] = mapped_column(
        Enum(ChangeOperation, name="change_operation_enum", native_enum=False),
        default=ChangeOperation.UPDATE,
        nullable=False,
    )
    #: ``[{"field": "price", "old_value": 1200000, "new_value": 950000}, …]``
    changed_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[ChangeActorType] = mapped_column(
        Enum(ChangeActorType, name="change_actor_type_enum", native_enum=False),
        default=ChangeActorType.SYSTEM,
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[ChangeSource] = mapped_column(
        Enum(ChangeSource, name="change_source_enum", native_enum=False),
        default=ChangeSource.SERVICE,
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: True when at least one value was shortened to the storage cap; the
    #: stored text then ends in ``…`` and the full value is unrecoverable by
    #: design — the flag is what makes that visible to a reviewer.
    truncated: Mapped[bool] = mapped_column(
        default=False, nullable=False, server_default="false"
    )

    def __repr__(self) -> str:
        return (
            f"<EntityChangeLog(id={self.id}, entity_type={self.entity_type}, "
            f"entity_id={self.entity_id}, operation={self.operation})>"
        )
