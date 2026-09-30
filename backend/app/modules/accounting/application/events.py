"""Additive outbox listener: observe money events and post journal entries.

The order / payment / refund / wallet / settlement paths themselves are NEVER
modified — this handler only consumes the events they already publish to the
transactional outbox (the same mechanism the invoicing credit-note listener
uses). It is wired into ``automation/application/outbox_worker.py`` and
returns quietly for event types it does not map.

Mapping (see ``posting_rules.py`` for the full table):

============================  ==========================================
Outbox event                  Journal entry
============================  ==========================================
``OrderCreated``              order → revenue + VAT payable
``PaymentCompleted``          payment → receivable (or wallet liability
                              for a top-up)
``ReturnRefunded``            refund → contra revenue + VAT reversal
``RefundProcessed``           refund → contra revenue + VAT reversal
``WalletWithdrawn``           wallet → bank payout
``VendorSettlementPaid``      settlement → payable cleared
``CashbackCredited``          cashback → expense + wallet liability
``LoyaltyCredited``           loyalty → expense + wallet liability
``ReferralCredited``          referral → expense + wallet liability
============================  ==========================================

**Publisher status of the three customer-credit events (verified 2026-09-25):**

- ``CashbackCredited`` — **published** by
  ``cashback_service.credit_pending_cashback``, which is the only one of the
  three that moves real money: it calls ``wallet_service.credit``. This was
  the actual gap; cashback had been crediting wallets with no journal entry.
- ``LoyaltyCredited`` / ``ReferralCredited`` — **handled but not yet
  published by anything**, because neither module pays into a wallet today.
  ``loyalty_service.redeem_points`` only decrements a points counter, and
  ``referral_service.calculate_and_credit_commission`` only writes a
  ``PENDING`` commission row (nothing in the codebase ever moves it to
  ``PAID``). The handlers exist so that the day either module starts paying
  out, the posting rule is already written and tested — not so that a reader
  mistakes them for an active feed.

Idempotency: the entry's ``(source_type, source_id, entry_type)`` triple is
unique, so outbox redelivery returns the existing entry instead of posting a
second one. A mapping failure raises — the outbox retry / dead-letter
machinery owns recovery, and the source transaction was already committed.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.modules.accounting.application import journal_service
from app.modules.accounting.application.posting_rules import (
    RuleError,
    customer_credit_lines,
    order_revenue_lines,
    payment_clearing_lines,
    purchase_order_receipt_lines,
    refund_contra_lines,
    settlement_payment_lines,
    wallet_withdrawal_lines,
)
from app.modules.accounting.domain.models import JournalEntryStatus, JournalSourceType

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_HANDLED_EVENTS = (
    "OrderCreated",
    "PaymentCompleted",
    "ReturnRefunded",
    "RefundProcessed",
    "WalletWithdrawn",
    "VendorSettlementPaid",
    "PurchaseOrderReceived",
    "CashbackCredited",
    "LoyaltyCredited",
    "ReferralCredited",
)


def is_accounting_event(event_type: str) -> bool:
    """True when this listener maps the event type to a journal entry."""
    return event_type in _HANDLED_EVENTS


def _int(value: Any) -> int:
    return max(int(value or 0), 0)


async def _payload_order_totals(db: Any, order_id: uuid.UUID) -> dict[str, int]:
    """Order header totals, with the tax observation's VAT preferred.

    The tax observation (``order_tax_observations``) is the fiscal source of
    truth captured at checkout; when it exists its ``vat_total_rial`` and
    ``grand_total_rial`` win. Otherwise the order header's own columns are
    used, so legacy orders still post.
    """
    from sqlalchemy import select

    from app.modules.checkout.domain.tax_models import OrderTaxObservation
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, order_id)
    if order is None:
        raise RuleError(f"order {order_id} not found for accounting posting")

    totals = {
        "total": _int(getattr(order, "total", 0)),
        "tax": _int(getattr(order, "tax", 0)),
        "shipping": _int(getattr(order, "shipping_cost", 0)),
    }

    obs_stmt = select(OrderTaxObservation).where(OrderTaxObservation.order_id == order_id)
    observation = (await db.execute(obs_stmt)).scalars().first()
    if observation is not None:
        if _int(observation.vat_total_rial) > 0:
            totals["tax"] = _int(observation.vat_total_rial)
        if _int(observation.grand_total_rial) > 0:
            totals["total"] = _int(observation.grand_total_rial)

    return totals


async def _post_order_revenue(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    order_id_raw = payload.get("order_id")
    if not order_id_raw:
        return {"status": "skipped", "reason": "no_order_id"}
    order_id = uuid.UUID(str(order_id_raw))

    totals = await _payload_order_totals(db, order_id)
    if totals["total"] <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    order_number = str(payload.get("order_number") or "")
    description = f"شناسایی درآمد سفارش {order_number}".strip()

    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.ORDER,
        source_id=str(order_id),
        entry_type="revenue",
        description=description,
        line_specs=order_revenue_lines(
            total_rial=totals["total"],
            tax_rial=totals["tax"],
            shipping_rial=totals["shipping"],
            description=description,
        ),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def _post_payment_clearing(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from app.modules.accounting.domain.models import JournalEntryStatus

    payment_id_raw = payload.get("payment_id")
    if not payment_id_raw:
        return {"status": "skipped", "reason": "no_payment_id"}
    payment_id = uuid.UUID(str(payment_id_raw))

    amount = _int(payload.get("amount"))
    if amount <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    order_id = payload.get("order_id")
    is_topup = not order_id
    # A wallet top-up is tagged on the payment row; when the payload carries
    # the order it is necessarily an order payment.
    if order_id:
        from app.modules.payments.domain.models import Payment

        payment = await db.get(Payment, payment_id)
        if payment is not None and (payment.extra_data or {}).get("purpose") == "wallet_topup":
            is_topup = True

    fee = _int(payload.get("fee") or payload.get("fee_rial"))
    description = (
        f"واریز به کیف پول (پرداخت {payment_id})"
        if is_topup
        else f"وصول مطالبات سفارش {order_id} (پرداخت {payment_id})"
    )

    existing = await journal_service.find_entry_by_source(
        db, source_type=JournalSourceType.PAYMENT, source_id=str(payment_id), entry_type="clearing"
    )
    if existing is not None:
        return {"status": "existing", "entry_id": str(existing.id)}

    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.PAYMENT,
        source_id=str(payment_id),
        entry_type="clearing",
        description=description,
        line_specs=payment_clearing_lines(
            amount_rial=amount, is_wallet_topup=is_topup, fee_rial=fee, description=description
        ),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def _post_refund_contra(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from app.modules.accounting.domain.models import JournalEntryStatus

    refund_amount = _int(payload.get("refund_amount") or payload.get("amount"))
    if refund_amount <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    # Stable per-refund key, mirroring the credit-note listener: the RMA id
    # when present, else the refund row id, else the outbox message id.
    refund_key = (
        payload.get("return_id")
        or payload.get("refund_id")
        or payload.get("payment_id")
        or payload.get("order_id")
    )
    if not refund_key:
        return {"status": "skipped", "reason": "no_source_key"}

    order_id = payload.get("order_id")
    # VAT reversal: proportional share of the order's VAT when the order is
    # known, capped at the refunded amount (integer Rial, floor division).
    vat_share = 0
    if order_id:
        try:
            totals = await _payload_order_totals(db, uuid.UUID(str(order_id)))
            if totals["total"] > 0 and totals["tax"] > 0:
                vat_share = min(totals["tax"] * refund_amount // totals["total"], refund_amount)
        except RuleError:
            vat_share = 0

    to_wallet = bool(payload.get("to_wallet"))
    description = f"برگشت وجه (مرجع {refund_key})"

    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.REFUND,
        source_id=str(refund_key),
        entry_type="contra",
        description=description,
        line_specs=refund_contra_lines(
            refund_rial=refund_amount,
            tax_rial=vat_share,
            to_wallet=to_wallet,
            description=description,
        ),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def _post_wallet_withdrawal(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from app.modules.accounting.domain.models import JournalEntryStatus

    amount = _int(payload.get("amount") or payload.get("amount_rial"))
    if amount <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    source_key = payload.get("wallet_transaction_id") or payload.get("transaction_id")
    if not source_key:
        return {"status": "skipped", "reason": "no_source_key"}

    description = f"برداشت از کیف پول (تراکنش {source_key})"
    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.WALLET,
        source_id=str(source_key),
        entry_type="withdrawal",
        description=description,
        line_specs=wallet_withdrawal_lines(amount_rial=amount, description=description),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def _post_settlement(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from app.modules.accounting.domain.models import JournalEntryStatus

    amount = _int(payload.get("amount") or payload.get("amount_rial"))
    if amount <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    source_key = payload.get("settlement_id")
    if not source_key:
        return {"status": "skipped", "reason": "no_settlement_id"}

    description = f"تسویه با فروشنده (سند {source_key})"
    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.SETTLEMENT,
        source_id=str(source_key),
        entry_type="settlement",
        description=description,
        line_specs=settlement_payment_lines(amount_rial=amount, description=description),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def _post_customer_credit(
    db: Any, payload: dict[str, Any], *, scheme: str
) -> dict[str, Any]:
    """A credit scheme paid into a wallet → expense + wallet liability.

    Closes the gap this listener used to have: cashback, loyalty points and
    referral commissions all move money into a customer wallet through
    ``wallet_service.credit``, which writes the wallet ledger but publishes no
    event. Accounting therefore never saw them, and its wallet-liability
    balance drifted from the sum of wallet balances by the total credited
    through these schemes — silently, because nothing compares the two.
    """
    amount = _int(payload.get("amount") or payload.get("amount_rial"))
    if amount <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    source_key = (
        payload.get(f"{scheme}_transaction_id")
        or payload.get("transaction_id")
        or payload.get("source_id")
    )
    if not source_key:
        return {"status": "skipped", "reason": "no_source_key"}

    labels = {
        "cashback": "کش‌بک",
        "loyalty": "امتیاز باشگاه مشتریان",
        "referral": "کمیسیون معرفی",
    }
    description = f"واریز {labels.get(scheme, scheme)} به کیف پول (سند {source_key})"

    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.WALLET,
        source_id=f"{scheme}:{source_key}",
        entry_type="customer_credit",
        description=description,
        line_specs=customer_credit_lines(
            scheme=scheme, amount_rial=amount, description=description
        ),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def _post_purchase_order_receipt(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    po_id_raw = payload.get("po_id")
    if not po_id_raw:
        return {"status": "skipped", "reason": "no_po_id"}

    amount = _int(payload.get("amount") or payload.get("total_amount_rial") or payload.get("amount_rial"))
    if amount <= 0:
        return {"status": "skipped", "reason": "zero_amount"}

    po_number = str(payload.get("po_number") or "")
    description = f"رسید انبار سفارش خرید {po_number}".strip()

    entry, created = await journal_service.create_entry(
        db,
        source_type=JournalSourceType.PURCHASE,
        source_id=str(po_id_raw),
        entry_type="purchase_receipt",
        description=description,
        line_specs=purchase_order_receipt_lines(amount_rial=amount, description=description),
        status=JournalEntryStatus.POSTED,
    )
    return {"status": "posted" if created else "existing", "entry_id": str(entry.id)}


async def handle_accounting_event(
    db: Any,
    *,
    event_type: str,
    payload: dict[str, Any],
    message_id: str | None = None,
) -> dict[str, Any] | None:
    """Map an outbox event to a journal entry (idempotent per source).

    Returns ``None`` for unmapped event types so the caller can ignore them
    silently. Raises on a real failure so the outbox retries.
    """
    if not is_accounting_event(event_type):
        return None

    try:
        if event_type == "OrderCreated":
            result = await _post_order_revenue(db, payload)
        elif event_type == "PaymentCompleted":
            result = await _post_payment_clearing(db, payload)
        elif event_type in ("ReturnRefunded", "RefundProcessed"):
            result = await _post_refund_contra(db, payload)
        elif event_type == "WalletWithdrawn":
            result = await _post_wallet_withdrawal(db, payload)
        elif event_type == "CashbackCredited":
            result = await _post_customer_credit(db, payload, scheme="cashback")
        elif event_type == "LoyaltyCredited":
            result = await _post_customer_credit(db, payload, scheme="loyalty")
        elif event_type == "ReferralCredited":
            result = await _post_customer_credit(db, payload, scheme="referral")
        elif event_type == "PurchaseOrderReceived":
            result = await _post_purchase_order_receipt(db, payload)
        else:  # VendorSettlementPaid
            result = await _post_settlement(db, payload)
    except RuleError as exc:
        # A rule that cannot balance is a *rule* bug, not a data problem:
        # log loudly and re-raise so the outbox dead-letters it for an admin.
        await logger.aerror(
            "accounting_rule_failed",
            event_type=event_type,
            message_id=message_id,
            error=str(exc),
        )
        raise

    await logger.ainfo(
        "accounting_event_posted",
        event_type=event_type,
        message_id=message_id,
        result=result,
    )
    return result
