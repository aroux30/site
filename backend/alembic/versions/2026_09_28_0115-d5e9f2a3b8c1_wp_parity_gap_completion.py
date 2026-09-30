"""WordPress-parity gap completion: comments, campaigns, rules, caps, i18n

Revision ID: d5e9f2a3b8c1
Revises: c4d81f52a9b7
Create Date: 2026-09-28 01:15:00.000000+03:30

Schema behind the eleven partial-gap completions:

- ``blog_comments`` — polymorphic (``resource_type``/``resource_id``) so CMS
  pages accept comments; ``post_id`` becomes nullable; threaded replies via
  the existing ``parent_id`` stay unchanged.
- ``blog_post_revisions`` — SEO title/description snapshots for revision diff.
- ``newsletter_campaigns`` / ``newsletter_campaign_recipients`` — campaign
  mailouts to the confirmed subscriber list with per-recipient tracking.
- ``user_permission_overrides`` — per-user grant/deny capability overrides
  (deny wins over role-derived permissions).
- ``automation_rules`` — declarative trigger → conditions → actions engine.
- ``localization_strings`` — backend UI-string catalogue (key, locale).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e9f2a3b8c1"
down_revision: str | None = "c4d81f52a9b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. blog_comments → polymorphic resource ──────────────────────────
    op.alter_column("blog_comments", "post_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "blog_comments",
        sa.Column(
            "resource_type", sa.String(50), nullable=False, server_default="'blog_post'"
        ),
    )
    # Nullable first, backfill from post_id, then enforce NOT NULL.
    op.add_column("blog_comments", sa.Column("resource_id", sa.UUID(), nullable=True))
    op.execute(
        "UPDATE blog_comments SET resource_id = post_id "
        "WHERE resource_id IS NULL AND post_id IS NOT NULL"
    )
    op.alter_column("blog_comments", "resource_id", existing_type=sa.UUID(), nullable=False)
    op.create_index(
        "ix_blog_comments_resource", "blog_comments", ["resource_type", "resource_id"]
    )
    op.create_check_constraint(
        "resource_consistency",
        "blog_comments",
        "((resource_type = 'blog_post' AND post_id IS NOT NULL AND resource_id = post_id) "
        "OR (resource_type = 'cms_page' AND post_id IS NULL AND resource_id IS NOT NULL))",
    )

    # ── 2. blog_post_revisions — SEO snapshots for revision diff ─────────
    op.add_column(
        "blog_post_revisions", sa.Column("seo_title", sa.String(200), nullable=True)
    )
    op.add_column(
        "blog_post_revisions",
        sa.Column("seo_description", sa.String(500), nullable=True),
    )

    # ── 3. newsletter_campaigns ──────────────────────────────────────────
    op.create_table(
        "newsletter_campaigns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("preheader", sa.String(255), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "SCHEDULED", "SENDING", "SENT", "FAILED",
                name="newsletter_campaign_status_enum", native_enum=False,
            ),
            server_default=sa.text("'draft'"),
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
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_newsletter_campaigns_created_by_users", ondelete="SET NULL",
        ),
    )
    op.create_index("ix_newsletter_campaigns_status", "newsletter_campaigns", ["status"])
    op.create_index(
        "ix_newsletter_campaigns_scheduled_at", "newsletter_campaigns", ["scheduled_at"]
    )

    # ── 4. newsletter_campaign_recipients ────────────────────────────────
    op.create_table(
        "newsletter_campaign_recipients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("subscriber_id", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "SENT", "FAILED",
                name="newsletter_campaign_recipient_status_enum", native_enum=False,
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["newsletter_campaigns.id"],
            # 63-char identifier limit: the convention-derived name for this FK
            # is 65 characters and PostgreSQL rejects it.
            name="fk_newsletter_recipients_campaign_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"], ["newsletter_subscribers.email"],
            # Convention name is 71 characters; see comment above.
            name="fk_newsletter_recipients_subscriber_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "campaign_id", "subscriber_id",
            name="uq_newsletter_campaign_recipients_campaign_id_subscriber_id",
        ),
    )
    op.create_index(
        "ix_newsletter_campaign_recipients_subscriber_id",
        "newsletter_campaign_recipients",
        ["subscriber_id"],
    )

    # ── 5. user_permission_overrides ─────────────────────────────────────
    op.create_table(
        "user_permission_overrides",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("permission", sa.String(100), nullable=False),
        sa.Column(
            "effect",
            sa.Enum(
                "GRANT", "DENY",
                name="user_permission_override_effect_enum", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_permission_overrides_user_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_user_permission_overrides_created_by_users", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "user_id", "permission", name="uq_user_permission_overrides_user_perm"
        ),
    )
    op.create_index(
        "ix_user_permission_overrides_permission",
        "user_permission_overrides",
        ["permission"],
    )

    # ── 6. automation_rules ──────────────────────────────────────────────
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "ORDER_PAID", "ORDER_CREATED", "USER_REGISTERED",
                "REVIEW_CREATED", "STOCK_LOW",
                name="automation_trigger_type_enum", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("actions", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_automation_rules_trigger_active", "automation_rules", ["trigger_type", "is_active"]
    )
    op.create_index("ix_automation_rules_name", "automation_rules", ["name"])

    # ── 7. localization_strings ──────────────────────────────────────────
    op.create_table(
        "localization_strings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("group", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "locale", name="uq_localization_strings_key_locale"),
    )
    op.create_index("ix_localization_strings_locale", "localization_strings", ["locale"])
    op.create_index("ix_localization_strings_group", "localization_strings", ["group"])


def downgrade() -> None:
    # localization_strings / automation_rules / user_permission_overrides /
    # newsletter_campaign_recipients / newsletter_campaigns
    op.drop_index("ix_localization_strings_group", table_name="localization_strings")
    op.drop_index("ix_localization_strings_locale", table_name="localization_strings")
    op.drop_table("localization_strings")

    op.drop_index("ix_automation_rules_name", table_name="automation_rules")
    op.drop_index("ix_automation_rules_trigger_active", table_name="automation_rules")
    op.drop_table("automation_rules")

    op.drop_index(
        "ix_user_permission_overrides_permission", table_name="user_permission_overrides"
    )
    op.drop_table("user_permission_overrides")

    op.drop_index(
        "ix_newsletter_campaign_recipients_subscriber_id",
        table_name="newsletter_campaign_recipients",
    )
    op.drop_table("newsletter_campaign_recipients")
    op.drop_index("ix_newsletter_campaigns_scheduled_at", table_name="newsletter_campaigns")
    op.drop_index("ix_newsletter_campaigns_status", table_name="newsletter_campaigns")
    op.drop_table("newsletter_campaigns")

    op.drop_column("blog_post_revisions", "seo_description")
    op.drop_column("blog_post_revisions", "seo_title")

    op.drop_constraint("resource_consistency", "blog_comments", type_="check")
    op.drop_index("ix_blog_comments_resource", table_name="blog_comments")
    op.drop_column("blog_comments", "resource_id")
    op.drop_column("blog_comments", "resource_type")
    # Only reversible while no cms_page comments exist (post_id back to NOT NULL).
    op.execute("UPDATE blog_comments SET post_id = resource_id WHERE post_id IS NULL")
    op.alter_column("blog_comments", "post_id", existing_type=sa.UUID(), nullable=False)
