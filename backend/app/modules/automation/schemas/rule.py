"""Pydantic schemas for automation rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TriggerType = Literal[
    "order_paid", "order_created", "user_registered", "review_created", "stock_low"
]
ConditionOperator = Literal["eq", "ne", "gt", "lt", "gte", "lte", "contains"]
ActionType = Literal["send_email", "send_notification", "fire_webhook"]


class RuleCondition(BaseModel):
    """One condition: a dotted context field compared against a value."""

    field: str = Field(..., min_length=1, examples=["order.total"])
    operator: ConditionOperator
    value: Any


class RuleAction(BaseModel):
    """One action executed when the rule matches."""

    type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)


class AutomationRuleCreate(BaseModel):
    """Create an automation rule."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    trigger_type: TriggerType
    conditions: list[RuleCondition] = Field(default_factory=list)
    actions: list[RuleAction] = Field(..., min_length=1)
    is_active: bool = True
    cooldown_minutes: int | None = Field(None, ge=0)


class AutomationRuleUpdate(BaseModel):
    """Update an automation rule (partial)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    conditions: list[RuleCondition] | None = None
    actions: list[RuleAction] | None = None
    is_active: bool | None = None
    cooldown_minutes: int | None = Field(None, ge=0)


class AutomationRuleResponse(BaseModel):
    """Automation rule output."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    trigger_type: str
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    is_active: bool
    cooldown_minutes: int | None = None
    last_triggered_at: datetime | None = None
    created_at: datetime


class AutomationRuleListResponse(BaseModel):
    """Paginated automation rule list."""

    items: list[AutomationRuleResponse]
    total: int


class AutomationRuleTestRequest(BaseModel):
    """Fire a rule against a synthetic context (admin dry-run)."""

    context: dict[str, Any] = Field(default_factory=dict)


class AutomationRuleTestResponse(BaseModel):
    """Result of firing one rule."""

    matched: bool
    actions: list[dict[str, Any]] = []
