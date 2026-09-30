"""DMS v1: polymorphic attachments and the fiscal archive index.

ERP benchmark gap analysis (feature #25 Document management, P2). The media
module is image-oriented and ``TicketAttachment`` is bound to one message;
neither answers "attach this PO/invoice/return document to any business
record" or "search frozen fiscal documents across modules".

- ``attachments``: a working document attached to any record via
  (entity_type, entity_id). Deliberately not an FK — see the module
  docstring; the type is validated against a registry at the API.
- ``archived_documents``: the immutable index over frozen fiscal artifacts.
  Unique ``(kind, document_key)`` means two archived invoices cannot claim the
  same number. No delete route exists by design.

Revision ID: b3d5f7a9c1e4
Revises: a2c4e6f8b1d3
Create Date: 2026-09-25 05:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b3d5f7a9c1e4"
down_revision = "a2c4e6f8b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. attachments ────────────────────────────────────────────────────
    op.create_table(
        "attachments",
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="GENERAL"),
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

    # ── 2. archived_documents ─────────────────────────────────────────────
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
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fiscal_period", sa.String(length=20), nullable=True),
        sa.Column(
            "is_superseded", sa.Boolean(), nullable=False, server_default=sa.text("false")
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


def downgrade() -> None:
    op.drop_index("ix_archived_documents_document_key", table_name="archived_documents")
    op.drop_index("ix_archived_documents_kind", table_name="archived_documents")
    op.drop_index("ix_archived_documents_entity", table_name="archived_documents")
    op.drop_table("archived_documents")

    op.drop_index("ix_attachments_uploaded_by_id", table_name="attachments")
    op.drop_index("ix_attachments_kind", table_name="attachments")
    op.drop_index("ix_attachments_entity", table_name="attachments")
    op.drop_table("attachments")
