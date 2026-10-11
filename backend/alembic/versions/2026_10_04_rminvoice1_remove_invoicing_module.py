"""Remove the invoicing module (fiscal documents: tables + permissions).

The «اسناد مالی» (fiscal documents) module was retired on 2026-10-04 by
operator decision, following the same review that removed the approvals
cartable. It was verified to be unused in practice:

- all three tables were empty at removal time (0 invoices, 0 lines,
  0 sequences — verified against the live database);
- no code path outside the module ever created a *posted* document: the only
  automatic producer was the refund outbox listener, which created draft
  credit notes that nothing ever posted (posting was a manual admin action);
- the admin list page had no reachable creation flow (the backfill Celery
  task was never beat-scheduled and had zero callers; the create-draft API
  had no UI caller), so the screen could only ever show an empty table;
- the storefront sells consumer goods and digital subscriptions; a formal
  fiscal ledger is not part of that flow. The printable tax invoice
  (``order_receipt_renderer``, ماده ۱۶۹ / سامانه مودیان HTML) is a separate,
  older path and is NOT touched by this removal — customers keep their
  receipt and printable invoice.

The accounting module's journal (hash-chained, gapless JE numbers) remains
the platform's money record; it observes the same refund events and was
never fed by this module.

Decision record: ``docs/invoicing-removal-2026-10-04.md``. Removed code is
archived under ``_archived/invoicing-module-2026-10-04/``. ``downgrade()``
recreates the full schema (three tables, constraints, indexes) and both
permission rows with their admin grants, so the removal is reversible.

Revision ID: rminvoice1
Revises: rmapprov1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rminvoice1"
down_revision = "rmapprov1"
branch_labels = None
depends_on = None

#: The permission rows as they existed at removal (verified against the live
#: database before dropping). Ids are pinned so a downgrade restores the
#: exact rows the removed code referenced.
_PERMISSIONS = (
    {
        "id": "caf3b0cd-35b0-499b-8146-287b9d25b741",
        "slug": "invoicing:read",
        "resource": "invoicing",
        "action": "read",
        "name": "مشاهده فاکتورها",
        "description": "مشاهده فاکتورهای فروش و رسمی و اسناد مالی مرتبط",
    },
    {
        "id": "cc96db17-a2cc-47c7-b8c7-9c3ef5941c6a",
        "slug": "invoicing:write",
        "resource": "invoicing",
        "action": "write",
        "name": "مدیریت فاکتورها",
        "description": "صدور، ویرایش و ابطال فاکتورها و اسناد مالی",
    },
)


def upgrade() -> None:
    # Children before parents: invoice_lines holds an FK into invoices.
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")

    op.drop_table("invoice_sequences")

    op.drop_index("ix_invoices_idempotency_key", table_name="invoices")
    op.drop_index("ix_invoices_issued_at", table_name="invoices")
    op.drop_index("ix_invoices_type", table_name="invoices")
    op.drop_index("ix_invoices_fiscal_period", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.drop_table("invoices")

    # The permissions leave with the feature they guarded. role_permissions
    # has ON DELETE CASCADE on permission_id, so the admin grants go too.
    op.execute(
        sa.text("DELETE FROM permissions WHERE slug IN ('invoicing:read', 'invoicing:write')")
    )


def downgrade() -> None:
    # ── invoices (initial schema, w5x6y7z8a9b0) ────────────────────────────
    op.create_table(
        "invoices",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum("INVOICE", "CREDIT_NOTE", name="invoice_type_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "POSTED", "PAID", "CANCELLED",
                name="invoice_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("number", sa.String(length=32), nullable=True),
        sa.Column("fiscal_period", sa.String(length=8), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("totals", postgresql.JSONB(), nullable=False),
        sa.Column("customer", postgresql.JSONB(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "credit_for_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("credit_reason", sa.Text(), nullable=True),
        sa.Column("archive_path", sa.String(length=500), nullable=True),
        sa.Column("archive_content_type", sa.String(length=100), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_invoices_idempotency_key"),
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_fiscal_period", "invoices", ["fiscal_period"])
    op.create_index("ix_invoices_type", "invoices", ["type"])
    op.create_index("ix_invoices_issued_at", "invoices", ["issued_at"])
    op.create_index("ix_invoices_idempotency_key", "invoices", ["idempotency_key"])

    # ── invoice_lines ──────────────────────────────────────────────────────
    op.create_table(
        "invoice_lines",
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("total_price", sa.BigInteger(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity >= 0", name="ck_invoice_lines_quantity_nonneg"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    # ── invoice_sequences ──────────────────────────────────────────────────
    op.create_table(
        "invoice_sequences",
        sa.Column("fiscal_period", sa.String(length=8), nullable=False),
        sa.Column(
            "doc_type",
            sa.Enum("INVOICE", "CREDIT_NOTE", name="invoice_type_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_period", "doc_type", name="uq_invoice_sequences_period_type"),
    )

    # ── the permission rows and their admin grants ─────────────────────────
    for perm in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, slug, resource, action, name, description,"
                " created_at, updated_at)"
                " VALUES (CAST(:id AS uuid), :slug, :resource, :action, :name, :description,"
                " now(), now())"
                " ON CONFLICT (slug) DO NOTHING"
            ).bindparams(**perm)
        )
        # Re-grant to the seeded admin role, matching permission_seed.py's
        # blanket grant to ADMIN_ROLE_SLUG. Missing role (a database that
        # never seeded) is fine: the row is granted by the next startup seed.
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at)"
                " SELECT gen_random_uuid(), r.id, p.id, now(), now()"
                " FROM roles r, permissions p"
                " WHERE r.slug = 'admin' AND p.slug = :slug"
                " ON CONFLICT DO NOTHING"
            ).bindparams(slug=perm["slug"])
        )
