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

    from app.modules.payments.domain.models import Payment

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
    """Admin review of a card-to-card transfer receipt.

    Karta ``admin/Orders::saveStatus`` semantics (P1.3): approval completes
    the linked pending ``card_transfer`` payment (which transitions the
    order to CONFIRMED); rejection fails that payment. The receipt row and
    the payment lifecycle are one flow — never two parallel truths.
    """
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

    from app.modules.payments.application import payment_service

    payment = await _find_pending_c2c_payment(db, receipt.order_id)
    if payment is not None:
        if is_approved:
            await payment_service.approve_payment(
                db,
                payment_id=payment.id,
                admin_user_id=safe_admin_id,
            )
        else:
            await payment_service.reject_payment(
                db,
                payment_id=payment.id,
                admin_user_id=safe_admin_id,
                reason=admin_notes or "کارت به کارت توسط مدیر مالی رد شد",
            )
    elif is_approved:
        # Receipt-only flow: no gateway payment row exists yet. Mirror the
        # legacy behavior — admin acceptance means the order is paid.
        from app.modules.orders.domain.models import Order, OrderStatus

        order = await db.get(Order, receipt.order_id)
        if order is not None and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CONFIRMED
            await logger.ainfo(
                "card2card_order_confirmed_without_payment_row",
                order_id=str(order.id),
                admin_id=str(safe_admin_id),
            )
    else:
        await logger.ainfo(
            "card2card_receipt_rejected_without_payment_row",
            receipt_id=str(safe_receipt_id),
            admin_id=str(safe_admin_id),
        )

    await db.flush()
    await logger.ainfo(
        "card2card_receipt_reviewed",
        receipt_id=str(safe_receipt_id),
        approved=is_approved,
        admin_id=str(safe_admin_id),
        payment_linked=payment is not None,
    )

    return receipt


async def _find_pending_c2c_payment(
    db: AsyncSession,
    order_id: uuid.UUID,
) -> Payment | None:
    """Find the newest pending card-transfer payment for an order."""
    from app.modules.payments.domain.models import Payment, PaymentProvider, PaymentStatus

    stmt = (
        select(Payment)
        .where(
            Payment.order_id == order_id,
            Payment.provider == PaymentProvider.CARD_TRANSFER,
            Payment.status == PaymentStatus.PENDING,
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def list_receipts_for_admin(
    db: AsyncSession,
    status: ReceiptReviewStatus | None = None,
    limit: int = 100,
) -> list[CardTransferReceipt]:
    """List submitted transfer receipts for the admin panel (P1.3)."""
    stmt = select(CardTransferReceipt).order_by(CardTransferReceipt.created_at.desc())
    if status is not None:
        stmt = stmt.where(CardTransferReceipt.status == status)
    stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())


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
