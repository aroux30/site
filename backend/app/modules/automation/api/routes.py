"""Automation admin API routes (rules CRUD + manual test-fire)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.automation.application import rules_engine, rules_service
from app.modules.automation.schemas.rule import (
    AutomationRuleCreate,
    AutomationRuleListResponse,
    AutomationRuleResponse,
    AutomationRuleTestRequest,
    AutomationRuleTestResponse,
    AutomationRuleUpdate,
)

router = APIRouter()


@router.get(
    "/admin/rules",
    response_model=AutomationRuleListResponse,
    dependencies=[Depends(RequirePermissions("automation:read"))],
    summary="List automation rules",
)
async def list_rules(
    trigger_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleListResponse:
    items, total = await rules_service.list_rules(
        db,
        trigger_type=trigger_type,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return AutomationRuleListResponse(
        items=[AutomationRuleResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get(
    "/admin/rules/{rule_id}",
    response_model=AutomationRuleResponse,
    dependencies=[Depends(RequirePermissions("automation:read"))],
    summary="Get an automation rule",
)
async def get_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    rule = await rules_service.get_rule(db, rule_id=rule_id)
    return AutomationRuleResponse.model_validate(rule)


@router.post(
    "/admin/rules",
    response_model=AutomationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("automation:write"))],
    summary="Create an automation rule",
)
async def create_rule(
    body: AutomationRuleCreate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    del actor_id  # rule creation is not audit-logged yet; actor kept for parity
    rule = await rules_service.create_rule(
        db,
        data={
            "name": body.name,
            "description": body.description,
            "trigger_type": body.trigger_type,
            "conditions": [c.model_dump() for c in body.conditions],
            "actions": [a.model_dump() for a in body.actions],
            "is_active": body.is_active,
            "cooldown_minutes": body.cooldown_minutes,
        },
    )
    return AutomationRuleResponse.model_validate(rule)


@router.patch(
    "/admin/rules/{rule_id}",
    response_model=AutomationRuleResponse,
    dependencies=[Depends(RequirePermissions("automation:write"))],
    summary="Update an automation rule",
)
async def update_rule(
    rule_id: uuid.UUID,
    body: AutomationRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    data: dict[str, Any] = {
        "name": body.name,
        "description": body.description,
        "conditions": [c.model_dump() for c in body.conditions] if body.conditions else None,
        "actions": [a.model_dump() for a in body.actions] if body.actions else None,
        "is_active": body.is_active,
        "cooldown_minutes": body.cooldown_minutes,
    }
    rule = await rules_service.update_rule(db, rule_id=rule_id, data=data)
    return AutomationRuleResponse.model_validate(rule)


@router.delete(
    "/admin/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("automation:write"))],
    summary="Delete an automation rule",
)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await rules_service.delete_rule(db, rule_id=rule_id)


@router.post(
    "/admin/rules/{rule_id}/trigger",
    response_model=AutomationRuleTestResponse,
    dependencies=[Depends(RequirePermissions("automation:write"))],
    summary="Test-fire an automation rule against a synthetic context",
)
async def trigger_rule(
    rule_id: uuid.UUID,
    body: AutomationRuleTestRequest,
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleTestResponse:
    """Evaluate one rule immediately with the given context (admin dry-run)."""
    rule = await rules_service.get_rule(db, rule_id=rule_id)
    matched = rules_engine.match_conditions(rule.conditions, body.context)
    actions: list[dict[str, Any]] = []
    if matched:
        actions = await rules_engine.run_actions(rule.actions, db, body.context)
        rule.last_triggered_at = datetime.now(UTC)
        await db.flush()
    return AutomationRuleTestResponse(matched=matched, actions=actions)
