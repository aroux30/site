"""CRUD service for automation rules (admin-managed)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import NotFoundError
from app.modules.automation.domain.rule_models import AutomationRule, AutomationTriggerType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def list_rules(
    db: AsyncSession,
    *,
    trigger_type: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AutomationRule], int]:
    """List automation rules with optional filters, newest first."""
    stmt = select(AutomationRule)
    count_stmt = select(func.count()).select_from(AutomationRule)

    if trigger_type is not None:
        trigger_value = AutomationTriggerType(str(trigger_type).strip().lower())
        stmt = stmt.where(AutomationRule.trigger_type == trigger_value)
        count_stmt = count_stmt.where(AutomationRule.trigger_type == trigger_value)
    if is_active is not None:
        stmt = stmt.where(AutomationRule.is_active.is_(is_active))
        count_stmt = count_stmt.where(AutomationRule.is_active.is_(is_active))

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(AutomationRule.created_at.desc()).offset(offset).limit(limit)
    items = list((await db.execute(stmt)).scalars().all())
    return items, int(total)


async def get_rule(db: AsyncSession, *, rule_id: uuid.UUID) -> AutomationRule:
    rule = await db.get(AutomationRule, rule_id)
    if rule is None:
        raise NotFoundError(resource="AutomationRule")
    return rule


async def create_rule(db: AsyncSession, *, data: dict[str, Any]) -> AutomationRule:
    """Create a rule; ``conditions``/``actions`` arrive schema-validated."""
    rule = AutomationRule(
        name=data["name"],
        description=data.get("description"),
        trigger_type=AutomationTriggerType(data["trigger_type"]),
        conditions=data.get("conditions") or [],
        actions=data.get("actions") or [],
        is_active=data.get("is_active", True),
        cooldown_minutes=data.get("cooldown_minutes"),
    )
    db.add(rule)
    await db.flush()
    await logger.ainfo(
        "automation_rule_created",
        rule_id=str(rule.id),
        name=rule.name,
        trigger_type=rule.trigger_type.value,
    )
    return rule


async def update_rule(
    db: AsyncSession,
    *,
    rule_id: uuid.UUID,
    data: dict[str, Any],
) -> AutomationRule:
    """Patch a rule; ``None`` fields are left untouched."""
    rule = await get_rule(db, rule_id=rule_id)

    if data.get("name") is not None:
        rule.name = data["name"]
    if "description" in data:
        rule.description = data["description"]
    if data.get("conditions") is not None:
        rule.conditions = data["conditions"]
    if data.get("actions") is not None:
        rule.actions = data["actions"]
    if data.get("is_active") is not None:
        rule.is_active = data["is_active"]
    if "cooldown_minutes" in data:
        rule.cooldown_minutes = data["cooldown_minutes"]

    await db.flush()
    await logger.ainfo("automation_rule_updated", rule_id=str(rule.id))
    return rule


async def delete_rule(db: AsyncSession, *, rule_id: uuid.UUID) -> None:
    rule = await get_rule(db, rule_id=rule_id)
    await db.delete(rule)
    await db.flush()
    await logger.ainfo("automation_rule_deleted", rule_id=str(rule_id))
