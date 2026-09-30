"""Abandoned-cart recovery service.

Concept ported from Odoo ``website_sale``'s abandoned-cart follow-up, rebuilt
clean-room on this project's stack: no Odoo code is used, only the workflow
idea (detect a cart the customer left, remind them once per stage, give them
a one-click link back to checkout).

A cart is remindable when it is ACTIVE, non-empty, owned by a user (guests
have no contact channel), and its ``last_activity_at`` has been quiet for the
current stage's window. Idempotence is two-layered: the per-(cart, stage)
``CartRecoveryAttempt`` row is written in the same transaction as the outbox
message that carries the reminder, so a retry can never double-send.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config.settings import get_settings
from app.core.security.jwt import create_recovery_token
from app.modules.cart.domain.models import (
    Cart,
    CartRecoveryAttempt,
    CartStatus,
    RecoveryChannel,
)
from app.shared.events.outbox_service import OutboxService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _storefront_url() -> str:
    return get_settings().STOREFRONT_BASE_URL.rstrip("/")


def build_recovery_url(cart_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """One-click link back into checkout for this cart."""
    token = create_recovery_token(cart_id, user_id)
    return f"{_storefront_url()}/cart/recover?token={token}"


async def find_recoverable_carts(
    db: AsyncSession,
    *,
    stage: int,
    window_minutes: int,
    limit: int,
) -> list[Cart]:
    """Carts whose owner should be reminded at ``stage`` now.

    Ordered by oldest activity first so a large backlog drains fairly, and
    capped so one run can never become an unbounded outbound-SMS burst.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(
            Cart.status == CartStatus.ACTIVE,
            Cart.user_id.is_not(None),
            Cart.last_activity_at.is_not(None),
            Cart.last_activity_at <= cutoff,
            Cart.recovery_stage == stage,
        )
        .order_by(Cart.last_activity_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    carts = list(result.scalars().all())
    return [cart for cart in carts if cart.items]


async def process_recoverable_carts(
    db: AsyncSession,
    *,
    batch_size: int | None = None,
) -> dict[str, int]:
    """Queue one reminder for every cart that has reached its next stage.

    Each stage window is measured from ``last_activity_at``; a cart advances
    at most one stage per run, and a user who edits their cart between runs
    resets the clock (they are shopping again, not abandoning).
    """
    settings = get_settings()
    if not settings.CART_RECOVERY_ENABLED:
        return {"queued": 0, "skipped": 0}

    stages = settings.CART_RECOVERY_STAGES_MINUTES
    limit = batch_size or settings.CART_RECOVERY_BATCH_SIZE
    queued = 0
    skipped = 0

    for stage, window_minutes in enumerate(stages):
        if queued >= limit:
            break
        carts = await find_recoverable_carts(
            db, stage=stage, window_minutes=window_minutes, limit=limit - queued
        )
        for cart in carts:
            try:
                did_queue = await _queue_one_reminder(db, cart=cart, stage=stage)
            except Exception:
                # One malformed cart must not stop the rest of the batch; the
                # attempt row is never written, so the next run retries it.
                skipped += 1
                await logger.aexception("cart_recovery_item_failed", cart_id=str(cart.id))
                continue
            if did_queue:
                queued += 1
            else:
                skipped += 1

    await logger.ainfo("cart_recovery_batch_done", queued=queued, skipped=skipped)
    return {"queued": queued, "skipped": skipped}


async def _queue_one_reminder(db: AsyncSession, *, cart: Cart, stage: int) -> bool:
    """Write the attempt row and its outbox message atomically.

    Returns False when another runner already claimed this (cart, stage) —
    the unique constraint on ``CartRecoveryAttempt`` makes the race a no-op
    instead of a duplicate SMS.
    """
    user_id = cart.user_id
    if user_id is None:
        return False

    subtotal = sum(item.quantity * item.price_snapshot for item in cart.items)
    item_count = sum(item.quantity for item in cart.items)
    recover_url = build_recovery_url(cart.id, user_id)
    channel = RecoveryChannel.SMS

    # Idempotence probe: a matching attempt row means a previous run already
    # queued this stage (even if its outbox message is still pending).
    exists_stmt = (
        select(func.count())
        .select_from(CartRecoveryAttempt)
        .where(
            CartRecoveryAttempt.cart_id == cart.id,
            CartRecoveryAttempt.stage == stage,
        )
    )
    if (await db.execute(exists_stmt)).scalar_one() > 0:
        return False

    attempt = CartRecoveryAttempt(
        cart_id=cart.id,
        stage=stage,
        channel=channel,
        subtotal_rial=subtotal,
        item_count=item_count,
    )
    db.add(attempt)
    await db.flush()

    await OutboxService.publish(
        db,
        event_type="CartRecoveryQueued",
        aggregate_type="cart",
        aggregate_id=str(cart.id),
        payload={
            "cart_id": str(cart.id),
            "user_id": str(user_id),
            "stage": stage,
            "channel": channel.value,
            "subtotal_rial": subtotal,
            "item_count": item_count,
            "recover_url": recover_url,
        },
        # The attempt id is the natural dedupe key for downstream retries.
        causation_id=str(attempt.id),
    )

    cart.recovery_stage = stage + 1
    await db.flush()

    await logger.ainfo(
        "cart_recovery_queued",
        cart_id=str(cart.id),
        user_id=str(user_id),
        stage=stage,
        subtotal_rial=subtotal,
    )
    return True
