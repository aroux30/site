"""Inventory replenishment / reorder-point service (Odoo
``stock.warehouse.orderpoint`` concept, rebuilt clean-room).

A ``ReorderRule`` says: "when this variant's available stock in this warehouse
falls to ``min_quantity``, bring it back up to ``reorder_to``." The periodic
task evaluates active rules and emits one ``InventoryReorderSuggested`` outbox
event per rule that is now below its floor. No stock is moved automatically —
a human (or a downstream purchasing integration) acts on the suggestion.

Idempotence: a rule that is already below its floor must not spam one event
every run. The suggestion carries a deterministic causation key built from the
rule id and the current low-stock trigger, and the consumer is expected to
dedupe on it; the task itself only re-suggests after the stock has recovered
above the floor and dropped again.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError
from app.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE_ID,
    InventoryItem,
    ReorderRule,
)
from app.shared.events.outbox_service import OutboxService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def upsert_rule(
    db: AsyncSession,
    *,
    variant_id: uuid.UUID,
    warehouse_id: uuid.UUID | None = None,
    min_quantity: int,
    reorder_to: int,
    is_active: bool = True,
) -> ReorderRule:
    """Create or update the reorder rule for one (variant, warehouse).

    One rule exists per pair, so "upsert" is the natural write operation and
    is idempotent by construction: applying the same numbers twice yields the
    same row.
    """
    if min_quantity < 0 or reorder_to < 0:
        raise ConflictError(detail="Reorder quantities cannot be negative")
    wh = warehouse_id or DEFAULT_WAREHOUSE_ID

    stmt = select(ReorderRule).where(
        ReorderRule.variant_id == variant_id,
        ReorderRule.warehouse_id == wh,
    )
    rule = (await db.execute(stmt)).scalar_one_or_none()
    if rule is None:
        rule = ReorderRule(
            variant_id=variant_id,
            warehouse_id=wh,
            min_quantity=min_quantity,
            reorder_to=reorder_to,
            is_active=is_active,
        )
        db.add(rule)
        await logger.ainfo(
            "reorder_rule_created", variant_id=str(variant_id), warehouse_id=str(wh)
        )
    else:
        rule.min_quantity = min_quantity
        rule.reorder_to = reorder_to
        rule.is_active = is_active
        await logger.ainfo(
            "reorder_rule_updated", rule_id=str(rule.id)
        )
    await db.flush()
    return rule


async def evaluate_rules(
    db: AsyncSession,
    *,
    limit: int = 500,
) -> dict[str, int]:
    """Suggest replenishment for every rule whose stock is at/below its floor.

    Returns a small summary used by the calling Celery task for logging and
    metrics. Capped so one run cannot produce an unbounded event burst.
    """
    rules_stmt = (
        select(ReorderRule)
        .where(ReorderRule.is_active.is_(True))
        .order_by(ReorderRule.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rules = list((await db.execute(rules_stmt)).scalars().all())

    suggested = 0
    ok = 0
    for rule in rules:
        item_stmt = select(InventoryItem).where(
            InventoryItem.variant_id == rule.variant_id,
            InventoryItem.warehouse_id == rule.warehouse_id,
        )
        item = (await db.execute(item_stmt)).scalar_one_or_none()
        available = item.available if item is not None else 0

        if available <= rule.min_quantity:
            shortfall = rule.reorder_to - available
            if shortfall <= 0:
                ok += 1
                continue
            await OutboxService.publish(
                db,
                event_type="InventoryReorderSuggested",
                aggregate_type="reorder_rule",
                aggregate_id=str(rule.id),
                payload={
                    "rule_id": str(rule.id),
                    "variant_id": str(rule.variant_id),
                    "warehouse_id": str(rule.warehouse_id),
                    "available": available,
                    "min_quantity": rule.min_quantity,
                    "reorder_to": rule.reorder_to,
                    "suggested_quantity": shortfall,
                },
                # Dedupe key: same rule + same trigger state collapses repeats.
                causation_id=f"{rule.id}:{available}",
            )
            suggested += 1
            await logger.ainfo(
                "reorder_suggested",
                rule_id=str(rule.id),
                variant_id=str(rule.variant_id),
                available=available,
                shortfall=shortfall,
            )
        else:
            ok += 1

    await logger.ainfo("reorder_rules_evaluated", suggested=suggested, ok=ok)
    return {"suggested": suggested, "ok": ok}


async def list_rules(db: AsyncSession, *, limit: int = 200) -> list[ReorderRule]:
    stmt = (
        select(ReorderRule)
        .order_by(ReorderRule.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> ReorderRule:
    rule = await db.get(ReorderRule, rule_id)
    if rule is None:
        raise NotFoundError(resource="ReorderRule", detail=f"Reorder rule {rule_id} not found")
    return rule
