"""Remove the accounting module — chart of accounts (decision 2026-10-05).

The owner asked for «کدینگ حساب‌ها» to be deleted outright: a retail
storefront's money record is the order/payment/wallet tables, and the
admin-maintained chart was a decorative ledger nothing downstream read.
This completes the removal wave that started with ``rmjournal1`` (which
dropped the journal and kept the chart "on purpose"); that decision is
superseded here, and the code is archived under
``_archived/accounting-module-2026-10-05/``.

Evidence at removal time (live probes 2026-10-05):

* ``accounts`` held exactly the 22 seed rows of the Iranian-standard
  skeleton — zero operator-created rows, and no table anywhere references
  ``accounts`` (the only FK ever pointing at it lived on ``journal_lines``,
  dropped by ``rmjournal1``). No business data is lost.
* Zero live importers of ``app.modules.accounting`` in the backend
  (``main.py`` router spec and ``alembic/env.py`` were the last two; both
  removed with this migration). Zero frontend consumers besides the deleted
  page and nav entry.
* ``accounting:read`` / ``accounting:write`` were granted only to the seeded
  ``admin`` role, and guarded only the three removed endpoints.

``downgrade()`` recreates the table exactly as ``a9c1e3f5b7d9`` defined it,
re-inserts all 22 seed rows with their original ids and parent links, and
restores the two permission rows (ids pinned from the live database) plus
their admin grants — so the removal is fully reversible. Chain note: this
migration is the new head (``down_revision = rmpayship2``), so a downgrade
runs it FIRST; by the time ``rmjournal1.downgrade()`` recreates
``journal_lines`` with its FK into ``accounts``, this table exists again.

Revision ID: rmaccount1
Revises: rmpayship2
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmaccount1"
down_revision = "rmpayship2"
branch_labels = None
depends_on = None

#: The permission rows as they existed at removal (ids verified against the
#: live database before dropping). Ids are pinned so a downgrade restores the
#: exact rows the removed code referenced.
_PERMISSIONS = (
    {
        "id": '5e6b866c-ffe3-4ee9-8dd2-03d1bf902171',
        "slug": 'accounting:read',
        "resource": 'accounting',
        "action": 'read',
        "name": 'مشاهده اسناد حسابداری',
        "description": 'مشاهده کدینگ حساب\u200cها، اسناد دفتر روزنامه، دوره\u200cهای مالی و خروجی\u200cهای حسابداری',
    },
    {
        "id": '51f55666-0d99-4a9b-a03b-a7e24e565978',
        "slug": 'accounting:write',
        "resource": 'accounting',
        "action": 'write',
        "name": 'مدیریت اسناد حسابداری',
        "description": 'ایجاد و ویرایش حساب\u200cها، ثبت و برگشت اسناد دستی، و بستن دوره مالی',
    },
)

#: The 22 live rows of ``accounts`` at removal time (id, code, name_fa, type,
#: parent_code, description). Restored verbatim by ``downgrade()`` so a
#: rollback brings back the exact chart an operator had.
_ACCOUNTS_SEED = (
    ('29a64b76-1d8f-40ed-89c4-9bf12f49865b', '1', 'داراییهای جاری', 'ASSET', None, 'گروه حسابهای دارایی'),
    ('04b3e90c-db01-450b-bc24-5fdb4d5bf61b', '1001', 'صندوق', 'ASSET', '1', 'موجودی نقد صندوق'),
    ('54141424-9af0-4ada-9396-2d3f1e24330b', '1002', 'بانک', 'ASSET', '1', 'موجودی حسابهای بانکی'),
    ('0746fa9e-7af1-49db-b58e-2687221e1408', '1003', 'حسابهای دریافتنی تجاری', 'ASSET', '1', 'مطالبات از مشتریان بابت فروش'),
    ('244bd22a-45d7-4536-80ce-14da0eae59cc', '1004', 'موجودی کالا', 'ASSET', '1', 'موجودی انبار به بهای تمامشده'),
    ('5202a386-82bd-4c7d-bccb-5d276dec0285', '1005', 'حساب واسط درگاه پرداخت', 'ASSET', '1', 'مبالغ در جریان وصول از درگاه پرداخت'),
    ('f55c6799-fee6-4d34-84dd-1e435ace42a8', '2', 'بدهیهای جاری', 'LIABILITY', None, 'گروه حسابهای بدهی'),
    ('c02d6fbb-67e2-480d-8063-ca207b4be0ba', '2001', 'حسابهای پرداختنی تجاری', 'LIABILITY', '2', 'بدهی به تامینکنندگان بابت خرید'),
    ('126dd69a-79b5-4800-a21f-8d2a15bd23e8', '2002', 'مالیات بر ارزش افزوده پرداختنی', 'LIABILITY', '2', 'مالیات ارزش افزوده فروش قابل پرداخت به سازمان امور مالیاتی'),
    ('3d889afe-d26d-4cc6-8c90-038335c286ab', '2003', 'کیف پول کاربران', 'LIABILITY', '2', 'مانده کیف پول کاربران (بدهی به کاربران)'),
    ('f8590133-970f-40fb-9923-9f8053ff1af8', '2004', 'بدهی به فروشندگان', 'LIABILITY', '2', 'مبالغ قابل پرداخت به فروشندگان پس از کسر کارمزد'),
    ('a3ae38ad-3931-413e-b6da-b94b7fbb39a7', '3', 'حقوق صاحبان سهام', 'EQUITY', None, 'گروه حسابهای سرمایه'),
    ('bef2985f-098c-402f-b6c3-b44cf98e087e', '3001', 'سرمایه', 'EQUITY', '3', 'سرمایه اولیه و افزایش سرمایه'),
    ('040053ac-e2f7-460c-a982-21ac4df8dbac', '4', 'درآمدها', 'REVENUE', None, 'گروه حسابهای درآمد'),
    ('636aee9a-30f5-4ed5-8f30-ea864e554479', '4001', 'فروش کالا', 'REVENUE', '4', 'درآمد فروش کالا و خدمات'),
    ('32382862-5971-4e46-825b-6bf1c6756f6e', '4002', 'برگشت فروش', 'REVENUE', '4', 'برگشت از فروش (حساب کاهنده درآمد)'),
    ('abf5c078-42ce-4a39-9f9e-72fbd7777216', '4003', 'تخفیف فروش', 'REVENUE', '4', 'تخفیفهای اعطایی به مشتریان (حساب کاهنده درآمد)'),
    ('c89156f2-7507-487f-9d00-cba171936d23', '4004', 'درآمد حمل', 'REVENUE', '4', 'هزینه حمل دریافتشده از مشتری'),
    ('82e4bfbf-069a-4aec-8c6f-5fd539adb8c6', '5', 'هزینهها', 'EXPENSE', None, 'گروه حسابهای هزینه'),
    ('e78bebb2-551e-433b-9bda-8a59d57713aa', '5001', 'هزینه حمل', 'EXPENSE', '5', 'هزینه حمل پرداختشده به پیک'),
    ('aff57c27-cd46-4fa9-8553-78affb1695ab', '5002', 'کارمزد درگاه پرداخت', 'EXPENSE', '5', 'کارمزد دریافتی شرکتهای PSP'),
    ('a546867f-55fb-4379-9001-104d857a4c64', '5003', 'کارمزد بانکی', 'EXPENSE', '5', 'کارمزد خدمات بانکی'),
)


def upgrade() -> None:
    # Indexes first (parent_id, type, is_active), then the table. The only FK
    # ever pointing at ``accounts`` (journal_lines.account_id) died with
    # ``rmjournal1``, so no child table blocks the drop.
    op.drop_index("ix_accounts_is_active", table_name="accounts")
    op.drop_index("ix_accounts_parent_id", table_name="accounts")
    op.drop_index("ix_accounts_type", table_name="accounts")
    op.drop_table("accounts")

    # The permissions leave with the feature they guarded. role_permissions
    # has ON DELETE CASCADE on permission_id, so the admin grants go too.
    op.execute(
        sa.text("DELETE FROM permissions WHERE slug IN ('accounting:read', 'accounting:write')")
    )


def downgrade() -> None:
    """Recreate ``accounts`` exactly as ``a9c1e3f5b7d9`` defined it, then
    restore its 22 seed rows and the two permission rows + admin grants."""
    op.create_table(
        "accounts",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "ASSET",
                "LIABILITY",
                "EQUITY",
                "REVENUE",
                "EXPENSE",
                name="account_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_accounts_code"),
    )
    op.create_index("ix_accounts_type", "accounts", ["type"])
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])
    op.create_index("ix_accounts_is_active", "accounts", ["is_active"])

    # Seed rows with their original ids. Parents are inserted in code order
    # (groups "1".."5" come before their leaves), so every parent_id resolves
    # within the same pass.
    by_code = {code: acct_id for acct_id, code, _n, _t, _p, _d in _ACCOUNTS_SEED}
    for acct_id, code, name_fa, acct_type, parent_code, description in _ACCOUNTS_SEED:
        op.execute(
            sa.text(
                "INSERT INTO accounts (id, code, name_fa, type, parent_id, is_active,"
                " description, created_at, updated_at)"
                " VALUES (CAST(:id AS uuid), :code, :name_fa, :type,"
                " CAST(:parent_id AS uuid), true, :description, now(), now())"
            ).bindparams(
                id=acct_id,
                code=code,
                name_fa=name_fa,
                type=acct_type,
                parent_id=by_code[parent_code] if parent_code else None,
                description=description,
            )
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
