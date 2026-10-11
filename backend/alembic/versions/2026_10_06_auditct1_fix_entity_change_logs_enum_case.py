"""Fix entity_change_logs enum storage: lowercase values -> member NAMES.

The live table carried CHECK constraints and column defaults that used the
enum *values* ('update', 'user', 'api'), while every Enum column in this
project stores member *names* — SQLAlchemy's ``Enum(..., native_enum=False)``
without ``values_callable`` persists 'UPDATE', 'USER', 'API'. The ORM bind
processor therefore sent UPPERCASE values into lowercase CHECKs, and every
capture insert raised CheckViolationError.

The capture hook is fail-soft by contract (it must never block a business
flush), so the failure surfaced only as a warning log and a permanently empty
table — which is exactly how it went unnoticed: ``entity_change_logs`` held
zero rows from creation until this fix, and the admin "تاریخچه تغییرات فیلدها"
tab showed its empty state forever.

The migration file that created the table (``c5e9a2b3d7f1``) already declares
UPPERCASE constraints — the live database had drifted from it. This migration
brings the live schema in line with the file and the ORM. Same class of fix
as ``c5f7a9b1d3e6`` (enum server defaults aligned to member names).

Reversible: ``downgrade()`` restores the lowercase constraint text and
defaults that the live database had at fix time, and lowercases any stored
values so the old constraints accept every row.

Revision ID: auditct1
Revises: rmdms1
Create Date: 2026-10-06
"""

from __future__ import annotations

from alembic import op

revision = "auditct1"
down_revision = "rmdms1"
branch_labels = None
depends_on = None

#: (constraint name, column, new members, old members) — old = what the live
#: database carried at fix time (the lowercase enum *values*).
_CONSTRAINTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "ck_entity_change_logs_operation",
        "operation",
        "'CREATE', 'UPDATE', 'DELETE'",
        "'create', 'update', 'delete'",
    ),
    (
        "ck_entity_change_logs_actor_type",
        "actor_type",
        "'USER', 'SYSTEM', 'CELERY'",
        "'user', 'system', 'celery'",
    ),
    (
        "ck_entity_change_logs_source",
        "source",
        "'API', 'ADMIN', 'SERVICE', 'SEED'",
        "'api', 'admin', 'service', 'seed'",
    ),
)


def upgrade() -> None:
    # Order matters: the OLD (lowercase) constraints must be dropped BEFORE
    # the normalising UPDATE runs. Doing the UPDATE first would itself violate
    # the constraint it is about to replace. (The live table was empty when
    # this ran, so the wrong order worked by accident — a migration that only
    # works on an empty table is a trap.)
    for name, _column, _new, _old in _CONSTRAINTS:
        op.drop_constraint(op.f(name), "entity_change_logs", type_="check")

    for _, column, _, _ in _CONSTRAINTS:
        op.execute(
            f"UPDATE entity_change_logs SET {column} = upper({column}) "
            f"WHERE {column} <> upper({column})"
        )

    for name, column, new_members, _old in _CONSTRAINTS:
        # op.f() marks the name literal so the naming convention does not
        # re-prefix it (ck_entity_change_logs_ck_entity_change_logs_...).
        op.create_check_constraint(
            op.f(name), "entity_change_logs", f"{column} IN ({new_members})"
        )

    # Defaults must also store what the column actually stores: a non-ORM
    # INSERT that omits the column would otherwise fill a value the CHECK
    # (and the ORM reader) rejects.
    op.alter_column("entity_change_logs", "operation", server_default="UPDATE")
    op.alter_column("entity_change_logs", "actor_type", server_default="SYSTEM")
    op.alter_column("entity_change_logs", "source", server_default="SERVICE")


def downgrade() -> None:
    # Mirror of upgrade: drop the new constraints first, then normalise the
    # stored values down, then recreate the old constraints.
    for name, _column, _new, _old in _CONSTRAINTS:
        op.drop_constraint(op.f(name), "entity_change_logs", type_="check")

    for _, column, _, _ in _CONSTRAINTS:
        op.execute(
            f"UPDATE entity_change_logs SET {column} = lower({column}) "
            f"WHERE {column} <> lower({column})"
        )

    for name, column, _new, old_members in _CONSTRAINTS:
        op.create_check_constraint(
            op.f(name), "entity_change_logs", f"{column} IN ({old_members})"
        )

    op.alter_column("entity_change_logs", "operation", server_default="update")
    op.alter_column("entity_change_logs", "actor_type", server_default="system")
    op.alter_column("entity_change_logs", "source", server_default="service")
