"""WooCommerce-style order status vocabulary (7 states).

Owner decision 2026-10-11: the store is digital, so the twelve-status chain
that modelled packing and shipping was noise. This migration rewrites both the
data and the declared vocabulary.

Data mapping (measured against the live table, 29365 orders):

    PENDING          → waiting_payment_gateway   24661  unpaid gateway orders
    CONFIRMED        → pending                    2075  paid, awaiting an operator
    PROCESSING       → processing                  176
    COMPLETED        → completed                  2009
    CANCELED         → canceled                    442
    REFUNDED         → refunded                      1
    SHIPPED          → completed                     1  synthetic fixture

A further refinement: gateway orders whose only payment attempt is a PENDING
CARD_TRANSFER (92 live rows) become ``waiting_payment_card`` rather than
``waiting_payment_gateway``. That distinction is the whole point of the new
vocabulary — the gateway bucket is swept to ``canceled`` on a timeout, while the
card bucket waits for an admin forever. Filing those 92 in the wrong bucket
would auto-cancel orders whose money is already in the account.

Storage contract: ``orders.status`` is a varchar-backed Enum
(``native_enum=False``) and the repo's contract is that it holds NAMES
(``WAITING_PAYMENT_GATEWAY``), not values. Writing lowercase values here makes
every subsequent ``Order.status`` read raise ValueError — this bit the first
manual run of this migration, which is why the guard at the end asserts against
the NAME form.

Column width: the column was created as ``varchar(18)``, sized from
``PARTIALLY_REFUNDED`` (the longest name in the ORIGINAL enum). The names in
this vocabulary are longer (``WAITING_PAYMENT_GATEWAY`` is 23), so the first
upgrade attempt failed with ``StringDataRightTruncation``. The column is widened
to 32 here, before any data is written.

Revision ID: rmstatus2
Revises: rmpricing1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "rmstatus2"
down_revision = "rmpricing1"
branch_labels = None
depends_on = None

#: Width for the status column. 32 leaves headroom over the longest name
#: (`WAITING_PAYMENT_GATEWAY`, 23) so a future rename does not need another
#: DDL change.
_STATUS_WIDTH = 32
_PREVIOUS_WIDTH = 18

#: old NAME → new NAME lives inline in `_rewrite` as an ORDERED step list, not
#: as a dict: a dict's iteration order turned out to be load-bearing here (one
#: step's output is another step's input), and encoding that in an unordered
#: mapping is how the downgrade collapsed two buckets together. See the
#: comment on `_rewrite` before changing the order.

#: The vocabulary the guard at the end allows.
_ALLOWED: frozenset[str] = frozenset(
    {
        "WAITING_PAYMENT_GATEWAY",
        "WAITING_PAYMENT_CARD",
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "CANCELED",
        "REFUNDED",
    }
)


def _widen_status_column(width: int) -> None:
    """Resize `orders.status` before writing longer names.

    Done unconditionally rather than only when narrowing/widening is detected:
    the column type is plain varchar, so a repeat run is a cheap no-op and the
    alternative (introspecting the current width) is more code for no gain.
    """
    op.alter_column(
        "orders",
        "status",
        existing_type=sa.String(length=_PREVIOUS_WIDTH),
        type_=sa.String(length=width),
        existing_nullable=False,
    )


def _rewrite(forward: bool) -> None:
    """Rewrite the status column, one mapping step at a time.

    ORDER IS NOT COSMETIC. A step's OUTPUT can be another step's INPUT, so the
    steps must run so that no freshly-written value is swept again:

    * Forward: PENDING must move to WAITING_PAYMENT_GATEWAY *before*
      CONFIRMED moves into PENDING — otherwise the 2075 accepted orders land in
      PENDING first and the next step would push them into the gateway bucket.
    * Backward: PENDING must move to CONFIRMED *before* the two WAITING_*
      buckets fold into PENDING — otherwise the ~24.6k gateway orders land in
      PENDING first and get swept into CONFIRMED along with the real ones.

    The first draft iterated a dict and got the backward order wrong; the
    downgrade then collapsed gateway + card + accepted orders into CONFIRMED,
    losing the card/gateway split. Hence the explicit step lists below.
    """
    conn = op.get_bind()

    # Each step is either ("rename", OLD, NEW) or ("sql", STATEMENT). A tagged
    # tuple rather than a bare one: an earlier draft used bare (old, new)
    # pairs alongside a (label, sql) pair, and the type check could not tell
    # them apart — the label was then written as a status value, producing
    # "value too long for varchar(32)".
    if forward:
        steps: list[tuple[str, str, str]] = [
            # ORDER MATTERS. The card-to-card subset must be carved out of the
            # OLD PENDING (unpaid gateway orders) — so it runs while PENDING
            # still means "unpaid". Running it after the gateway step would
            # find the 2075 accepted orders sitting in PENDING and mislabel any
            # of them that happen to have a card-transfer payment row.
            (
                "sql",
                "UPDATE orders SET status = 'WAITING_PAYMENT_CARD' "
                "WHERE status = 'PENDING' AND EXISTS ("
                "  SELECT 1 FROM payments p WHERE p.order_id = orders.id "
                "    AND p.provider = 'CARD_TRANSFER' AND p.status = 'PENDING'"
                ")",
            ),
            # …then the rest of the old PENDING becomes the gateway bucket.
            ("rename", "PENDING", "WAITING_PAYMENT_GATEWAY"),
            # …and only now does CONFIRMED (the accepted orders) take over the
            # PENDING name. Doing this earlier would put accepted orders in the
            # bucket the previous step was draining.
            ("rename", "CONFIRMED", "PENDING"),
            # The six physical-store statuses fold into their nearest survivor.
            ("rename", "SHIPPED", "COMPLETED"),
            ("rename", "DELIVERED", "COMPLETED"),
            ("rename", "ON_HOLD", "PROCESSING"),
            ("rename", "RETURNED", "REFUNDED"),
            ("rename", "PARTIALLY_REFUNDED", "REFUNDED"),
            # PROCESSING/COMPLETED/CANCELED/REFUNDED keep their names; no step.
        ]
    else:
        steps = [
            # PENDING must leave BEFORE the WAITING_* buckets fold into it, or
            # the accepted orders get swept into CONFIRMED with the gateway ones.
            ("rename", "PENDING", "CONFIRMED"),
            ("rename", "WAITING_PAYMENT_GATEWAY", "PENDING"),
            ("rename", "WAITING_PAYMENT_CARD", "PENDING"),
        ]

    for step in steps:
        kind = step[0]
        if kind == "sql":
            conn.execute(sa.text(step[1]))
        else:
            old, new = step[1], step[2]
            if old == new:
                continue  # no-op: skip a pointless full-table UPDATE
            conn.execute(
                sa.text("UPDATE orders SET status = :new WHERE status = :old"),
                {"new": new, "old": old},
            )


def upgrade() -> None:
    _widen_status_column(_STATUS_WIDTH)
    _rewrite(forward=True)

    # Assert the column now holds only NAMES the new enum knows. A stray value
    # here means every Order read raises ValueError at runtime, far from the
    # cause — so fail the migration instead of shipping a landmine.
    conn = op.get_bind()
    remaining = {
        row[0]
        for row in conn.execute(sa.text("SELECT DISTINCT status FROM orders")).fetchall()
    }
    stray = remaining - _ALLOWED
    if stray:
        raise RuntimeError(
            f"order status migration left values the new enum cannot read: {sorted(stray)}"
        )


def downgrade() -> None:
    """Best-effort reverse. The collapse is lossy: waiting_payment_card folds
    back into PENDING, and the six physical-store statuses cannot be
    reconstructed — they are not recoverable from the new vocabulary, only from
    a backup.

    The column is narrowed back to its previous width AFTER the data is
    rewritten, because the intermediate names would not fit otherwise.
    """
    _rewrite(forward=False)
    _widen_status_column(_PREVIOUS_WIDTH)
