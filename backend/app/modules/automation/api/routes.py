"""Automation admin API routes (rules CRUD + manual test-fire)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.automation.application import rules_engine, rules_service
from app.shared.events.outbox_models import OutboxStatus
from app.shared.events.outbox_service import OutboxService
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


# ── Dead letters (wave 6 #82) ──────────────────────────────────────────────
# The outbox had four writers of DEAD_LETTER and no reader, so a message that
# exhausted its retries sat in a terminal state no operator could see or replay.
# `has_scope`-style promises are exactly this bug's shape: a state exists, the
# documentation implies someone handles it, and nobody can.

_OUTBOX_STATUSES = {
    "dead_letter": OutboxStatus.DEAD_LETTER,
    "failed": OutboxStatus.FAILED,
    "pending": OutboxStatus.PENDING,
    "processed": OutboxStatus.PROCESSED,
}


class DeadLetterItem(BaseModel):
    id: uuid.UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    status: str
    retry_count: int
    max_retries: int
    last_error: str | None
    created_at: datetime
    available_at: datetime


class DeadLetterListResponse(BaseModel):
    items: list[DeadLetterItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class RequeueResult(BaseModel):
    id: uuid.UUID
    status: str
    retry_count: int
    message: str


@router.get(
    "/admin/outbox/dead-letters",
    response_model=DeadLetterListResponse,
    dependencies=[Depends(RequirePermissions("automation:read"))],
    summary="List outbox messages by status, for the dead-letter screen",
)
async def list_outbox_messages(
    status_filter: str = Query(
        "dead_letter",
        alias="status",
        description="Which queue state to list",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> DeadLetterListResponse:
    """Messages that failed permanently, so an operator can see what broke.

    Defaults to the dead-letter queue rather than all traffic: an operator
    opening this screen is asking "what is broken", not "show me everything".
    """
    wanted = _OUTBOX_STATUSES.get(status_filter)
    if wanted is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown status {status_filter!r}; expected one of "
                f"{', '.join(sorted(_OUTBOX_STATUSES))}"
            ),
        )

    rows, total = await OutboxService.list_by_status(
        db, wanted, limit=page_size, offset=(page - 1) * page_size
    )
    items = [
        DeadLetterItem(
            id=m.id,
            event_type=m.event_type,
            aggregate_type=m.aggregate_type,
            aggregate_id=m.aggregate_id,
            status=m.status.value,
            retry_count=m.retry_count,
            max_retries=m.max_retries,
            last_error=m.last_error,
            created_at=m.created_at,
            available_at=m.available_at,
        )
        for m in rows
    ]
    return DeadLetterListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-total // page_size)),
    )


@router.post(
    "/admin/outbox/dead-letters/{message_id}/requeue",
    response_model=RequeueResult,
    dependencies=[Depends(RequirePermissions("automation:write"))],
    summary="Replay a dead-lettered outbox message",
)
async def requeue_outbox_message(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RequeueResult:
    """Put a failed message back on the queue.

    Retry count resets by default: replaying is normally done after fixing the
    cause, and a carried-forward exhausted counter would dead-letter the message
    again on its very next failure.
    """
    try:
        msg = await OutboxService.requeue(db, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Outbox message not found"
        )
    return RequeueResult(
        id=msg.id,
        status=msg.status.value,
        retry_count=msg.retry_count,
        message="پیام دوباره در صف قرار گرفت.",
    )


@router.delete(
    "/admin/outbox/dead-letters/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermissions("automation:write"))],
    summary="Discard a dead-lettered outbox message",
)
async def purge_outbox_message(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a dead letter for good, for an event that should never run."""
    if not await OutboxService.purge(db, message_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Outbox message not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
