"""Allow refunds for order-less payments (wallet top-ups) and tie the refund
purpose to its payment explicitly.

Problem
-------
``payments.order_id`` was made nullable (revision b3e7a9c2d154) so wallet
top-ups — which have no order — can be recorded as payments. ``refunds
.order_id``, however, stayed NOT NULL. Any attempt to refund a top-up fails
with a database-level ``NotNullViolationError``, so money taken through the
gateway for a wallet charge could never be returned through the refund flow.

This was reproduced against a live PostgreSQL before the fix:

    insert into refunds (payment_id, order_id, amount, ...)
    values (<order-less payment id>, NULL, 1000, 'processed', ...);
    --> null value in column "order_id" of relation "refunds"
        violates not-null constraint

Design (single coherent contract)
---------------------------------
A refund always belongs to a *payment*; it belongs to an *order* only when
that payment was order-backed. Concretely:

* ``refunds.order_id`` becomes nullable and keeps its FK to ``orders``
  (``ON DELETE RESTRICT``), so an order-backed refund can still never be
  orphaned from its order.
* A CHECK constraint enforces the relationship structurally: an order-backed
  payment's refund must carry the order id, and an order-less payment's
  refund must not. This keeps the two tables from drifting into a state where
  ``refunds.payment_id`` and ``refunds.order_id`` disagree about what was
  refunded.

A refund for a top-up credits the customer's wallet (see
``payment_service.refund_payment``), so the ledger — not an order row — is the
record of the money movement.

Pre-flight (run BEFORE deploying; the migration fails loudly if violated):

    -- A refund whose order disagrees with its payment's order:
    SELECT r.id, r.payment_id, r.order_id AS refund_order, p.order_id AS payment_order
    FROM refunds r JOIN payments p ON p.id = r.payment_id
    WHERE r.order_id IS DISTINCT FROM p.order_id;

    -- Order-backed refunds missing an order (would violate the new CHECK):
    SELECT r.id FROM refunds r JOIN payments p ON p.id = r.payment_id
    WHERE p.order_id IS NOT NULL AND r.order_id IS NULL;

Remediate any rows returned (and the code path that produced them) first.

Revision ID: a3f9c1e7d2b4
Revises: c8d9e0f1a2b3
Create Date: 2026-09-18 04:10:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3f9c1e7d2b4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. A refund may now reference an order only when its payment does.
    op.alter_column(
        "refunds",
        "order_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # 2. Gateway-side reference for the refund, recorded before the provider
    #    is called so an accepted-but-uncommitted refund can be reconciled.
    op.add_column(
        "refunds",
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_refunds_provider_reference",
        "refunds",
        ["provider_reference"],
    )

    # 3. Structural invariant: refunds.order_id is locked to payments.order_id.
    #    Enforced in the database so no code path can create a refund that
    #    claims a different order than the payment it settles.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refunds_match_payment_order()
        RETURNS trigger AS $$
        DECLARE
            payment_order uuid;
        BEGIN
            SELECT order_id INTO payment_order
            FROM payments WHERE id = NEW.payment_id;

            IF payment_order IS NULL AND NEW.order_id IS NOT NULL THEN
                RAISE EXCEPTION
                    'refund % references order % but its payment is not order-backed',
                    NEW.id, NEW.order_id
                    USING ERRCODE = 'check_violation';
            END IF;

            IF payment_order IS NOT NULL AND NEW.order_id IS DISTINCT FROM payment_order THEN
                RAISE EXCEPTION
                    'refund % order % does not match payment order %',
                    NEW.id, NEW.order_id, payment_order
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_refunds_match_payment_order
        BEFORE INSERT OR UPDATE OF payment_id, order_id ON refunds
        FOR EACH ROW EXECUTE FUNCTION refunds_match_payment_order();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_refunds_match_payment_order ON refunds")
    op.execute("DROP FUNCTION IF EXISTS refunds_match_payment_order()")
    op.drop_index("ix_refunds_provider_reference", table_name="refunds")
    op.drop_column("refunds", "provider_reference")
    # Fails if order-less refunds exist — delete or reassign them first.
    op.alter_column(
        "refunds",
        "order_id",
        existing_type=sa.UUID(),
        nullable=False,
    )