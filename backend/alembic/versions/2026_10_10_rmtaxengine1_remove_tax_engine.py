"""Remove the tax rule engine — one settings field is the only rate.

Owner decision 2026-10-09 (screenshot review of /admin/settings → مالی و
پرداخت vs the sidebar's «موتور مالیات»): the store had four different VAT
rates in play —

- the ``store.shipping_tax.tax_rate_percent`` admin field: stored **12**,
  read by no backend code;
- the v2 engine's seeded ``IR-VAT-DEFAULT`` rule: **9%** — what orders were
  actually charged;
- the legacy ``TaxService`` fallback: **10%** (its ``tax_rules`` table is
  empty, so the quote step always fell back);
- hard-coded «۱۰٪» labels in the cart, drawer and checkout.

The owner chose a single simple field as the authority and the engine, its
admin panel, the VAT report and the B2B withholding profile are removed
wholesale (archived under ``_archived/tax-engine-removal-2026-10-09/``).
The settings field keeps the value the engine actually charged (9) and every
surface — quote, order creation, per-line snapshots, storefront labels —
now derives from it via ``checkout.tax_rate_service``.

Schema half:

- drops ``tax_rules_v2`` (1 seeded row: the 9% default rule — captured in
  the archive) and its six indexes;
- drops ``order_tax_observations`` (0 rows; the per-order fiscal record the
  engine wrote) and its two indexes;
- drops the legacy ``tax_rules`` table (0 rows; the v1 engine's table —
  its callers are gone with ``tax_service.py``);
- drops the B2B columns ``is_b2b`` / ``company_name`` /
  ``tax_exemption_certificate_no`` from ``user_profiles`` (added by
  ``x6y7z8a9b0c1d`` for withholding; verified live: 20 rows all
  ``is_b2b = false``, 0 certificates, 0 company names);
- deletes the ``tax:read`` / ``tax:write`` permissions and their role
  grants (the only guarded routes were the removed ``/admin/tax/*``).

``downgrade()`` recreates the tables/indexes/columns exactly as
``x6y7z8a9b0c1d`` and ``01bc8bed842e`` defined them, re-seeds the 9%
default rule, and re-inserts the two permission rows with their captured
UUIDs. Historical order rows are untouched (orders.tax / price snapshots
keep the amounts that were actually charged).

Revision ID: rmtaxengine1
Revises: rmfreeship1
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmtaxengine1"
down_revision = "rmfreeship1"
branch_labels = None
depends_on = None

#: Captured live 2026-10-09 before the drop.
_TAX_PERMISSIONS = (
    (
        "6fcbe38b-111c-4f6d-b0e0-60d05a97803d",
        "مشاهده مالیات",
        "tax:read",
        "مشاهده قوانین مالیاتی، نرخ‌ها و گزارش‌های مالیات بر ارزش افزوده",
        "tax",
        "read",
    ),
    (
        "c33bdc9f-fa71-4f34-8468-8ee067025b82",
        "مدیریت مالیات",
        "tax:write",
        "ایجاد و ویرایش قوانین مالیاتی، نرخ‌ها و پروفایل‌های مالیاتی",
        "tax",
        "write",
    ),
)

_ADMIN_ROLE_ID = "51ab099d-92ff-4361-9d02-9dbc07263f50"


def upgrade() -> None:
    # ── Make the settings field the live rate at the charged value ──────
    # The field stored 12 (edited once in the admin form, read by nothing)
    # while orders were actually charged 9% (the engine's seeded default —
    # owner-confirmed as the intended rate). Writing 9 here keeps every
    # historical amount consistent with the new single source: the quote,
    # the order path and the storefront labels all derive from this value.
    op.execute(
        sa.text(
            "UPDATE site_settings "
            "SET value = jsonb_set(value, '{tax_rate_percent}', '\"9\"') "
            "WHERE key = 'store.shipping_tax'"
        )
    )

    # ── Permissions (routes removed with the engine) ─────────────────────
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE slug IN ('tax:read', 'tax:write'))"
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE slug IN ('tax:read', 'tax:write')")
    )

    # ── B2B / withholding columns (0 values in every row, verified) ──────
    op.drop_column("user_profiles", "tax_exemption_certificate_no")
    op.drop_column("user_profiles", "company_name")
    op.drop_column("user_profiles", "is_b2b")

    # ── order_tax_observations (0 rows) ──────────────────────────────────
    op.drop_index(
        "ix_order_tax_observations_created_at", table_name="order_tax_observations"
    )
    op.drop_index(
        "ix_order_tax_observations_order_id", table_name="order_tax_observations"
    )
    op.drop_table("order_tax_observations")

    # ── tax_rules_v2 (1 seeded row, captured in the archive) ─────────────
    op.drop_index("ix_tax_rules_v2_effective_dates", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_is_active", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_product_id", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_category_id", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_scope", table_name="tax_rules_v2")
    op.drop_index("ix_tax_rules_v2_code", table_name="tax_rules_v2")
    op.drop_table("tax_rules_v2")

    # ── legacy tax_rules (0 rows; the v1 engine's table) ─────────────────
    op.drop_index("ix_tax_rules_jurisdiction", table_name="tax_rules")
    op.drop_index("ix_tax_rules_is_active", table_name="tax_rules")
    op.drop_index("ix_tax_rules_effective_dates", table_name="tax_rules")
    op.drop_index("ix_tax_rules_code", table_name="tax_rules")
    op.drop_index("ix_tax_rules_category", table_name="tax_rules")
    op.drop_table("tax_rules")


def downgrade() -> None:
    # Restore the field's pre-removal value (captured live 2026-10-09).
    op.execute(
        sa.text(
            "UPDATE site_settings "
            "SET value = jsonb_set(value, '{tax_rate_percent}', '\"12\"') "
            "WHERE key = 'store.shipping_tax'"
        )
    )

    # ── legacy tax_rules (01bc8bed842e) ──────────────────────────────────
    op.create_table(
        "tax_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "STANDARD",
                "REDUCED",
                "EXEMPT",
                "ZERO",
                name="tax_category_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String(length=50), nullable=False),
        sa.Column("rate_basis_points", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_compound", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tax_rules")),
        sa.UniqueConstraint("code", name=op.f("uq_tax_rules_code")),
    )
    op.create_index("ix_tax_rules_category", "tax_rules", ["category"], unique=False)
    op.create_index("ix_tax_rules_code", "tax_rules", ["code"], unique=True)
    op.create_index(
        "ix_tax_rules_effective_dates",
        "tax_rules",
        ["effective_from", "effective_to"],
        unique=False,
    )
    op.create_index("ix_tax_rules_is_active", "tax_rules", ["is_active"], unique=False)
    op.create_index("ix_tax_rules_jurisdiction", "tax_rules", ["jurisdiction"], unique=False)

    # ── tax_rules_v2 (x6y7z8a9b0c1d) ─────────────────────────────────────
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
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
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
    # Re-seed the captured default rule (9% VAT).
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

    # ── order_tax_observations (x6y7z8a9b0c1d) ───────────────────────────
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

    # ── user_profiles B2B columns ────────────────────────────────────────
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

    # ── Permissions + the admin role grant (captured UUIDs) ──────────────
    for perm_id, name, slug, description, resource, action in _TAX_PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions "
                "(id, name, slug, description, resource, action, created_at, updated_at) "
                f"SELECT '{perm_id}', :name, :slug, :description, :resource, :action, "
                "now(), now() WHERE NOT EXISTS "
                "(SELECT 1 FROM permissions WHERE slug = :slug)"
            ).bindparams(
                sa.bindparam("name", value=name),
                sa.bindparam("slug", value=slug),
                sa.bindparam("description", value=description),
                sa.bindparam("resource", value=resource),
                sa.bindparam("action", value=action),
            )
        )
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role_id, permission_id) "
                f"SELECT gen_random_uuid(), '{_ADMIN_ROLE_ID}', id FROM permissions WHERE slug = :slug "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
                f"WHERE rp.role_id = '{_ADMIN_ROLE_ID}' AND rp.permission_id = permissions.id)"
            ).bindparams(sa.bindparam("slug", value=slug))
        )
