"""add source_asset_id and edit_operation to media_assets

Non-destructive editing produced a new MediaAsset row per crop/resize/rotate
with no link to what it was made from. The files were there, but the chain was
not, which is why there was no "restore the original" and no undo: the editor
could see every result and could not relate any of them to any other.

source_asset_id is self-referential, so a chain of any depth resolves in one
hop per level and no join table is needed. SET NULL rather than CASCADE: the
parent is a lineage pointer, not an ownership one, and a cascade would delete a
child whose parent was removed.

RevisionLimit:
- Type: added Columns
- Table: media_assets
- Nullable: yes — every pre-existing row is an original, which is exactly
  "no parent".

ColumnLimit:
- Column: media_assets.source_asset_id
- Type: uuid
- Nullable: yes (FK media_assets.id, ondelete SET NULL)

- Column: media_assets.edit_operation
- Type: varchar(20)
- Nullable: yes

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m7n8o9p0q1r2"
down_revision = "q7w8e9r0t1y2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_assets",
        sa.Column("source_asset_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "media_assets",
        sa.Column("edit_operation", sa.String(length=20), nullable=True),
    )
    op.create_foreign_key(
        "fk_media_assets_source_asset",
        "media_assets",
        "media_assets",
        ["source_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # The history panel walks children of a root, and the delete guard asks
    # "what points at this file" — both lead with source_asset_id.
    op.create_index(
        "ix_media_assets_source_asset_id", "media_assets", ["source_asset_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_media_assets_source_asset_id", table_name="media_assets")
    op.drop_constraint(
        "fk_media_assets_source_asset", "media_assets", type_="foreignkey"
    )
    op.drop_column("media_assets", "edit_operation")
    op.drop_column("media_assets", "source_asset_id")