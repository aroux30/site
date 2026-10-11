"""Remove the B2B/reseller, CRM, vendors and anti-fraud subsystems (rmb2b1).

Owner order 2026-10-10: «هرچیزی مربوط به این ماژول ها هست میخوام پاک کنی
کامل پاک کن از کد هیچ اثری نمیخوام ازشون باشه برای سایت فروشگاه اینترنتی
کارایی ندارن!» — the B2B/reseller flow (partner API keys + wholesale card
purchases), the CRM wholesale-inquiry pipeline, the multi-vendor marketplace,
and the anti-fraud / bank-card / user-trust block are all retired.

Verified against the live database before removal (all data was test-window
data; no real business data):

- ``reseller_api_keys``: 22 rows, all QA fixtures ("همکار تست ...", "QA");
- ``lead_inquiries``: 3 rows, all visual-test submissions;
- ``user_trust_profiles``: 1 row; ``user_bank_cards``: 7 rows (one test PAN);
- ``failed_attempts``: 194 rows, all LOGIN, nothing after 2026-09-20 (the
  recorder was already effectively dead — the row was rolled back on the
  error path; the Redis brute-force lockout is the real gate and stays);
- ``vendors``: 1 row (browser-test store); ``vendor_settlements``: 0 rows;
- ``products.vendor_id`` / ``product_variants.vendor_id``: 0 non-NULL values;
- the ``vendor`` RBAC role: 0 holders (only a ``media:read`` grant);
- ``saved_reports`` / ``report_runs``: 0 rows, so the removed
  ``vendor_settlement`` report type has no stored consumers.

This migration removes the schema half:

- drops ``lead_inquiries``, ``reseller_api_keys``, ``vendor_settlements``,
  ``vendors``, ``user_trust_profiles``, ``user_bank_cards``,
  ``failed_attempts`` (children before parents) with their indexes;
- drops ``vendor_id`` (FK + index) from ``products`` and ``product_variants``;
- deletes the ``vendor`` role (``role_permissions`` / ``user_roles`` rows
  cascade) and the ``crm:read`` / ``crm:write`` / ``vendors:read`` /
  ``vendors:write`` permissions (admin grants cascade).

The downgrade recreates every table, constraint, index and permission row
exactly as they existed live at removal time (permission and role ids are the
real ones, pinned so a downgrade restores what the removed code referenced).

Revision ID: rmb2b1
Revises: rmsub1
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmb2b1"
down_revision = "rmsub1"
branch_labels = None
depends_on = None

#: The permission rows as they existed at removal (verified live — ids are
#: the real ones, pinned so a downgrade restores the exact rows the removed
#: code referenced).
_PERMISSIONS = (
    {
        "id": "5edfa8c9-87fd-41c0-95a1-80d0a40d1521",
        "slug": "crm:read",
        "resource": "crm",
        "action": "read",
        "name": "مشاهده قیف فروش عمده",
        "description": "مشاهده درخواست‌های عمده‌فروشی و مراحل قیف فروش",
    },
    {
        "id": "e44540aa-2351-473b-8db3-3856d3ac71cb",
        "slug": "crm:write",
        "resource": "crm",
        "action": "write",
        "name": "مدیریت قیف فروش عمده",
        "description": "ثبت، پیگیری و تبدیل درخواست‌های عمده‌فروشی به همکار تجاری",
    },
    {
        "id": "bf62faca-590a-4843-b305-4f97f638e235",
        "slug": "vendors:read",
        "resource": "vendors",
        "action": "read",
        "name": "مشاهده فروشندگان",
        "description": "مشاهده فروشندگان، غرفه‌ها و وضعیت آن‌ها",
    },
    {
        "id": "e8fc9f54-9250-4120-9559-f47a01ba4640",
        "slug": "vendors:write",
        "resource": "vendors",
        "action": "write",
        "name": "مدیریت فروشندگان",
        "description": "ایجاد، تایید و مدیریت فروشندگان و غرفه‌های آن‌ها",
    },
)

#: The vendor staff role and its single grant, as they existed at removal.
_VENDOR_ROLE_ID = "b5649694-0faa-4fb3-9026-962ba632688d"
_VENDOR_ROLE_MEDIA_READ_PERMISSION_ID = "031cbf5f-adbb-4246-a591-f75085c82d2b"


def upgrade() -> None:
    # ── Tables: children before parents ────────────────────────────────────
    op.drop_index("ix_vendor_settlements_vendor_id", table_name="vendor_settlements")
    op.drop_index("ix_vendor_settlements_status", table_name="vendor_settlements")
    op.drop_index("ix_vendor_settlements_created_at", table_name="vendor_settlements")
    op.drop_table("vendor_settlements")

    op.drop_index("ix_lead_inquiries_company", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_created_at", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_next_follow_up", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_owner_id", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_stage", table_name="lead_inquiries")
    op.drop_table("lead_inquiries")

    op.drop_index("ix_reseller_api_keys_is_active", table_name="reseller_api_keys")
    op.drop_index("ix_reseller_api_keys_key_hash", table_name="reseller_api_keys")
    op.drop_index("ix_reseller_api_keys_user_id", table_name="reseller_api_keys")
    op.drop_table("reseller_api_keys")

    op.drop_index("ix_user_trust_profiles_is_trusted", table_name="user_trust_profiles")
    op.drop_index("ix_user_trust_profiles_user_id", table_name="user_trust_profiles")
    op.drop_table("user_trust_profiles")

    op.drop_index("ix_user_bank_cards_card_pan_hash", table_name="user_bank_cards")
    op.drop_index("ix_user_bank_cards_is_verified", table_name="user_bank_cards")
    op.drop_index("ix_user_bank_cards_user_id", table_name="user_bank_cards")
    op.drop_table("user_bank_cards")

    op.drop_index("ix_failed_attempts_attempt_type", table_name="failed_attempts")
    op.drop_index("ix_failed_attempts_created_at", table_name="failed_attempts")
    op.drop_index("ix_failed_attempts_identifier", table_name="failed_attempts")
    op.drop_table("failed_attempts")

    # ── products / product_variants: the vendor dimension ──────────────────
    # FKs and indexes go before the columns; the ``vendors`` table drops after
    # both columns are gone (all values were NULL — verified live).
    op.drop_index("ix_products_vendor_id", table_name="products")
    op.drop_constraint("fk_products_vendor_id_vendors", "products", type_="foreignkey")
    op.drop_column("products", "vendor_id")

    op.drop_index("ix_product_variants_vendor_id", table_name="product_variants")
    op.drop_constraint(
        "fk_product_variants_vendor_id_vendors", "product_variants", type_="foreignkey"
    )
    op.drop_column("product_variants", "vendor_id")

    op.drop_index("ix_vendors_is_active", table_name="vendors")
    op.drop_index("ix_vendors_is_verified", table_name="vendors")
    op.drop_index("ix_vendors_slug", table_name="vendors")
    op.drop_index("ix_vendors_user_id", table_name="vendors")
    op.drop_table("vendors")

    # ── RBAC rows ──────────────────────────────────────────────────────────
    # The vendor role leaves with the marketplace it served. role_permissions
    # and user_roles both CASCADE on role_id, so the grants go too.
    op.execute(sa.text("DELETE FROM roles WHERE slug = 'vendor'"))
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE slug IN "
            "('crm:read', 'crm:write', 'vendors:read', 'vendors:write')"
        )
    )


def downgrade() -> None:
    # ── vendors / vendor_settlements (initial schema, ec9dd94538b4) ────────
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("store_name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=250), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("banner_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("commission_rate", sa.Integer(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("national_id", sa.String(length=20), nullable=True),
        sa.Column("iban_number", sa.String(length=50), nullable=True),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("total_sales_count", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendors")),
        sa.UniqueConstraint("slug", name=op.f("uq_vendors_slug")),
        sa.UniqueConstraint("user_id", name=op.f("uq_vendors_user_id")),
    )
    op.create_index("ix_vendors_user_id", "vendors", ["user_id"])
    op.create_index("ix_vendors_slug", "vendors", ["slug"])
    op.create_index("ix_vendors_is_active", "vendors", ["is_active"])
    op.create_index("ix_vendors_is_verified", "vendors", ["is_verified"])

    op.create_table(
        "vendor_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("payment_reference", sa.String(length=100), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor_settlements")),
    )
    op.create_index("ix_vendor_settlements_vendor_id", "vendor_settlements", ["vendor_id"])
    op.create_index("ix_vendor_settlements_status", "vendor_settlements", ["status"])
    op.create_index("ix_vendor_settlements_created_at", "vendor_settlements", ["created_at"])

    # ── products / product_variants: vendor dimension back ─────────────────
    op.add_column(
        "products",
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_vendor_id_vendors",
        "products",
        "vendors",
        ["vendor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_products_vendor_id", "products", ["vendor_id"])

    op.add_column(
        "product_variants",
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_product_variants_vendor_id_vendors",
        "product_variants",
        "vendors",
        ["vendor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_product_variants_vendor_id", "product_variants", ["vendor_id"])

    # ── reseller_api_keys (a1b2c3d4e5f6) ───────────────────────────────────
    op.create_table(
        "reseller_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_whitelist", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("credit_balance", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "rate_limit_per_minute",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reseller_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_reseller_api_keys_key_hash")),
    )
    op.create_index("ix_reseller_api_keys_user_id", "reseller_api_keys", ["user_id"])
    op.create_index("ix_reseller_api_keys_key_hash", "reseller_api_keys", ["key_hash"])
    op.create_index("ix_reseller_api_keys_is_active", "reseller_api_keys", ["is_active"])

    # ── lead_inquiries (c4e6a8b2d5f7; email column already removed by
    #    rmemail1 and stays absent) ─────────────────────────────────────────
    op.create_table(
        "lead_inquiries",
        sa.Column("contact_name", sa.String(length=200), nullable=False),
        sa.Column("company_name", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=32), server_default="NEW", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="WEB_FORM", nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("estimated_monthly_value_rial", sa.BigInteger(), nullable=True),
        sa.Column("estimated_monthly_volume", sa.Integer(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("converted_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(length=500), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
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
            ["owner_id"],
            ["users.id"],
            name="fk_lead_inquiries_owner_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["converted_user_id"],
            ["users.id"],
            name="fk_lead_inquiries_converted_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_inquiries")),
        sa.CheckConstraint("contact_name <> ''", name="ck_lead_inquiries_contact_name_not_empty"),
        sa.CheckConstraint(
            "stage IN ('NEW','CONTACTED','QUALIFIED','NEGOTIATING','CONVERTED','LOST')",
            name="ck_lead_inquiries_stage",
        ),
        sa.CheckConstraint(
            "source IN ('WEB_FORM','PHONE','EMAIL','REFERRAL','SOCIAL','OTHER')",
            name="ck_lead_inquiries_source",
        ),
        sa.CheckConstraint(
            "estimated_monthly_value_rial IS NULL OR estimated_monthly_value_rial >= 0",
            name="ck_lead_inquiries_value_non_negative",
        ),
    )
    op.create_index("ix_lead_inquiries_stage", "lead_inquiries", ["stage"])
    op.create_index("ix_lead_inquiries_owner_id", "lead_inquiries", ["owner_id"])
    op.create_index("ix_lead_inquiries_created_at", "lead_inquiries", ["created_at"])
    op.create_index("ix_lead_inquiries_company", "lead_inquiries", ["company_name"])
    op.create_index("ix_lead_inquiries_next_follow_up", "lead_inquiries", ["next_follow_up_at"])

    # ── user_trust_profiles / user_bank_cards / failed_attempts
    #    (e7f1a3b8c5d2; shahkar_verified already removed by rmpayship1) ─────
    op.create_table(
        "user_trust_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_trusted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("risk_score", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column(
            "delayed_delivery_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "daily_spend_limit",
            sa.BigInteger(),
            server_default=sa.text("50000000"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_trust_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_trust_profiles_user_id")),
    )
    op.create_index("ix_user_trust_profiles_user_id", "user_trust_profiles", ["user_id"])
    op.create_index("ix_user_trust_profiles_is_trusted", "user_trust_profiles", ["is_trusted"])

    op.create_table(
        "user_bank_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("card_pan_masked", sa.String(length=20), nullable=False),
        sa.Column("card_pan_hash", sa.String(length=64), nullable=False),
        sa.Column("card_pan_encrypted", sa.String(length=255), nullable=False),
        sa.Column("iban", sa.String(length=30), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_bank_cards")),
    )
    op.create_index("ix_user_bank_cards_user_id", "user_bank_cards", ["user_id"])
    op.create_index("ix_user_bank_cards_card_pan_hash", "user_bank_cards", ["card_pan_hash"])
    op.create_index("ix_user_bank_cards_is_verified", "user_bank_cards", ["is_verified"])

    op.create_table(
        "failed_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("attempt_type", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failed_attempts")),
    )
    op.create_index("ix_failed_attempts_identifier", "failed_attempts", ["identifier"])
    op.create_index("ix_failed_attempts_attempt_type", "failed_attempts", ["attempt_type"])
    op.create_index("ix_failed_attempts_created_at", "failed_attempts", ["created_at"])

    # ── RBAC rows: permissions, grants, and the vendor role ────────────────
    for perm in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, slug, resource, action, name, description) "
                "VALUES (CAST(:id AS uuid), :slug, :resource, :action, :name, :description) "
                "ON CONFLICT (slug) DO NOTHING"
            ).bindparams(**perm)
        )
    # Grant all four to the super-admin role, as they were before removal.
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), r.id, p.id, now(), now() FROM roles r, permissions p "
            "WHERE r.name = 'مدیر سیستم' "
            "AND p.slug IN ('crm:read', 'crm:write', 'vendors:read', 'vendors:write') "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "  WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
        )
    )
    # The vendor staff role, with its single media:read grant.
    op.execute(
        sa.text(
            "INSERT INTO roles (id, slug, name, description, is_system, created_at, updated_at) "
            "VALUES (CAST(:id AS uuid), 'vendor', 'فروشنده', "
            "'فروشندهٔ ثبت‌نام‌شده. دسترسی فقط به فروشگاه و تسویهٔ خودش؛ "
            "بدون دسترسی به ویندورهای دیگر.', true, now(), now()) "
            "ON CONFLICT (slug) DO NOTHING"
        ).bindparams(id=_VENDOR_ROLE_ID)
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), r.id, p.id, now(), now() FROM roles r, permissions p "
            "WHERE r.slug = 'vendor' AND p.id = CAST(:perm_id AS uuid) "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "  WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
        ).bindparams(perm_id=_VENDOR_ROLE_MEDIA_READ_PERMISSION_ID)
    )
