"""Hand a departing user's content to somebody else before they are deleted.

P0 "کاربران: حذف کاربر با واگذاری محتوا". Deleting a user set ``deleted_at`` and
stopped there. Thirty-four columns point at ``users`` with ``ON DELETE SET NULL``,
so every post, page, comment, review and reusable block they wrote silently
became ownerless — an article attributed to nobody, an edit history with a hole in
it, a comment thread that can no longer be traced.

WordPress handles this with " reassign author" on delete: you pick who inherits
the content, and the attribution is never lost. This is that, and it is offered
as an explicit step rather than a side effect, because the choice of heir is a
judgement an operator has to make.

**The column list is discovered, not written down.** A hardcoded tuple of
"the tables that hold content" is a list that rots: a new module adds an
``author_id``, nobody updates it, and that table joins the thirty-four. Reading
``information_schema`` at call time means the reassignment covers every column
that will actually be affected, including the one added next week.

Not every ``SET NULL`` column is content. ``order_status_history.changed_by`` and
``warehouse_transfers.created_by`` record *who performed an action*, and pointing
those at a successor would be a lie about the audit trail. So a column is
reassigned when its name says it denotes authorship — ``author``, ``owner``,
``uploader``, ``sender``, ``reviewer`` — and left alone when it records an action.
The list of names is a judgement and is written down, so it can be argued with; the
list of columns it applies to is not.

Rewriting history is deliberately *not* done. A revision or a status-history row
is a record of what happened; moving it to a different person would falsify it.
Only current, authorship-bearing rows move.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


#: Column-name fragments that denote authorship. A column matching one of these
#: is reassigned; everything else pointed at the departing user is left as it is.
#:
#: The excluded ones are the reason this list exists at all. `changed_by`,
#: `processed_by`, `created_by` and `approved_by` record *that a person did
#: something*, and moving them would rewrite the audit trail — a refund would
#: appear to have been issued by somebody who never saw it. `assigned_to` is a
#: current assignment rather than authorship, and `converted_user_id` is a
#: conversion outcome. Reassigning any of those to a successor is a different
#: operation and needs its own decision.
AUTHORSHIP_COLUMN_FRAGMENTS: tuple[str, ...] = (
    "author_id",
    "owner_id",
    "uploader_id",
    "sender_id",
    "reviewer_id",
    "approved_by_user",
)

#: Explicitly not authorship, even though a fragment above would match. Named
#: rather than implied by absence, because a future column called `approved_by`
#: would otherwise be swept up by the fragments without anybody deciding so.
NOT_AUTHORSHIP_COLUMNS: frozenset[tuple[str, str]] = frozenset(
    {
        ("lead_inquiries", "converted_user_id"),
        # Matches the `owner_id` fragment, so without this entry a departing
        # user's sales leads are handed to a successor. That is a business
        # decision, not a cleanup: the lead may have been assigned by hand.
        ("lead_inquiries", "owner_id"),
        ("support_tickets", "assigned_to"),
    }
)


@dataclass(frozen=True)
class ReassignableColumn:
    """One column whose authorship should move."""

    table: str
    column: str

    def __str__(self) -> str:  # pragma: no cover - used in log messages
        return f"{self.table}.{self.column}"


async def discover_authored_columns(db: AsyncSession) -> list[ReassignableColumn]:
    """Every ``users`` foreign key that denotes authorship and nulls on delete.

    Read from ``information_schema`` rather than from a list, for the reason in
    the module docstring: a list of tables is a list that stops being true.
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                JOIN information_schema.referential_constraints rc
                  ON tc.constraint_name = rc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND ccu.table_name = 'users'
                  AND rc.delete_rule = 'SET NULL'
                ORDER BY tc.table_name, kcu.column_name
                """
            )
        )
    ).fetchall()

    found: list[ReassignableColumn] = []
    for table, column in rows:
        if (table, column) in NOT_AUTHORSHIP_COLUMNS:
            continue
        if not any(fragment in column for fragment in AUTHORSHIP_COLUMN_FRAGMENTS):
            continue
        found.append(ReassignableColumn(table=table, column=column))
    return found


async def reassign_authored_content(
    db: AsyncSession,
    *,
    from_user_id: uuid.UUID,
    to_user_id: uuid.UUID,
    columns: list[ReassignableColumn] | None = None,
) -> dict[str, int]:
    """Point every authored row of ``from_user_id`` at ``to_user_id``.

    Returns ``{column: rows_moved}`` for the columns that actually moved, so the
    caller can log and show a real count rather than "reassigned". An empty dict
    means the departing user had authored nothing — which is a legitimate answer
    and not a failure.

    Raises ``ValueError`` if the two ids are equal: reassigning to oneself moves
    every row and reports nothing, and an operator who picks the same person twice
    would see a zero and conclude the tool is broken.
    """
    if from_user_id == to_user_id:
        raise ValueError(
            "the departing user and the heir must be different; reassigning to "
            "oneself moves nothing and reports nothing"
        )

    targets = columns if columns is not None else await discover_authored_columns(db)
    moved: dict[str, int] = {}
    for col in targets:
        result = await db.execute(
            text(
                "UPDATE {t} SET {c} = :to WHERE {c} = :frm".format(t=col.table, c=col.column)
            ),
            {"to": to_user_id, "frm": from_user_id},
        )
        count = int(result.rowcount or 0)
        if count:
            moved[str(col)] = count
    return moved


async def count_authored_content(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    columns: list[ReassignableColumn] | None = None,
) -> dict[str, int]:
    """How many authored rows a user has, per column.

    Read before the reassignment so the operator is told what is about to move.
    A count of zero is the common case for most staff accounts and worth showing
    anyway: "you have nothing to reassign" and "we did not look" are different
    answers.
    """
    targets = columns if columns is not None else await discover_authored_columns(db)
    counts: dict[str, int] = {}
    for col in targets:
        result = await db.execute(
            text("SELECT count(*) FROM {t} WHERE {c} = :u".format(t=col.table, c=col.column)),
            {"u": user_id},
        )
        n = int(result.scalar() or 0)
        if n:
            counts[str(col)] = n
    return counts


def summarise_reassignment(moved: dict[str, int]) -> str:
    """One Persian line for the operator, naming the real total.

    Reads the same dict the log records, so the number on screen and the number
    in the audit trail cannot disagree — which is the only reason either is worth
    having.
    """
    if not moved:
        return "محتوایی برای واگذاری وجود نداشت."
    total = sum(moved.values())
    parts = "، ".join("%s: %d" % (k, v) for k, v in sorted(moved.items()))
    return "%d ردیف محتوا واگذار شد (%s)." % (total, parts)
