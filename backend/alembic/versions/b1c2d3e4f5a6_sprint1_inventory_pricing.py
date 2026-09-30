"""Sprint 1 — secure inventory & pricing schema (Karta roadmap items 1.3-1.7).

Adds:
- products.min_order_quantity / products.max_order_quantity
  (Karta per-invoice purchase limits; backend is the source of truth)
- order_items.custom_fields JSONB
  (Karta categoryFields/orderFields — dynamic buyer inputs persisted with the invoice)
- digital_cards.serial_ciphertext
  (serials are sensitive too — stored AES-256-GCM like PINs, plaintext retired)

Data migration: existing plaintext serials are encrypted with the current
application key and their plaintext column is cleared. Rows created after
this migration never carry a plaintext serial.

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "min_order_quantity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column("products", sa.Column("max_order_quantity", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("custom_fields", JSONB(), nullable=True))
    op.add_column(
        "category_custom_fields", sa.Column("options_json", JSONB(), nullable=True)
    )
    op.add_column("digital_cards", sa.Column("serial_ciphertext", sa.Text(), nullable=True))

    _encrypt_existing_serials()


def _encrypt_existing_serials() -> None:
    """Encrypt legacy plaintext serials, then retire the plaintext column."""
    import sqlalchemy as sa_inner

    from app.modules.inventory.application.crypto_service import encrypt_pin

    bind = op.get_bind()
    cards = sa_inner.table(
        "digital_cards",
        sa_inner.column("id"),
        sa_inner.column("serial_number"),
        sa_inner.column("serial_ciphertext"),
    )

    rows = bind.execute(
        sa_inner.select(cards.c.id, cards.c.serial_number).where(
            cards.c.serial_number.isnot(None),
            cards.c.serial_ciphertext.is_(None),
        )
    ).fetchall()

    for row in rows:
        plaintext = (row.serial_number or "").strip()
        if not plaintext:
            continue
        ciphertext = encrypt_pin(plaintext)
        bind.execute(
            cards.update()
            .where(cards.c.id == row.id)
            .values(serial_ciphertext=ciphertext, serial_number=None)
        )


def downgrade() -> None:
    # Encrypted serials cannot be restored to plaintext faithfully in bulk;
    # the column stays NULL for post-migration rows. Rotation of schema only.
    op.drop_column("digital_cards", "serial_ciphertext")
    op.drop_column("order_items", "custom_fields")
    op.drop_column("products", "max_order_quantity")
    op.drop_column("products", "min_order_quantity")
