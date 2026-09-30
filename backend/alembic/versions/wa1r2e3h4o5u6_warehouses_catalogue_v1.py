"""Warehouses catalogue v1 — expose the multi-warehouse model that already exists.

ERP benchmark gap analysis (feature #17 Multi-warehouse, P1): every inventory
row (items, reservations, transactions, reorder rules, counts, transfers,
receipts) already carries ``warehouse_id``, but there was no *catalogue* of
warehouses — only the fixed ``DEFAULT_WAREHOUSE_ID`` sentinel, so the platform
was single-warehouse in practice.

This migration is purely additive:

- ``warehouses``: name, unique code, address, ``is_default``, ``is_active``.
- A **partial** unique index (``is_default``) makes "at most one default" a
  database fact, not a convention. Partial so that any number of warehouses may
  be non-default.
- The sentinel warehouse row (``00000000-…-0101``) is inserted only when it does
  not already exist, flagged default while no other default is present. It is
  *not* assigned to existing stock rows: those already carry that exact
  ``warehouse_id`` from ``b3c4d5e6f7a8``. This migration moves no quantities.

No existing table is altered, no column is dropped, and no stock is touched —
the single-warehouse operating mode (all call sites defaulting to the sentinel)
keeps working unchanged.

Revision ID: wa1r2e3h4o5u6
Revises: p1q2r3s4t5u6
Create Date: 2026-09-24 23:59:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "wa1r2e3h4o5u6"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None

DEFAULT_WAREHOUSE_ID = "00000000-0000-0000-0000-000000000101"
DEFAULT_WAREHOUSE_NAME = "انبار مرکزی"
DEFAULT_WAREHOUSE_CODE = "CENTRAL"


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_warehouses_name_not_blank"),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_warehouses_code_not_blank"),
        # NOTE: the migration names these explicitly because ``op.create_table``
        # does not apply the metadata naming convention; the model declares the
        # same names via the ``ck_<table>_<name>`` convention.
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("code", name="uq_warehouses_code"),
    )
    op.create_index(
        "ix_warehouses_is_active", "warehouses", ["is_active"], unique=False
    )
    # At most one default warehouse — enforced by the database. Partial so the
    # (many) non-default rows are unconstrained.
    op.create_index(
        "uq_warehouses_single_default",
        "warehouses",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )

    # Register the sentinel warehouse the ledger already writes to. Guarded so
    # re-running (or an install that already created it) is a no-op, and
    # flagged default only while nothing else claims the flag.
    op.execute(
        sa.text(
            """
            INSERT INTO warehouses (id, name, code, address, is_default, is_active,
                                    created_at, updated_at)
            SELECT CAST(:warehouse_id AS uuid), :name, :code, NULL,
                   NOT EXISTS (SELECT 1 FROM warehouses WHERE is_default),
                   true, now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM warehouses WHERE id = CAST(:warehouse_id AS uuid)
            )
            """
        ).bindparams(
            warehouse_id=DEFAULT_WAREHOUSE_ID,
            name=DEFAULT_WAREHOUSE_NAME,
            code=DEFAULT_WAREHOUSE_CODE,
        )
    )


def downgrade() -> None:
    op.drop_index("uq_warehouses_single_default", table_name="warehouses")
    op.drop_index("ix_warehouses_is_active", table_name="warehouses")
    op.drop_table("warehouses")
