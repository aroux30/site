"""Automation rule domain models.

The automation module previously shipped only the transactional-outbox
Celery worker; rules let operators declare "when X happens, do Y" without
code changes — a WordPress/Hook-io style trigger → conditions → actions
pipeline.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class AutomationTriggerType(str, enum.Enum):
    """Events automation rules can hook into."""

    ORDER_PAID = "order_paid"
    ORDER_CREATED = "order_created"
    USER_REGISTERED = "user_registered"
    REVIEW_CREATED = "review_created"
    STOCK_LOW = "stock_low"


class AutomationRule(BaseModel):
    """One declarative automation rule: trigger → conditions → actions.

    ``conditions`` is a JSON list of ``{"field", "operator", "value"}`` where
    *field* is a dotted path into the trigger context and *operator* is one
    of ``eq | ne | gt | lt | gte | lte | contains``. All conditions must pass
    (AND); a missing context field fails the condition.

    ``actions`` is a JSON list of ``{"type", "params"}`` with *type* one of
    ``send_email | send_notification | fire_webhook``. Each action runs
    independently — one failing action never aborts the others.
    """

    __tablename__ = "automation_rules"
    __table_args__ = (
        Index("ix_automation_rules_trigger_active", "trigger_type", "is_active"),
        Index("ix_automation_rules_name", "name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trigger_type: Mapped[AutomationTriggerType] = mapped_column(
        Enum(
            AutomationTriggerType,
            name="automation_trigger_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Re-trigger throttle: after a fire, the rule sleeps this many minutes.
    cooldown_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AutomationRule(id={self.id}, name={self.name}, trigger={self.trigger_type})>"
