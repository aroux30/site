"""CMS parity completion: newsletter, switchable themes, translation groups

Revision ID: c4d81f52a9b7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-27 21:30:00.000000+03:30

Adds the three schema pieces behind the WordPress-parity gap fixes:

- ``newsletter_subscribers`` — double opt-in list; the email address is the
  primary key (a subscription's identity IS the address) and the confirm
  token is a server-computed HMAC, so lifecycle lookups are PK fetches.
- ``site_themes`` — switchable token-set themes; activation copies tokens
  into the ``theme`` single type the storefront already consumes.
- ``translation_group`` on ``blog_posts``/``cms_pages`` — rows sharing a
  group are translations of one another (i18n).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4d81f52a9b7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "newsletter_subscribers",
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "SUBSCRIBED", "UNSUBSCRIBED",
                name="newsletter_status_enum", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("confirm_token", sa.String(64), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(50), server_default="'footer'", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("email"),
        sa.UniqueConstraint("confirm_token", name="uq_newsletter_subscribers_confirm_token"),
    )
    op.create_index(
        "ix_newsletter_subscribers_status", "newsletter_subscribers", ["status"]
    )
    op.create_index(
        "ix_newsletter_subscribers_created_at", "newsletter_subscribers", ["created_at"]
    )

    op.create_table(
        "site_themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_site_themes_slug"),
    )
    op.create_index("ix_site_themes_slug", "site_themes", ["slug"])
    op.create_index("ix_site_themes_is_active", "site_themes", ["is_active"])

    op.add_column(
        "blog_posts",
        sa.Column("translation_group", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_blog_posts_translation_group", "blog_posts", ["translation_group"]
    )

    op.add_column(
        "cms_pages",
        sa.Column("translation_group", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_cms_pages_translation_group", "cms_pages", ["translation_group"]
    )


def downgrade() -> None:
    op.drop_index("ix_cms_pages_translation_group", table_name="cms_pages")
    op.drop_column("cms_pages", "translation_group")
    op.drop_index("ix_blog_posts_translation_group", table_name="blog_posts")
    op.drop_column("blog_posts", "translation_group")
    op.drop_index("ix_site_themes_is_active", table_name="site_themes")
    op.drop_index("ix_site_themes_slug", table_name="site_themes")
    op.drop_table("site_themes")
    op.drop_index("ix_newsletter_subscribers_created_at", table_name="newsletter_subscribers")
    op.drop_index("ix_newsletter_subscribers_status", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")
    sa.Enum(name="newsletter_status_enum").drop(op.get_bind(), checkfirst=True)
