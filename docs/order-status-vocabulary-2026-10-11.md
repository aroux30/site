# Order status vocabulary — WooCommerce-style, 7 states (2026-10-11)

Owner decision. The previous twelve-status chain modelled a physical store
(packing, shipping, delivery). This store is digital — 2908 digital + 2238
simple products, zero shipments — so those stages were noise. The live table
confirmed it: `delivered`, `on_hold`, `returned` and `partially_refunded` held
**zero** rows; `shipped` and `refunded` held one each, both synthetic fixtures.

## The seven statuses

| Value | Persian label | Meaning |
|---|---|---|
| `waiting_payment_gateway` | در انتظار تایید پرداخت | Order created, sent to the gateway, awaiting the callback. **Expires to `canceled` on a timeout.** |
| `waiting_payment_card` | در انتظار تایید کارت به کارت | Card-to-card receipt uploaded. **Waits for an admin forever — never expires.** |
| `pending` | در حال انجام | Paid and accepted; the operator is working on it. |
| `processing` | در حال پردازش / در انتظار بررسی | Being fulfilled / under review. |
| `completed` | تکمیل شده | Done. Terminal. |
| `canceled` | لغو شده | Terminal. |
| `refunded` | بازگشت وجه | Terminal. |

## The distinction that matters

`waiting_payment_gateway` and `waiting_payment_card` are both "waiting", but they have
**opposite expiry rules**, and that is the entire reason the vocabulary has
seven states instead of six:

- An abandoned **gateway** order holds stock forever unless something cancels
  it. The Celery sweep `cancel_stale_pending_orders` does that on a timeout.
- A **card-to-card** order means the customer's money may already be in the
  account while an admin is still looking at the receipt. Cancelling it on a
  timer would destroy a sale *and* lose the refund obligation. So it waits for
  a human, however late they get to it.

Filing one in the other's bucket is the expensive mistake this vocabulary makes
possible. It is pinned by `app/tests/unit/test_order_status_vocabulary.py`,
which reads the sweep's source and fails if `WAITING_PAYMENT_CARD` appears in a
candidate query — negative-tested by widening the filter and watching it fail.

## Transitions

```
waiting_payment_gateway ─┐                        ┌→ canceled
waiting_payment_card    ─┼→ pending → processing ─┼→ completed
                 ┘                        └→ refunded
```

`refunded` is reachable from every non-terminal state, including both
payment-waiting ones — an admin can refund an order that never got paid for.

## Storage contract

`orders.status` is a varchar-backed Enum (`native_enum=False`) and the repo's
contract is that it stores **NAMES** (`WAITING_PAYMENT_CARD`), not values
(`waiting_payment_card`). Writing lowercase values makes every subsequent
`Order.status` read raise `ValueError` — far from the cause. This bit the first
manual run of the data migration; the alembic migration now asserts against the
NAME form at the end and refuses to complete if any stray value remains
(negative-tested).

## Where the status is decided

- **Checkout** picks the opening status from the payment method:
  `_is_card_to_card(slug)` → `waiting_payment_card`, else `waiting_payment_gateway`.
  Slug matching folds case, spaces and dashes, because a silent miss here
  files an admin-gated order into the auto-expire bucket.
- **Gateway callback** (`payment_service.verify_payment`) and **admin approval**
  (`payment_service.approve_payment`, `card_transfer_service`,
  `split_tender_service`) all land on `pending`.
- **The sweep** (`orders/application/tasks.py`) touches `waiting_payment_gateway` only.

## Migration

`alembic/versions/2026_10_11_rmstatus2_woocommerce_status_vocabulary.py`
(`rmstatus2`, revises `rmpricing1`). Verified on a fresh database: the whole
chain reaches head, and a seeded `CONFIRMED` order becomes `PENDING` through a
downgrade→upgrade round trip. The downgrade is best-effort and lossy — the six
removed statuses cannot be reconstructed from the new vocabulary, only from a
backup.

Live data after the migration (29365 orders):

| status | count |
|---|---|
| `waiting_payment_gateway` | 24569 |
| `pending` | 2075 |
| `completed` | 2010 |
| `canceled` | 442 |
| `processing` | 176 |
| `waiting_payment_card` | 92 |
| `refunded` | 1 |

The 92 `waiting_payment_card` rows are the live card-to-card orders whose payment is
still `PENDING` — exactly the set that must not be swept.

## Tests

418 backend tests pass (up from 380). New:

- `test_order_status_vocabulary.py` (12) — the enum's shape, the chain, the
  sweep's scope, the slug matcher.
- `test_checkout_payment_status_flow.py` (5) — the real `admin_update_status`
  path moving both waiting states into the operator's lane, plus the
  transitions that must be refused.

## Board layout (revised 2026-10-11)

Owner decision: every status is its OWN board column — no grouping. The
previous layout collapsed `waiting_payment_gateway`, `waiting_payment_card`,
`pending` and `processing` into one «در حال پردازش» lane. The owner asked for
each status to be visible separately, so the operator sees seven columns:

| Column | Status |
|---|---|
| در انتظار تایید پرداخت | `waiting_payment_gateway` |
| در انتظار تایید کارت به کارت | `waiting_payment_card` |
| در حال انجام | `pending` |
| در حال پردازش | `processing` |
| تکمیل شده | `completed` |
| لغو شده | `canceled` |
| بازگشت وجه | `refunded` |

The settings popover still lets operators toggle each column on/off (persisted
to `localStorage["admin.orders.boardColumns"]`). The list view also shows all
seven as filter buttons — the old «بیشتر…» dropdown is gone.
