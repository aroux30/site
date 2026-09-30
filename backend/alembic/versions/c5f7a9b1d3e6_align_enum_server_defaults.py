"""Align enum server defaults with the ORM's stored member names.

Every Enum(...) column in this project is declared ``native_enum=False`` without
``values_callable``, so SQLAlchemy persists the **member names** — 'DRAFT', not
'draft'. Fourteen columns were created with a lowercase ``server_default``,
which does not match what the column actually stores.

This is not cosmetic. The ORM always supplies an explicit value, so the default
is invisible in normal operation — but any row written outside the ORM (raw
SQL, a bulk INSERT, a restore from a dump that omits the column) receives the
lowercase default, and reading it back raises ``LookupError`` because
SQLAlchemy cannot map 'draft' onto ContentStatus.DRAFT. The shipping upgrade
hit exactly this: a NOT NULL column added with ``server_default="home"``
backfilled 173 rows with an unreadable value and the migration aborted.

Fixing the column defaults removes the trap for every future non-ORM write.

Revision ID: c5f7a9b1d3e6
Revises: c4e6a8b2d5f7
Create Date: 2026-09-25 04:00:00
"""

from __future__ import annotations

from alembic import op

revision = "c5f7a9b1d3e6"
down_revision = "c4e6a8b2d5f7"
branch_labels = None
depends_on = None

# (table, column, correct member name, previous lowercase default)
COLUMNS: list[tuple[str, str, str, str]] = [
    ("cms_pages", "status", "DRAFT", "draft"),
    ("cms_content_types", "kind", "COLLECTION", "collection"),
    ("cms_content_entries", "status", "DRAFT", "draft"),
    ("site_menus", "location", "HEADER_MAIN", "header_main"),
    ("webhook_deliveries", "status", "PENDING", "pending"),
    ("digital_cards", "status", "AVAILABLE", "available"),
    ("digital_cards", "delivery_type", "UNIQUE", "unique"),
    ("notices", "notice_type", "POPUP", "popup"),
    ("notices", "target_page", "ALL", "all"),
    ("payment_allocations", "status", "PENDING", "pending"),
    ("card_transfer_receipts", "status", "PENDING_REVIEW", "pending_review"),
    ("direct_invoices", "status", "UNPAID", "unpaid"),
    ("installment_plans", "status", "PENDING", "pending"),
    ("saved_payment_methods", "status", "ACTIVE", "active"),
]


def upgrade() -> None:
    for table, column, member_name, _old in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{member_name}'"
        )


def downgrade() -> None:
    for table, column, _member_name, old in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{old}'"
        )
