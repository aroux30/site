"""Tax engine v1: effective-dated rules, per-order tax observations, B2B profile.

ERP benchmark gap analysis (feature #16 Tax engine, P0) — additive upgrade:

- ``tax_rules_v2``: effective-dated, priority-ordered rules of type
  vat / exempt / compound / withholding (مالیات تکلیفی) with per-category and
  per-product override scopes (product > category > default).
- ``order_tax_observations``: immutable per-order fiscal record (one row per
  order) holding the per-line tax breakdown JSONB plus header totals — the
  future سامانه مودیان reporting source. All integer Rials.
- ``user_profiles``: additive B2B columns (is_b2b, company_name,
  tax_exemption_certificate_no) driving withholding at checkout.

Seeds exactly one default rule: 9% VAT (900 basis points, Iranian ارزش
افزوده), code ``IR-VAT-DEFAULT``. The seed is idempotent (INSERT … WHERE NOT
EXISTS) so re-running the migration never duplicates the default rule.

The legacy ``tax_rules`` table and its callers are untouched.

Revision ID: x6y7z8a9b0c1d
Revises: w5x6y7z8a9b0
Create Date: 2026-09-24 23:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "x6y7z8a9b0c1d"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tax_rules_v2 ─────────────────────────────────────────────────────
    op.create_table(
        "tax_rules_v2",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column(
            "rule_type",
            sa.Enum(
                "VAT", "EXEMPT", "COMPOUND", "WITHHOLDING",
                name="tax_rule_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.Enum(
                "DEFAULT", "CATEGORY", "PRODUCT",
                name="tax_rule_scope_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rate_basis_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exempt_reason", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_tax_rules_v2_code", "tax_rules_v2", ["code"], unique=True)
    op.create_index("ix_tax_rules_v2_scope", "tax_rules_v2", ["scope"])
    op.create_index("ix_tax_rules_v2_category_id", "tax_rules_v2", ["category_id"])
    op.create_index("ix_tax_rules_v2_product_id", "tax_rules_v2", ["product_id"])
    op.create_index("ix_tax_rules_v2_is_active", "tax_rules_v2", ["is_active"])
    op.create_index(
        "ix_tax_rules_v2_effective_dates",
        "tax_rules_v2",
        ["effective_from", "effective_to"],
    )

    # ── order_tax_observations ───────────────────────────────────────────
    op.create_table(
        "order_tax_observations",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="IRR", nullable=False),
        sa.Column(
            "customer_is_b2b",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("exemption_certificate_ref", sa.String(length=200), nullable=True),
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vat_total_rial", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "withholding_total_rial", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("tax_total_rial", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "grand_total_rial", sa.BigInteger(), nullable=False, server_default="0"
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
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(
        "ix_order_tax_observations_order_id",
        "order_tax_observations",
        ["order_id"],
        unique=True,
    )
    op.create_index(
        "ix_order_tax_observations_created_at",
        "order_tax_observations",
        ["created_at"],
    )

    # ── user_profiles B2B columns (additive, nullable/defaulted) ────────
    op.add_column(
        "user_profiles",
        sa.Column("is_b2b", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("company_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("tax_exemption_certificate_no", sa.String(length=200), nullable=True),
    )

    # ── Seed: one always-present default rule — 9% Iranian VAT (900 bp) ──
    # Idempotent: INSERT … WHERE NOT EXISTS on the fixed seed UUID.
    op.execute(
        sa.text(
            """
            INSERT INTO tax_rules_v2 (
                id, name, code, rule_type, scope, rate_basis_points,
                is_active, priority, effective_from, effective_to,
                exempt_reason, description, created_at, updated_at
            )
            SELECT
                '11111111-2222-3333-4444-555555555555',
                'مالیات بر ارزش افزوده — پیش‌فرض',
                'IR-VAT-DEFAULT',
                'VAT',
                'DEFAULT',
                900,
                true,
                0,
                NULL,
                NULL,
                NULL,
                'Seeded default: 9% VAT (900 basis points) — Iranian ارزش افزوده',
                now(),
                now()
            WHERE NOT EXISTS (
                SELECT 1 FROM tax_rules_v2
                WHERE id = '11111111-2222-3333-4444-555555555555'
                   OR code = 'IR-VAT-DEFAULT'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "tax_exemption_certificate_no")
    op.drop_column("user_profiles", "company_name")
    op.drop_column("user_profiles", "is_b2b")

    op.drop_index(
        "ix_order_tax_observations_created_at", table_name="order_tax_observations"
    )
    op.drop_index(
        "ix_order_tax_observations_order_id", table_name="order_tax_observations"
    )
    op.drop_table("order_tax_observations")

    op.drop_index("ix_tax_rules_v2_effective_dates", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_is_active", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_product_id", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_category_id", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_scope", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_code", table_name="tax_rules_v2")
    op.drop_table("tax_rules_v2")
