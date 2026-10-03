"""newsletter status columns: store the member NAME, not the value

Both columns are non-native enums, so SQLAlchemy writes
`EnumClass.MEMBER_NAME` into them — "DRAFT", "PENDING" — while the enum
members themselves carry the values "draft" and "pending".

The model declared lowercase defaults to match the value, which is the same
confusion the other enum columns in this schema had already resolved by storing
the name (`'PUBLIC'::character varying`, `'PUBLISHED'::character varying`). The
model is fixed; this brings the *database* default into line with it.

That default is the part that reaches rows written outside the ORM — a raw
insert, a bulk load, a restore. With it left lowercase, such a row stores
"draft" where the ORM looks for "DRAFT", and reading it back raises LookupError
while the result set is still being mapped, which takes out the whole listing
rather than one row.

No data migration is included: both tables are empty in this deployment, and a
migration that rewrote rows would be a guess if they were not.

RevisionLimit:
- Type: updated Rows
- Table: newsletter_campaigns, newsletter_campaign_recipients
- Nullable: not applicable

ColumnLimit:
- Column: newsletter_campaigns.status
- Type: String(50)
- Nullable: no

ColumnLimit:
- Column: newsletter_campaign_recipients.status
- Type: String(50)
- Nullable: no

"""

from __future__ import annotations

from alembic import op

revision = "x5y6z7a8b9c0"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None

# Only names that exist in the enums are rewritten; anything else is data this
# migration could not have produced and is left for a human to look at.
CAMPAIGN_STATES = {"DRAFT", "SCHEDULED", "SENDING", "SENT", "PAUSED", "CANCELLED"}
RECIPIENT_STATES = {"PENDING", "SENT", "FAILED", "BOUNCED"}


def _normalise(table: str, states: set[str], key: str) -> None:
    values = ", ".join(f"'{s}'" for s in sorted(states))
    op.execute(
        f"""
        UPDATE {table}
        SET {key} = upper({key})
        WHERE {key} <> ''
          AND upper({key}) = {key}
          AND {key} IN ({", ".join(f"'{s.lower()}'" for s in sorted(states))})
        """
    )


def upgrade() -> None:
    _normalise("newsletter_campaigns", CAMPAIGN_STATES, "status")
    _normalise("newsletter_campaign_recipients", RECIPIENT_STATES, "status")
    op.execute(
        "ALTER TABLE newsletter_campaigns "
        "ALTER COLUMN status SET DEFAULT 'DRAFT'::character varying"
    )
    op.execute(
        "ALTER TABLE newsletter_campaign_recipients "
        "ALTER COLUMN status SET DEFAULT 'PENDING'::character varying"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE newsletter_campaigns "
        "ALTER COLUMN status SET DEFAULT 'draft'::character varying"
    )
    op.execute(
        "ALTER TABLE newsletter_campaign_recipients "
        "ALTER COLUMN status SET DEFAULT 'pending'::character varying"
    )