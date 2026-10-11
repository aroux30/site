"""Remove the Documents & Attachments (DMS) module (decision 2026-10-06).

The owner asked for «اسناد و پیوست‌ها» to be deleted outright — it has no use
in a retail storefront. The code is archived under
``_archived/dms-documents-2026-10-06/``.

What the module was:

- **``attachments``** — polymorphic working documents attached to any business
  record via ``(entity_type, entity_id)``. Its registry of attachable types
  listed order/return/purchase_order/vendor_settlement/invoice/receipt/... —
  purchase orders died with the logistics removal, returns with the RMA
  removal, invoices with the invoicing removal. No page in the whole app ever
  offered an "attach file" UI, and ``create_attachment`` had no caller outside
  the module's own routes.
- **``archived_documents``** — the immutable fiscal archive index. Its only
  writer was the invoicing module, removed 2026-10-04; since then the table
  had **zero writers in the codebase** and the "بایگانی اسناد مالی" tab was
  empty by construction.

Verified at removal time (live probe 2026-10-06):
- ``attachments`` = 0 rows, ``archived_documents`` = 0 rows. Dropping both
  loses nothing.
- The two permission rows (``documents:read`` id
  ``91902960-2b32-48a8-b46e-fee282203ca4``, ``documents:write`` id
  ``f9628304-a0c4-4b3d-ae02-7a7454f7a365``) had 2 grants, both on the seeded
  ``admin`` role (``51ab099d-92ff-4361-9d02-9dbc07263f50``); the
  ``role_permissions`` rows cascade on ``permission_id``.

``downgrade()`` recreates both tables exactly as ``b3d5f7a9c1e4`` defined
them — same columns, types, lengths, check constraints, unique constraint,
FK, indexes — and re-inserts the two permission rows with their observed
UUIDs plus the admin-role grants (``ON CONFLICT DO NOTHING``, so a database
that already has the rows is left alone).

Chain: ``rmprivacy1 → rmnews1 → rmdms1`` — the supervisor ordered session 3's
newsletter removal to land first so the two drops never form parallel heads.

Revision ID: rmdms1
Revises: rmnews1
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmdms1"
down_revision = "rmnews1"
branch_labels = None
depends_on = None


#: The permission rows as they existed at removal (verified against the live
#: database; ids captured to ``_capture_dms_perms.json`` in the archive).
_PERMISSIONS: list[dict[str, str]] = [
    {
        "id": "91902960-2b32-48a8-b46e-fee282203ca4",
        "slug": "documents:read",
        "resource": "documents",
        "action": "read",
        "name": "مشاهده اسناد و پیوست‌ها",
        "description": "مشاهده پیوست‌های پرونده‌ها و جست‌وجو در بایگانی اسناد مالی",
    },
    {
        "id": "f9628304-a0c4-4b3d-ae02-7a7454f7a365",
        "slug": "documents:write",
        "resource": "documents",
        "action": "write",
        "name": "مدیریت اسناد و پیوست‌ها",
        "description": "افزودن و حذف پیوست روی رکوردهای کسب‌وکار",
    },
]


def upgrade() -> None:
    # Children first: indexes, then the table. Both tables held 0 rows at
    # removal time, so nothing is copied out.
    op.drop_index("ix_archived_documents_document_key", table_name="archived_documents")
    op.drop_index("ix_archived_documents_kind", table_name="archived_documents")
    op.drop_index("ix_archived_documents_entity", table_name="archived_documents")
    op.drop_table("archived_documents")

    op.drop_index("ix_attachments_uploaded_by_id", table_name="attachments")
    op.drop_index("ix_attachments_kind", table_name="attachments")
    op.drop_index("ix_attachments_entity", table_name="attachments")
    op.drop_table("attachments")

    # The permission rows leave with the features they guarded.
    # role_permissions has ON DELETE CASCADE on permission_id, so the admin
    # grants go with them.
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE slug IN ('documents:read', 'documents:write')"
        )
    )


def downgrade() -> None:
    """Recreate both tables exactly as ``b3d5f7a9c1e4_dms_v1`` defined them.

    Schema-faithful: same column order, types, lengths, defaults, check
    constraints, unique constraint, FK and indexes. The 0 rows are trivially
    restored (there were none); the two permission rows are re-inserted with
    their observed UUIDs.
    """
    op.create_table(
        "attachments",
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind", sa.String(length=32), nullable=False, server_default="GENERAL"
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint(
            "entity_type <> ''", name=op.f("ck_attachments_entity_type_not_empty")
        ),
        sa.CheckConstraint(
            "kind IN ('GENERAL', 'CONTRACT', 'INVOICE', 'RECEIPT', "
            "'SHIPPING_LABEL', 'INSPECTION', 'RETURN_FORM', 'OTHER')",
            name=op.f("ck_attachments_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_attachments_uploaded_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachments")),
    )
    op.create_index(
        "ix_attachments_entity", "attachments", ["entity_type", "entity_id"]
    )
    op.create_index("ix_attachments_kind", "attachments", ["kind"])
    op.create_index("ix_attachments_uploaded_by_id", "attachments", ["uploaded_by_id"])

    op.create_table(
        "archived_documents",
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("document_key", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archive_path", sa.String(length=500), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=150),
            nullable=False,
            server_default="text/html",
        ),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("fiscal_period", sa.String(length=20), nullable=True),
        sa.Column(
            "is_superseded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
        sa.CheckConstraint(
            "entity_type <> ''",
            name=op.f("ck_archived_documents_entity_type_not_empty"),
        ),
        sa.CheckConstraint(
            "kind IN ('INVOICE', 'CREDIT_NOTE', 'RECEIPT', 'SETTLEMENT', 'OTHER')",
            name=op.f("ck_archived_documents_kind"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_archived_documents")),
        # Two archived invoices may never claim the same number.
        sa.UniqueConstraint(
            "kind", "document_key", name="uq_archived_documents_kind_key"
        ),
    )
    op.create_index(
        "ix_archived_documents_entity",
        "archived_documents",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_archived_documents_kind", "archived_documents", ["kind"])
    op.create_index(
        "ix_archived_documents_document_key", "archived_documents", ["document_key"]
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
        # blanket grant to ADMIN_ROLE_SLUG. A missing role (a database that
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
