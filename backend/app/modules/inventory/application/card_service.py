"""Digital card stock management, atomic allocation, and delivery (Karta Phase 1/2).

Implements:
- Atomic card allocation with SELECT FOR UPDATE (Karta checkOrderCardsAgain & markCards)
- Customer decrypted card retrieval
- Legal reading timestamp tracking (Karta reading flag)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.inventory.application.crypto_service import decrypt_pin
from app.modules.inventory.domain.digital_models import (
    DigitalCard,
    DigitalCardStatus,
    DigitalDeliveryType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def allocate_cards_for_order(
    db: AsyncSession,
    product_id: uuid.UUID,
    order_id: uuid.UUID,
    quantity: int,
) -> list[DigitalCard]:
    """Atomically allocate digital cards to an order upon verified payment."""
    if quantity <= 0:
        raise ValidationError("Quantity to allocate must be positive")

    now = datetime.now(UTC)

    # 1. Lock available UNIQUE cards
    unique_stmt = (
        select(DigitalCard)
        .where(
            DigitalCard.product_id == product_id,
            DigitalCard.status == DigitalCardStatus.AVAILABLE,
            DigitalCard.delivery_type == DigitalDeliveryType.UNIQUE,
            (DigitalCard.expire_at.is_(None)) | (DigitalCard.expire_at > now),
        )
        .order_by(DigitalCard.created_at.asc())
        .limit(quantity)
        .with_for_update()
    )
    unique_cards = list((await db.execute(unique_stmt)).scalars().all())

    allocated: list[DigitalCard] = []

    for card in unique_cards:
        card.status = DigitalCardStatus.DELIVERED
        card.assigned_order_id = order_id
        card.used_count += 1
        card.used_at = now
        allocated.append(card)

    remaining_needed = quantity - len(allocated)

    # 2. If needed, allocate from available SHARED capacity
    if remaining_needed > 0:
        shared_stmt = (
            select(DigitalCard)
            .where(
                DigitalCard.product_id == product_id,
                DigitalCard.status == DigitalCardStatus.AVAILABLE,
                DigitalCard.delivery_type == DigitalDeliveryType.SHARED,
                DigitalCard.used_count < DigitalCard.max_uses,
                (DigitalCard.expire_at.is_(None)) | (DigitalCard.expire_at > now),
            )
            .order_by(DigitalCard.created_at.asc())
            .with_for_update()
        )
        shared_cards = list((await db.execute(shared_stmt)).scalars().all())

        for card in shared_cards:
            if remaining_needed <= 0:
                break
            available_slots = card.max_uses - card.used_count
            slots_to_take = min(available_slots, remaining_needed)

            card.used_count += slots_to_take
            card.assigned_order_id = order_id
            card.used_at = now
            if card.used_count >= card.max_uses:
                card.status = DigitalCardStatus.DELIVERED

            allocated.append(card)
            remaining_needed -= slots_to_take

    if len(allocated) < quantity:
        raise ConflictError(
            detail=(
                f"Insufficient digital stock for product {product_id}: "
                f"requested {quantity}, but only {len(allocated)} available"
            )
        )

    await db.flush()
    await logger.ainfo(
        "digital_cards_allocated",
        order_id=str(order_id),
        product_id=str(product_id),
        allocated_count=len(allocated),
    )
    return allocated


async def get_delivered_cards_for_order(
    db: AsyncSession,
    order_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Fetch and decrypt PINs for cards assigned to an order (customer view)."""
    stmt = (
        select(DigitalCard)
        .where(DigitalCard.assigned_order_id == order_id)
        .order_by(DigitalCard.created_at.asc())
    )
    cards = list((await db.execute(stmt)).scalars().all())

    result = []
    for card in cards:
        decrypted = decrypt_pin(card.pin_ciphertext)
        result.append(
            {
                "id": card.id,
                "serial_number": card.serial_number,
                "pin": decrypted,
                "delivery_type": card.delivery_type,
                "file_download_url": card.file_path,
                "delivered_at": card.used_at,
                "reading_at": card.reading_at,
            }
        )
    return result


async def mark_card_viewed(
    db: AsyncSession,
    card_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> DigitalCard:
    """Record timestamp when customer first views the decrypted PIN (legal evidence).

    When ``user_id`` is supplied the card must belong to an order owned by
    that user, otherwise the card is reported as not found.
    """
    card = await db.get(DigitalCard, card_id, with_for_update=True)
    if card is None:
        raise NotFoundError(resource="DigitalCard", detail=f"Card {card_id} not found")

    if user_id is not None:
        from app.modules.orders.domain.models import Order

        order = (
            await db.get(Order, card.assigned_order_id)
            if card.assigned_order_id is not None
            else None
        )
        if order is None or order.user_id != user_id:
            raise NotFoundError(resource="DigitalCard", detail=f"Card {card_id} not found")

    if card.reading_at is None:
        card.reading_at = datetime.now(UTC)
        await db.flush()
        await logger.ainfo(
            "digital_card_read",
            card_id=str(card_id),
            at=card.reading_at.isoformat(),
        )

    return card
