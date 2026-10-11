"""Remove the Newsletter module (owner decision 2026-10-06).

The owner asked for «خبرنامه» to be deleted outright — it has no use in this
retail storefront. The code is archived under
``_archived/newsletter-removal-2026-10-06/``.

What goes with this migration:

- **``newsletter_campaign_recipients``** — per-recipient delivery rows.
  Verified at removal time (live probe 2026-10-06): 0 rows.
- **``newsletter_campaigns``** — mailout headers. 0 rows.
- **``newsletter_subscribers``** — the double opt-in list. 1 row, a parity
  test fixture (``test-check@example.com``, status PENDING, never confirmed,
  source 'footer'). The full row is in the archive's
  ``db_snapshot_before.json`` and is restored by ``downgrade()``.
- **``newsletter:read`` / ``newsletter:write`` permissions** — deleted from
  ``permissions``; the two ``role_permissions`` grant rows (both to the
  system admin role) cascade away with them (FK
  ``fk_role_permissions_permission_id_permissions`` ON DELETE CASCADE).
  Zero ``user_permission_overrides`` rows referenced them.
- The two newsletter Celery tasks (``send_newsletter_campaign``,
  ``dispatch_due_scheduled_campaigns``) and the beat entry
  ``dispatch-due-newsletter-campaigns`` are removed from
  ``app/worker/celery_app.py`` in the same change set.

``downgrade()`` recreates all three tables exactly as the live database had
them at removal time (constraints, indexes, enum storage as member NAMES per
this schema's enum-storage contract — the ``x5y6z7a8b9c0`` status-case fix is
baked in), re-inserts the single subscriber fixture row and the two permission
rows + admin grants with their exact ids and timestamps from the snapshot.

Revision ID: rmnews1
Revises: rmtelegram1
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmnews1"
down_revision = "rmtelegram1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Children first: recipients references both campaigns and subscribers.
    op.drop_index(
        "ix_newsletter_campaign_recipients_subscriber_id",
        table_name="newsletter_campaign_recipients",
    )
    op.drop_table("newsletter_campaign_recipients")

    op.drop_index("ix_newsletter_campaigns_scheduled_at", table_name="newsletter_campaigns")
    op.drop_index("ix_newsletter_campaigns_status", table_name="newsletter_campaigns")
    op.drop_table("newsletter_campaigns")

    op.drop_index("ix_newsletter_subscribers_created_at", table_name="newsletter_subscribers")
    op.drop_index("ix_newsletter_subscribers_status", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")

    # Permissions; role_permissions grant rows cascade away with the FK.
    op.execute("DELETE FROM permissions WHERE slug LIKE 'newsletter:%'")


def downgrade() -> None:
    """Recreate the three tables + permission rows as of removal time.

    Enum columns are VARCHAR + CHECK (``native_enum=False``); stored values
    are the member *names* (``PENDING``/``SUBSCRIBED``/``UNSUBSCRIBED``,
    ``DRAFT``/``SCHEDULED``/``SENDING``/``SENT``/``FAILED``), and the status
    defaults are the uppercase server defaults the live schema carried
    (baked in by ``x5y6z7a8b9c0``).
    """
    op.create_table(
        "newsletter_subscribers",
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SUBSCRIBED",
                "UNSUBSCRIBED",
                name="newsletter_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("confirm_token", sa.String(64), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source",
            sa.String(50),
            # Byte-for-byte the live default: the creating migration passed
            # server_default="'footer'" (a plain string), so SQLAlchemy
            # double-quoted it into the literal `'footer'` — quotes included.
            server_default=sa.text("'''footer'''::character varying"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("email", name="pk_newsletter_subscribers"),
        sa.UniqueConstraint("confirm_token", name="uq_newsletter_subscribers_confirm_token"),
    )
    op.create_index(
        "ix_newsletter_subscribers_status", "newsletter_subscribers", ["status"]
    )
    op.create_index(
        "ix_newsletter_subscribers_created_at", "newsletter_subscribers", ["created_at"]
    )

    op.create_table(
        "newsletter_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("preheader", sa.String(255), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "SCHEDULED",
                "SENDING",
                "SENT",
                "FAILED",
                name="newsletter_campaign_status_enum",
                native_enum=False,
            ),
            server_default=sa.text("'DRAFT'::character varying"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "total_recipients", sa.Integer(), server_default=sa.text("'0'"), nullable=False
        ),
        sa.Column("total_sent", sa.Integer(), server_default=sa.text("'0'"), nullable=False),
        sa.Column(
            "total_failed", sa.Integer(), server_default=sa.text("'0'"), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_newsletter_campaigns"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_newsletter_campaigns_created_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_newsletter_campaigns_status", "newsletter_campaigns", ["status"])
    op.create_index(
        "ix_newsletter_campaigns_scheduled_at", "newsletter_campaigns", ["scheduled_at"]
    )

    op.create_table(
        "newsletter_campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscriber_id", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SENT",
                "FAILED",
                name="newsletter_campaign_recipient_status_enum",
                native_enum=False,
            ),
            server_default=sa.text("'PENDING'::character varying"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_newsletter_campaign_recipients"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["newsletter_campaigns.id"],
            # 63-char identifier limit: the convention-derived name for this FK
            # is 65 characters and PostgreSQL rejects it.
            name="fk_newsletter_recipients_campaign_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"],
            ["newsletter_subscribers.email"],
            # Convention name is 71 characters; see comment above.
            name="fk_newsletter_recipients_subscriber_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "subscriber_id",
            name="uq_newsletter_campaign_recipients_campaign_id_subscriber_id",
        ),
    )
    op.create_index(
        "ix_newsletter_campaign_recipients_subscriber_id",
        "newsletter_campaign_recipients",
        ["subscriber_id"],
    )

    # The one subscriber row (parity fixture), exactly as snapshotted.
    op.execute(
        """
        INSERT INTO newsletter_subscribers
            (email, status, confirm_token, confirmed_at, unsubscribed_at, source,
             created_at, updated_at)
        VALUES (
            'test-check@example.com', 'PENDING',
            '5RX1eARUP6xfLb2BKbMaLRk1aQy9yGIl1qZL76F2bTU',
            NULL, NULL, 'footer',
            '2026-09-27 19:41:09.486618+00', '2026-09-27 19:41:09.486618+00'
        )
        ON CONFLICT (email) DO NOTHING
        """
    )

    # The two permission rows + the admin grants, ids/timestamps from snapshot.
    op.execute(
        """
        INSERT INTO permissions
            (id, created_at, updated_at, description, resource, action, name, slug)
        VALUES
            ('be336b07-5550-4cb5-ad7b-ee9f02e0a97b',
             '2026-09-27 19:40:33.074711+00', '2026-09-27 19:40:33.074711+00',
             'مشاهده فهرست مشترکان خبرنامه و وضعیت عضویت آن‌ها',
             'newsletter', 'read', 'مشاهده خبرنامه', 'newsletter:read'),
            ('aa32b6d2-0786-4eab-8c24-cb1ed5fd6bab',
             '2026-09-27 19:40:33.074711+00', '2026-09-27 19:40:33.074711+00',
             'حذف مشترکان و مدیریت لیست خبرنامه',
             'newsletter', 'write', 'مدیریت خبرنامه', 'newsletter:write')
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions
            (id, role_id, permission_id, created_at, updated_at)
        VALUES
            ('200252ec-6e3a-4025-9bdd-504072539b10',
             '51ab099d-92ff-4361-9d02-9dbc07263f50',
             'be336b07-5550-4cb5-ad7b-ee9f02e0a97b',
             '2026-09-27 19:40:33.074711+00', '2026-09-27 19:40:33.074711+00'),
            ('fcc55121-2a87-4edd-b342-9a9fd9775812',
             '51ab099d-92ff-4361-9d02-9dbc07263f50',
             'aa32b6d2-0786-4eab-8c24-cb1ed5fd6bab',
             '2026-09-27 19:40:33.074711+00', '2026-09-27 19:40:33.074711+00')
        ON CONFLICT (id) DO NOTHING
        """
    )
