"""orders: sequential numeric order numbers (WordPress-style #1, #2, ...)

The old order_number values were opaque prefixed strings
(``ORD-YYYYMMDD-XXXX``, ``B2B-YYYYMMDD-XXXXXXXX``, ``ORD-C-<uuid>``). The
owner asked for WordPress-style sequential numeric codes, so:

1. every existing order is renumbered ``1..N`` (oldest first, by created_at
   then id) — numeric codes take over the column completely;
2. a ``site_settings`` counter row (``orders.order_number_counter``) is
   seeded with ``{"next": N + 1}``; the application hands out values from it
   under a row lock (see ``order_number_service.next_order_number``).

The old order_number strings are not recoverable once renumbered, so the
downgrade only removes the counter row — the renumbering itself is not
reversible. Historical copies of the old codes (sent SMS, gateway logs)
keep referring to the previous strings.

Revision ID: ordnum1
Revises: uvord1
Create Date: 2026-10-24
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ordnum1"
down_revision: str | None = "uvord1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COUNTER_KEY = "orders.order_number_counter"


def upgrade() -> None:
    # 1. Park the (possibly numeric) existing codes so renumbering cannot
    #    collide with the unique constraint mid-UPDATE.
    op.execute(
        "UPDATE orders SET order_number = 'RN-' || CAST(id AS TEXT) "
        "WHERE order_number ~ '^[0-9]+$'"
    )
    # 2. Renumber every order sequentially, oldest first.
    op.execute(
        "WITH renumbered AS ("
        "  SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC) AS rn"
        "  FROM orders"
        ") "
        "UPDATE orders SET order_number = CAST(renumbered.rn AS TEXT) "
        "FROM renumbered WHERE orders.id = renumbered.id"
    )
    # 3. Seed the counter row the application hands numbers out from.
    #    is_public stays false: the counter is internal bookkeeping and must
    #    never surface through the public-settings API.
    op.execute(
        sa.text(
            "INSERT INTO site_settings (id, key, value, is_public) "
            "SELECT :id, :key, jsonb_build_object('next', "
            "  COALESCE(MAX(CAST(order_number AS BIGINT)), 0) + 1), false "
            "FROM orders "
            "ON CONFLICT (key) DO NOTHING"
        ).bindparams(id=uuid.uuid4(), key=_COUNTER_KEY)
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM site_settings WHERE key = :key").bindparams(
            key=_COUNTER_KEY
        )
    )
