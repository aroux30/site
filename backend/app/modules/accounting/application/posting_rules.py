"""Documented posting rules: domain event → balanced journal lines.

This module is **pure**: it takes an event payload plus the resolved account
ids and returns line specs (account code, debit, credit, description). It does
no I/O, so every rule is unit-testable and the mapping table below is the
single source of truth.

┌──────────────────────┬───────────────────────────────────────────────────────────────────────────────────┬──────────────────────────────────────────┐
│ Event (source)       │ Debit                                                                              │ Credit                                    │
├──────────────────────┼───────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ OrderCreated (order) │ حسابهای دریافتنی تجاری (1003) = order total                                        │ فروش کالا (4001) = total − VAT − shipping │
│                      │                                                                                    │ درآمد حمل (4004) = shipping               │
│                      │                                                                                    │ مالیات بر ارزش افزوده پرداختنی (2002) = VAT│
├──────────────────────┼───────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ PaymentCompleted     │ حساب واسط درگاه (1005), یا بانک (1002) وقتی کارمزدی گزارش نشده                        │ حسابهای دریافتنی (1003)                  │
│ (payment)            │ کارمزد درگاه (5002) = fee (فقط وقتی fee > 0)                                         │ حساب واسط درگاه (1005) = fee              │
│                      │                                                                                    │ یا کیف پول کاربران (2003) برای شارژ کیف پول│
├──────────────────────┼───────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ ReturnRefunded /     │ برگشت فروش (4002) = refund − VAT                                                     │ بانک (1002) یا کیف پول کاربران (2003)      │
│ RefundProcessed      │ مالیات بر ارزش افزوده پرداختنی (2002) = VAT (وقتی > 0)                                 │ = refund (کل مبلغ بازگشتی)                 │
│ (refund)             │                                                                                    │                                          │
├──────────────────────┼───────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ WalletWithdrawn      │ کیف پول کاربران (2003) = amount                                                     │ بانک (1002) = amount                     │
│ (wallet)             │                                                                                    │                                          │
├──────────────────────┼───────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ VendorSettlementPaid │ حسابهای پرداختنی تجاری (2001) = amount                                              │ بانک (1002) = amount                     │
│ (settlement)         │                                                                                    │                                          │
├──────────────────────┼───────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ Manual (manual)      │ admin-specified                                                                     │ admin-specified (must balance)           │
└──────────────────────┴───────────────────────────────────────────────────────────────────────────────────┴──────────────────────────────────────────┘

Two invariants every rule must uphold (enforced by ``journal_service`` and the
DB check constraints):

1. ``sum(debit) == sum(credit)`` — an unbalanced entry is rejected outright.
2. Each line has exactly one non-zero side; both sides are positive integers
   in Rial (never float, never a negative amount).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LineSpec:
    """One side of one account movement, before the account id is resolved."""

    account_code: str
    debit_rial: int = 0
    credit_rial: int = 0
    description: str | None = None


class RuleError(Exception):
    """A rule could not be applied (missing/zero amounts, unknown source)."""


def _int(value: Any) -> int:
    """Coerce a payload figure to a non-negative integer Rial amount."""
    if value is None:
        return 0
    return max(int(value), 0)


def _balanced(lines: list[LineSpec]) -> list[LineSpec]:
    """Drop zero-amount lines; raise if the remainder does not balance.

    A rule that cannot balance is a *rule* bug, so this raises instead of
    silently dropping a side — the caller (the outbox listener) lets the
    outbox retry/dead-letter machinery own it.
    """
    kept = [ln for ln in lines if ln.debit_rial or ln.credit_rial]
    debit = sum(ln.debit_rial for ln in kept)
    credit = sum(ln.credit_rial for ln in kept)
    if not kept or debit != credit:
        raise RuleError(f"posting rule produced an unbalanced entry: debit={debit} credit={credit}")
    return kept


# ── Order → revenue ──────────────────────────────────────────────────────────


def order_revenue_lines(
    *,
    total_rial: int,
    tax_rial: int,
    shipping_rial: int = 0,
    description: str | None = None,
) -> list[LineSpec]:
    """Order placed → debit receivable, credit revenue + shipping + VAT payable.

    The receivable is the gross amount the customer owes (``total_rial``).
    The order header already carries discounts inside ``total``
    (``total = subtotal - discount + shipping + tax``), so revenue is simply
    the non-VAT, non-shipping remainder:

        revenue = total - shipping - vat

    Shipping is recognised separately as a revenue account (it is income, not
    a reduction of goods revenue), and the VAT portion is a liability.
    """
    from app.modules.accounting.application.account_seed import (
        RECEIVABLE,
        SALES_REVENUE,
        SHIPPING_REVENUE,
        VAT_PAYABLE,
    )

    total = _int(total_rial)
    vat = min(_int(tax_rial), total)
    shipping = min(_int(shipping_rial), total - vat)
    revenue = total - vat - shipping

    lines = [LineSpec(RECEIVABLE, debit_rial=total, description=description)]
    if revenue:
        lines.append(LineSpec(SALES_REVENUE, credit_rial=revenue, description=description))
    if shipping:
        lines.append(LineSpec(SHIPPING_REVENUE, credit_rial=shipping, description=description))
    if vat:
        lines.append(LineSpec(VAT_PAYABLE, credit_rial=vat, description=description))

    return _balanced(lines)


# ── Payment → clearing ───────────────────────────────────────────────────────


def payment_clearing_lines(
    *,
    amount_rial: int,
    is_wallet_topup: bool = False,
    fee_rial: int = 0,
    description: str | None = None,
) -> list[LineSpec]:
    """Payment captured → debit bank/PSP clearing, credit receivable.

    A wallet top-up has no order behind it: the credit side is the wallet
    liability account (money the platform now owes the user) instead of the
    receivable. A reported gateway fee is expensed against the same clearing
    account in the same entry.
    """
    from app.modules.accounting.application.account_seed import (
        BANK,
        GATEWAY_FEE_EXPENSE,
        PSP_CLEARING,
        RECEIVABLE,
        WALLET_LIABILITY,
    )

    amount = _int(amount_rial)
    if amount <= 0:
        raise RuleError("payment rule requires a positive amount")

    credit_account = WALLET_LIABILITY if is_wallet_topup else RECEIVABLE
    lines = [
        LineSpec(PSP_CLEARING if fee_rial else BANK, debit_rial=amount, description=description),
        LineSpec(credit_account, credit_rial=amount, description=description),
    ]

    fee = _int(fee_rial)
    if fee:
        # The PSP remits the gross amount and charges its fee separately, so
        # the fee is an expense against the clearing account, not a reduction
        # of the clearing debit (which must equal the payment amount).
        lines.append(LineSpec(GATEWAY_FEE_EXPENSE, debit_rial=fee, description=description))
        lines.append(LineSpec(PSP_CLEARING, credit_rial=fee, description=description))

    return _balanced(lines)


# ── Refund → contra revenue ──────────────────────────────────────────────────


def refund_contra_lines(
    *,
    refund_rial: int,
    tax_rial: int = 0,
    to_wallet: bool = False,
    description: str | None = None,
) -> list[LineSpec]:
    """Refund / credit note → debit returns + VAT reversal, credit bank/wallet.

    The reversal mirrors :func:`order_revenue_lines`: the returned goods debit
    ``برگشت فروش`` for the non-VAT portion and debit ``مالیات پرداختنی`` for
    the VAT portion, while the money leaves the bank (or the wallet, for a
    wallet-credited refund — a wallet credit never touches a bank account).
    """
    from app.modules.accounting.application.account_seed import (
        BANK,
        SALES_RETURNS,
        VAT_PAYABLE,
        WALLET_LIABILITY,
    )

    amount = _int(refund_rial)
    if amount <= 0:
        raise RuleError("refund rule requires a positive amount")

    vat = min(_int(tax_rial), amount)
    net = amount - vat
    credit_account = WALLET_LIABILITY if to_wallet else BANK

    lines = [
        LineSpec(SALES_RETURNS, debit_rial=net, description=description),
        LineSpec(credit_account, credit_rial=amount, description=description),
    ]
    if vat:
        lines.append(LineSpec(VAT_PAYABLE, debit_rial=vat, description=description))

    return _balanced(lines)


# ── Wallet withdrawal ────────────────────────────────────────────────────────


def wallet_withdrawal_lines(*, amount_rial: int, description: str | None = None) -> list[LineSpec]:
    """Wallet withdrawal paid out → debit wallet liability, credit bank."""
    from app.modules.accounting.application.account_seed import BANK, WALLET_LIABILITY

    amount = _int(amount_rial)
    if amount <= 0:
        raise RuleError("withdrawal rule requires a positive amount")
    return _balanced(
        [
            LineSpec(WALLET_LIABILITY, debit_rial=amount, description=description),
            LineSpec(BANK, credit_rial=amount, description=description),
        ]
    )


# ── Vendor settlement paid ───────────────────────────────────────────────────


def settlement_payment_lines(
    *, amount_rial: int, description: str | None = None
) -> list[LineSpec]:
    """Vendor settlement paid → debit payable, credit bank."""
    from app.modules.accounting.application.account_seed import BANK, PAYABLE

    amount = _int(amount_rial)
    if amount <= 0:
        raise RuleError("settlement rule requires a positive amount")
    return _balanced(
        [
            LineSpec(PAYABLE, debit_rial=amount, description=description),
            LineSpec(BANK, credit_rial=amount, description=description),
        ]
    )


# ── Purchase order received ──────────────────────────────────────────────────


def purchase_order_receipt_lines(
    *, amount_rial: int, description: str | None = None
) -> list[LineSpec]:
    """Goods receipt on purchase order → debit inventory asset, credit accounts payable."""
    from app.modules.accounting.application.account_seed import INVENTORY, PAYABLE

    amount = _int(amount_rial)
    if amount <= 0:
        raise RuleError("purchase order receipt rule requires a positive amount")
    return _balanced(
        [
            LineSpec(INVENTORY, debit_rial=amount, description=description),
            LineSpec(PAYABLE, credit_rial=amount, description=description),
        ]
    )


# ── Reversal ─────────────────────────────────────────────────────────────────


def mirror_lines(lines: list[Any]) -> list[LineSpec]:
    """Swap debit/credit of every line — the body of a reversal entry.

    A reversal is always a *new* entry that mirrors the original: the two
    entries sum to zero and the original stays untouched (posted entries are
    immutable fiscal records). Callers must pass lines whose ``account``
    relationship is loaded.
    """
    mirrored: list[LineSpec] = []
    for line in lines:
        account = getattr(line, "account", None)
        code = getattr(account, "code", None)
        if not isinstance(code, str):  # pragma: no cover - defensive
            raise RuleError("cannot mirror a line whose account relationship is not loaded")
        mirrored.append(
            LineSpec(
                account_code=code,
                debit_rial=int(getattr(line, "credit_rial", 0) or 0),
                credit_rial=int(getattr(line, "debit_rial", 0) or 0),
                description=getattr(line, "description", None),
            )
        )
    return mirrored


# ── Customer credit schemes (cashback / loyalty / referral) ──────────────────

#: Scheme name → the name of the expense account constant its credit posts
#: against. Stored as the constant's *name* because the code is imported
#: inside the function (the module avoids a circular import at module level —
#: see the other rules below).
CREDIT_SCHEME_ACCOUNT_NAMES: dict[str, str] = {
    "cashback": "CASHBACK_EXPENSE",
    "loyalty": "LOYALTY_EXPENSE",
    "referral": "REFERRAL_EXPENSE",
}


def customer_credit_lines(
    *, scheme: str, amount_rial: int, description: str | None = None
) -> list[LineSpec]:
    """A credit scheme paid into a customer's wallet.

    Debit the scheme's expense account, credit the wallet liability. The
    platform now owes the customer that money, and it has cost the platform
    that money — which is exactly what the two sides say.

    Before this rule existed, the wallet ledger recorded the movement and the
    general ledger did not, so the wallet liability in accounting drifted away
    from the sum of wallet balances with every cashback payout. Nothing failed
    when that happened; the two figures simply disagreed.
    """
    from app.modules.accounting.application.account_seed import (
        WALLET_LIABILITY,
    )

    account_name = CREDIT_SCHEME_ACCOUNT_NAMES.get(scheme)
    if account_name is None:
        raise RuleError(
            f"unknown customer-credit scheme '{scheme}' "
            f"(expected one of: {', '.join(sorted(CREDIT_SCHEME_ACCOUNT_NAMES))})"
        )

    # Imported here, not at module level, to match the other rules and keep
    # account_seed free of a dependency on this module.
    from app.modules.accounting.application import account_seed

    account_code = getattr(account_seed, account_name)

    amount = _int(amount_rial)
    if amount <= 0:
        raise RuleError("customer-credit rule requires a positive amount")

    return _balanced(
        [
            LineSpec(account_code, debit_rial=amount, description=description),
            LineSpec(WALLET_LIABILITY, credit_rial=amount, description=description),
        ]
    )


# Rule discriminator per source type — the second half of the per-source
# uniqueness key on journal entries.
ENTRY_TYPES = {
    "order_revenue": "revenue",
    "payment_clearing": "clearing",
    "refund_contra": "contra",
    "wallet_withdrawal": "withdrawal",
    "settlement_payment": "settlement",
    "customer_credit": "customer_credit",
    "manual": "manual",
    "reversal": "reversal",
}
