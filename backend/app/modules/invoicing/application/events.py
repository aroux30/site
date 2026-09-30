"""Additive outbox listener: observe refund events and issue credit notes.

The refund paths themselves are NEVER modified — this handler only consumes
the events they already publish to the transactional outbox:

- ``ReturnRefunded``  (RMA terminal refund, orders/order_service.py)
- ``RefundProcessed`` (customer cancel / admin refund wallet settlements)

Idempotency: each event carries a stable key (RMA id, or order id +
initiator) that feeds the credit note's idempotency key, so outbox retries
never create duplicate notes. Failures raise so the outbox retry/dead-letter
machinery owns recovery.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.modules.invoicing.application import invoice_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_HANDLED_EVENTS = ("ReturnRefunded", "RefundProcessed")


def is_refund_event(event_type: str) -> bool:
    return event_type in _HANDLED_EVENTS


async def handle_refund_event(
    db: Any,
    *,
    event_type: str,
    payload: dict[str, Any],
    message_id: str | None = None,
) -> None:
    """Issue (idempotently) a credit note for a completed refund event."""
    if not is_refund_event(event_type):
        return

    order_id_raw = payload.get("order_id")
    if not order_id_raw:
        return
    order_id = uuid.UUID(str(order_id_raw))

    amount = int(payload.get("refund_amount") or payload.get("amount") or 0)
    if amount <= 0:
        await logger.awarning(
            "credit_note_skipped_no_amount", event_type=event_type, order_id=str(order_id)
        )
        return

    # Stable per-refund key: the RMA id when present, else the order +
    # initiator + amount (outbox message id as last resort so retries of the
    # SAME message still dedupe).
    event_key = (
        str(payload.get("return_id"))
        if payload.get("return_id")
        else f"{payload.get('initiated_by', 'refund')}:{message_id or 'direct'}"
    )

    reason = (
        f"بازگشت وجه مرجوعی (RMA {payload['return_id']})"
        if payload.get("return_id")
        else "بازگشت وجه سفارش"
    )

    note, created = await invoice_service.issue_credit_note_for_refund(
        db,
        order_id=order_id,
        refund_amount=amount,
        reason=reason,
        event_key=event_key,
    )
    await logger.ainfo(
        "refund_event_credit_note",
        event_type=event_type,
        order_id=str(order_id),
        credit_note_id=str(note.id),
        created=created,
    )
