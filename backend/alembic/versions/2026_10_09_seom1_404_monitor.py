"""404 monitor table + SEO settings storage (SEO menu build-out, 2026-10-09).

The owner asked for a proper SEO menu like Rank Math's. Of its five panels,
two existed (redirects, and a scoring page that was removed for being
incomplete), and the missing ones need storage:

* ``seo_404_logs`` — the 404 monitor. Rank Math records every not-found hit
  with the path, referrer and count so an operator can turn a broken link
  into a redirect. Without it a 404 is invisible: the reader leaves and
  nothing reports it. One row per distinct path (a counter, not a log
  flood): the table answers "what is broken", not "what happened at 03:12".

* ``seo_settings`` site options — the SEO defaults panel writes
  ``seo_default_title_template`` and ``seo_default_description_template``
  into ``site_options`` (no new table; the options service already exists).

Chain: ``seokw3 -> seom1`` (seokw3 was the head when this landed).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seom1"
down_revision: str | None = "seokw3"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seo_404_logs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("path", sa.String(500), nullable=False),
        # The referring URL when the crawler or reader sent one; null for a
        # direct hit. Long URLs are truncated by the writer, not here.
        sa.Column("referrer", sa.String(500), nullable=True),
        # The user agent, trimmed — enough to tell Googlebot from a reader.
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # One row per path: the unique key is what makes the upsert a counter.
        sa.UniqueConstraint("path", name="uq_seo_404_logs_path"),
    )
    op.create_index("ix_seo_404_logs_last_seen", "seo_404_logs", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_seo_404_logs_last_seen", table_name="seo_404_logs")
    op.drop_table("seo_404_logs")
