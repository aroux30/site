"""Card-to-card manual transfer and receipt verification service (Karta Phase 3/5).

Implements:
- Buyer receipt submission with tracking reference and source card last 4 digits (Karta card2card)
- Immediate financial admin alert logging (Karta card2card_alert)
- Admin review, approval, and order state transition
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.payments.domain.fintech_models import (
    CardTransferReceipt,
    ReceiptReviewStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def submit_card_transfer_receipt(
    db: AsyncSession,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    amount: int,
    tracking_code: str,
    source_card_last4: str,
    destination_card_number: str | None = None,
    receipt_image_url: str | None = None,
) -> CardTransferReceipt:
    """Submit a manual payment receipt for admin review."""
    safe_order_id = uuid.UUID(str(order_id))
    safe_user_id = uuid.UUID(str(user_id))

    # Ownership guard: receipts may only be attached to the caller's own
    # orders, and the order must actually exist.
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, safe_order_id)
    if order is None or order.user_id != safe_user_id:
        raise NotFoundError(resource="Order")

    clean_track = tracking_code.strip()
    if not clean_track:
        raise ValidationError("شماره پیگیری واریز الزامی است")

    clean_last4 = source_card_last4.strip()
    if len(clean_last4) != 4 or not clean_last4.isdigit():
        raise ValidationError("۴ رقم آخر کارت مبدا باید دقیقاً ۴ رقم عددی باشد")

    receipt = CardTransferReceipt(
        order_id=safe_order_id,
        user_id=safe_user_id,
        amount=amount,
        tracking_code=clean_track,
        source_card_last4=clean_last4,
        destination_card_number=destination_card_number,
        receipt_image_url=receipt_image_url,
        status=ReceiptReviewStatus.PENDING_REVIEW,
    )
    db.add(receipt)
    await db.flush()

    await logger.awarning(
        "card2card_receipt_submitted",
        receipt_id=str(receipt.id),
        order_id=str(safe_order_id),
        user_id=str(safe_user_id),
        amount=amount,
        tracking_code=clean_track,
    )

    return receipt


async def review_card_transfer_receipt(
    db: AsyncSession,
    receipt_id: uuid.UUID,
    reviewed_by: uuid.UUID,
    is_approved: bool,
    admin_notes: str | None = None,
) -> CardTransferReceipt:
    """Admin review of a card-to-card transfer receipt."""
    safe_receipt_id = uuid.UUID(str(receipt_id))
    safe_admin_id = uuid.UUID(str(reviewed_by))

    receipt = await db.get(CardTransferReceipt, safe_receipt_id)
    if receipt is None:
        raise NotFoundError(
            resource="CardTransferReceipt",
            detail=f"Receipt {safe_receipt_id} not found",
        )

    if receipt.status != ReceiptReviewStatus.PENDING_REVIEW:
        raise ConflictError(detail=f"این رسید قبلاً تعیین وضعیت شده است: {receipt.status.value}")

    receipt.status = ReceiptReviewStatus.APPROVED if is_approved else ReceiptReviewStatus.REJECTED
    receipt.admin_notes = admin_notes
    receipt.reviewed_by = safe_admin_id
    receipt.reviewed_at = datetime.now(UTC)

    await db.flush()
    await logger.ainfo(
        "card2card_receipt_reviewed",
        receipt_id=str(safe_receipt_id),
        approved=is_approved,
        admin_id=str(safe_admin_id),
    )

    return receipt


async def list_receipts_by_order(
    db: AsyncSession,
    order_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[CardTransferReceipt]:
    """List transfer receipts submitted for an order.

    When ``user_id`` is supplied (customer endpoint) the order must belong
    to that user; admin callers pass ``user_id=None`` behind a permission
    dependency.
    """
    safe_order_id = uuid.UUID(str(order_id))
    if user_id is not None:
        from app.modules.orders.domain.models import Order

        order = await db.get(Order, safe_order_id)
        if order is None or order.user_id != user_id:
            raise NotFoundError(resource="Order")
    stmt = (
        select(CardTransferReceipt)
        .where(CardTransferReceipt.order_id == safe_order_id)
        .order_by(CardTransferReceipt.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
