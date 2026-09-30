# Payment Reconciliation Runbook

Operational procedures for the failure cases in the payment lifecycle. The system
is designed so that **the server owns payment truth** — every recovery path below
goes through server-side verification, never through client claims.

---

## Lifecycle reference

```text
Order (PENDING) → Payment (PENDING) → Gateway
    → callback/webhook → verify_payment (row-locked, authority-pinned, amount-checked)
    → Payment COMPLETED → Order CONFIRMED (state machine)
```

Guards in place (do not weaken):

- `create_payment` locks the order row and refuses when a live payment already exists
  (one live payment per order; retries only after FAILED).
- `verify_payment` re-verifies with the gateway server-side; authority is pinned to the
  payment; a canceled/returned/refunded order can never accept a completion.
- Webhook events are deduplicated via the `PaymentWebhookEvent` replay table.
- Auto-cancel of stale PENDING orders **skips** any order with a live payment attempt
  (`stale_order_skipped_payment_in_flight` log event).

---

## Case 1 — Customer paid at the gateway, callback/redirect lost

**Detection:** a PENDING order older than `ORDER_PAYMENT_TIMEOUT_MINUTES` (60) with a
PENDING/PROCESSING payment attempt logs `stale_order_skipped_payment_in_flight` from
`cancel_stale_pending_orders` (worker log / Alertmanager).

**Impact:** inventory stays committed for that order (bounded — see recovery). No money
is lost, no order is wrongly canceled.

**Recovery (in order of preference):**

1. **Wait for retry sources:** the gateway callback URL stays valid; NowPayments
   webhooks are retried by the provider and deduplicated by the replay table.
2. **Admin verify:** re-run the server verify for the payment
   (`POST /api/v1/payments/{payment_id}/verify` with the gateway authority, admin
   session) — the order is still PENDING, so completion succeeds and the state machine
   confirms the order.
3. **Gateway refund:** if the customer requests cancellation instead, refund at the
   gateway dashboard and mark the payment FAILED via the admin refund endpoint.

## Case 2 — Gateway says success, local verify says failure/tampered

**Detection:** verify response mismatch (`zarinpal_refund_manual_required` /
underpayment-guard log events). The payment stays PENDING; the order stays PENDING.

**Recovery:** manual review — compare gateway dashboard amount vs. `payments.amount`
(crypto has a 1% underpayment tolerance; below tolerance the payment fails closed).
Refund at the gateway, then mark the payment FAILED (admin), which frees the customer
to retry (new payment on the same still-PENDING order).

## Case 3 — Payment COMPLETED but order confirmation crashed

**Detection:** `PaymentCompleted` outbox event with no `OrderConfirmed`; or a COMPLETED
payment whose order is still PENDING (admin payments view).

**Recovery:** safe to re-run — completion and order confirmation run in one transaction
(payment row locked; wallet debit/credit atomic). Re-invoking verify is idempotent for
an already-COMPLETED payment (returns the existing result without double-charging).
If the outbox row is stuck, `process_outbox_queue` (beat, every minute) drains it; the
worker logs `outbox` failures per event.

## Case 4 — Wallet credit/debit succeeded but the ledger diverges

**Detection:** `reconcile_wallet_balances` (beat) compares each wallet balance to its
signed transaction ledger and logs `wallet_reconcile_drifted_wallets` with the count.

**Recovery:** the task re-syncs the balance from the ledger (the ledger is the source
of truth). Investigate the triggering transaction before trusting the corrected balance
during a live incident; `wallet_transactions.reference_type/reference_id` ties every
entry to its business cause.

## Case 5 — Auto-cancel skipped an order forever (customer never returns)

**Detection:** PENDING orders with live payments older than several days.

**Recovery:** admin decision — either verify (if the gateway shows success) or mark the
payment FAILED and let the normal auto-cancel pick the order up on the next run
(restock is idempotent and dedupes per variant).

---

## What is intentionally NOT automated

- **Gateway inquiry sweeps** (polling providers for the status of every PENDING
  payment): provider APIs are heterogeneous and none expose a uniform inquiry endpoint
  in this codebase. Introduce only with provider-specific evidence.
- **Auto-refund on timeout:** refunds are money movement; they require the explicit
  Case-5 admin decision above.
