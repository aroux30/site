"""Remove the pricing (price lists) module (revision rmpricing1).

Owner order (2026-10-10): the price-list module (لیست‌های قیمت) is not used by
the online store and must be removed completely — code, admin page, nav entry,
RBAC rows and tables. The volume-tier engine (``price_tiers``, Karta
findPrice) is NOT part of this module and stays; it now lives in
``app.modules.inventory.application.pricing_service``.

Data check before removal (live DB):
  price_lists        — 1 row: «همکاران طلایی» (GOLD, priority 10, active)
  price_list_rules   — 1 row: catalog-wide 10% discount (discount_bp=1000)
  customer_segments  — never existed as a table (only the enum name on
                       price_lists.segment, stored as VARCHAR)
  permissions        — pricing:read, pricing:write (both granted to admin)
  entity_change_logs — 0 rows of entity_type='price_list_rule'

Downgrade recreates both tables with their exact live shape (indexes,
CHECK constraints with the live double-prefixed names, FKs) and re-inserts
the permission rows with their real live ids, re-granted to the admin role.

Revision ID: rmpricing1
Revises: rmb2b1
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmpricing1"
down_revision = "rmb2b1"
branch_labels = None
depends_on = None

#: The permission rows as they existed at removal (verified live — ids are
#: the real ones, pinned so a downgrade restores the exact rows the removed
#: code referenced).
_PERMISSIONS = (
    {
        "id": "03d130c4-e772-4fa7-84de-98cb73bc5e29",
        "slug": "pricing:read",
        "resource": "pricing",
        "action": "read",
        "name": "مشاهده قیمت‌گذاری",
        "description": "مشاهده قوانین قیمت‌گذاری، لیست‌های قیمت و افزایش قیمت",
    },
    {
        "id": "d64f75a3-fa9f-4223-8c3f-f1cd83c4ed4f",
        "slug": "pricing:write",
        "resource": "pricing",
        "action": "write",
        "name": "مدیریت قیمت‌گذاری",
        "description": "ایجاد و ویرایش قوانین قیمت‌گذاری و لیست‌های قیمت",
    },
)

#: The admin role id, as it exists live (slug 'admin', name 'مدیر سیستم').
_ADMIN_ROLE_ID = "51ab099d-92ff-4361-9d02-9dbc07263f50"

#: The single live price_list row at removal time, restored by downgrade so a
#: rollback returns the exact data the removed page displayed.
_PRICE_LIST_ROW = {
    "id": "72ff0894-9cc8-43f9-97ea-c57a9293b835",
    "name": "همکاران طلایی",
    "segment": "GOLD",
    "is_active": True,
    "priority": 10,
}
_PRICE_LIST_RULE_ROW = {
    "id": "19e49ab3-817e-4e19-8745-bea4056047bf",
    "price_list_id": "72ff0894-9cc8-43f9-97ea-c57a9293b835",
    "min_quantity": 0,
    "discount_bp": 1000,
}


def upgrade() -> None:
    # ── Tables: children before parents ────────────────────────────────────
    op.drop_index("ix_price_list_rules_variant_id", table_name="price_list_rules")
    op.drop_index("ix_price_list_rules_product_id", table_name="price_list_rules")
    op.drop_index("ix_price_list_rules_price_list_id", table_name="price_list_rules")
    op.drop_table("price_list_rules")

    op.drop_index("ix_price_lists_is_active", table_name="price_lists")
    op.drop_index("ix_price_lists_segment", table_name="price_lists")
    op.drop_table("price_lists")

    # ── RBAC rows ──────────────────────────────────────────────────────────
    # role_permissions has ON DELETE CASCADE on permission_id, so the admin
    # grants go with the permission rows.
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE slug IN ('pricing:read', 'pricing:write')"
        )
    )


def downgrade() -> None:
    # ── Tables: parents before children ────────────────────────────────────
    # The declarative naming convention (ck_%(table_name)s_%(constraint_name)s)
    # prefixes CHECK names, so the short ck_plr_* names below become the live
    # ck_price_list_rules_ck_plr_* names exactly as the original migration
    # (l4m5n6o7p8q9) produced them.
    op.create_table(
        "price_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("segment", sa.String(length=9), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_lists")),
    )
    op.create_index("ix_price_lists_segment", "price_lists", ["segment"])
    op.create_index("ix_price_lists_is_active", "price_lists", ["is_active"])

    op.create_table(
        "price_list_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("min_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fixed_price_rial", sa.BigInteger(), nullable=True),
        sa.Column("discount_bp", sa.Integer(), nullable=True),
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
            ["price_list_id"],
            ["price_lists.id"],
            name="fk_price_list_rules_price_list_id_price_lists",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_price_list_rules_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_price_list_rules_variant_id_product_variants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_list_rules")),
        # Short names on purpose: the declarative naming convention
        # (ck_%(table_name)s_%(constraint_name)s) prefixes them, producing the
        # live names ck_price_list_rules_ck_plr_*. Passing the full name here
        # would double-prefix it.
        sa.CheckConstraint(
            "min_quantity >= 0",
            name="ck_plr_min_qty_non_negative",
        ),
        sa.CheckConstraint(
            "discount_bp >= 0 AND discount_bp <= 10000",
            name="ck_plr_discount_bp_range",
        ),
        sa.CheckConstraint(
            "fixed_price_rial IS NULL OR fixed_price_rial >= 0",
            name="ck_plr_fixed_price_non_negative",
        ),
    )
    op.create_index(
        "ix_price_list_rules_price_list_id", "price_list_rules", ["price_list_id"]
    )
    op.create_index(
        "ix_price_list_rules_product_id", "price_list_rules", ["product_id"]
    )
    op.create_index(
        "ix_price_list_rules_variant_id", "price_list_rules", ["variant_id"]
    )

    # ── The live data rows, so a rollback shows what the page displayed ────
    op.execute(
        sa.text(
            "INSERT INTO price_lists (id, name, segment, is_active, priority, "
            "created_at, updated_at) "
            "VALUES (CAST(:id AS uuid), :name, :segment, :is_active, :priority, "
            "now(), now()) ON CONFLICT (id) DO NOTHING"
        ).bindparams(**_PRICE_LIST_ROW)
    )
    op.execute(
        sa.text(
            "INSERT INTO price_list_rules (id, price_list_id, product_id, variant_id, "
            "min_quantity, fixed_price_rial, discount_bp, created_at, updated_at) "
            "VALUES (CAST(:id AS uuid), CAST(:price_list_id AS uuid), NULL, NULL, "
            ":min_quantity, NULL, :discount_bp, now(), now()) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(**_PRICE_LIST_RULE_ROW)
    )

    # ── RBAC rows: permissions + admin grants ──────────────────────────────
    for perm in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, slug, resource, action, name, description) "
                "VALUES (CAST(:id AS uuid), :slug, :resource, :action, :name, :description) "
                "ON CONFLICT (slug) DO NOTHING"
            ).bindparams(**perm)
        )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), r.id, p.id, now(), now() FROM roles r, permissions p "
            "WHERE r.id = CAST(:role_id AS uuid) "
            "AND p.slug IN ('pricing:read', 'pricing:write') "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "  WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
        ).bindparams(role_id=_ADMIN_ROLE_ID)
    )
