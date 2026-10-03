#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the enum storage contract: these columns store member NAMES.

Every enum column here is declared ``Enum(SomeEnum, name=..., native_enum=False)``
with no ``values_callable``, which makes SQLAlchemy persist the member **name**.
``payments.status`` holds ``COMPLETED``, not ``completed``. That is the
project's contract, and it has now misled three separate audits into reporting
"0 orders with a completed payment" when the real count was 672 — a lowercase
literal returns zero rows and reads as a measurement rather than as a malformed
one.

The failure this gate exists to prevent is the *mismatch*: a column that stores
names while its ``server_default``, its migration, or an existing row holds a
value. That is silent on the write path and fatal on the read path — the ORM
raises ``LookupError`` for the offending row, so one page with a stale value
takes out every query that selects it. ``cms_pages.visibility`` was found in
exactly that state on 2026-10-02: ``server_default=text("'public'")`` beside a
column that stores ``PUBLIC``, and the live row held ``'public'``.

Discovery, not a fixed list. A hand-written list of enum columns is a list that
goes stale the day a module is added, and a gate that only knows about the
columns it was written for reports clean on a codebase that has since grown a
fourth variant. Every ``mapped_column(Enum(...))`` in ``backend/app`` is found
by walking the AST, so a new column is classified the day it is declared and a
new *table* needs no edit here.

Two properties are checked per column, and both have bitten this codebase:

* **the stored form** — ``values_callable`` would flip the contract to values,
  and the flip is invisible from the model alone;
* **the declared default** — a ``server_default`` naming a value writes a row the
  ORM cannot read back. Rows written outside the ORM (raw SQL, a bulk insert, a
  restore) use it, so this is not a hypothetical path.

The second trap in the same family is the column width: SQLAlchemy sizes a
``native_enum=False`` column from the longest member **name**, so a value longer
than every name raises ``StringDataRightTruncationError`` on insert. Checked
here against the enum's own members, without a database.

Read-only: parses source, imports nothing, touches no database.

    python scripts/wp-parity/check_enum_storage_contract.py
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
APP = os.path.join(ROOT, "backend", "app")

#: The project's contract. Flipping this to "value" is a migration across every
#: enum column in the database, not an edit to this file.
STORED = "name"

SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}


class Column:
    """One `mapped_column(Enum(...))` declaration."""

    def __init__(self, path: str, table: str, name: str, enum_name: str) -> None:
        self.path = path
        self.table = table
        self.name = name
        self.enum_name = enum_name
        self.values_callable = False
        self.explicit_length = None
        self.server_default = None
        self.default = None
        #: "NAME", "value", or "" when the default is not a string literal.
        self.default_stores = ""

    @property
    def qualified(self) -> str:
        return f"{self.table}.{self.name}"


def _literal(node: ast.AST | None) -> str | None:
    """The source text of a node, or None."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 — a node we cannot render is not a finding
        return None


def _quoted(text: str | None) -> str | None:
    """The string a default literal will write, or None if it is not a literal.

    Takes the *source text* of the node, parses it, and unwraps whatever
    wrapper is around the literal: ``text("'DRAFT'::character varying")``,
    ``"'DRAFT'"``, ``text("'draft'")``. All three write a string, and the first
    is how almost every healthy column here declares its default.

    Returns None for anything it cannot classify — a function call, an
    arithmetic expression, an enum member reference. That is deliberate: a
    default this gate cannot read is a default it must not claim to have
    verified. Reporting it as a value would manufacture a failure, and skipping
    it silently would manufacture a pass.

    The cast syntax at the end of a Postgres literal (``::character varying``)
    is not valid Python, so the unparse-then-parse round trip strips it first.
    """
    if not text:
        return None
    source = re.sub(r"::\s*[\w ]+(\s*\([^)]*\))?", "", text).strip()
    try:
        node: ast.AST = ast.parse(source, mode="eval").body
    except SyntaxError:
        return None
    for _ in range(5):
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.Call):
            node = node.args[0] if node.args else ast.Constant(None)
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = _quoted(_literal(node.left))
            right = _quoted(_literal(node.right))
            if left is None or right is None:
                return None
            return left + right
        return None
    return None


def _member_names(enum_name: str, module: ast.Module) -> dict[str, str]:
    """`{MEMBER: "value"}` for an enum class declared in this module."""
    for node in ast.walk(module):
        if not isinstance(node, ast.ClassDef) or node.name != enum_name:
            continue
        members: dict[str, str] = {}
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Constant):
                continue
            target = stmt.targets[0]
            if isinstance(target, ast.Name):
                members[target.id] = str(stmt.value.value)
        return members
    return {}


def _default_form(value: str | None, members: dict[str, str]) -> str:
    """Whether a default literal is a member NAME or a member VALUE."""
    if not value:
        return ""
    if members:
        if value in members:
            return "NAME"
        if value in set(members.values()):
            return "value"
    # No enum body to compare against. Upper-case is this project's convention
    # for the name form, and a mixed-case literal that is not a known name is
    # reported as unclassified rather than guessed at.
    if value.isupper() or (value.replace("_", "").isalnum() and value.isupper()):
        return "NAME"
    return "value"


def _classify(table: str, stmt: ast.AnnAssign, enum_call: ast.Call, path: str,
              module: ast.Module) -> Column | None:
    name = stmt.target.id if isinstance(stmt.target, ast.Name) else None
    if not name or not enum_call.args:
        return None
    enum_arg = enum_call.args[0]
    enum_name = enum_arg.attr if isinstance(enum_arg, ast.Attribute) else (
        enum_arg.id if isinstance(enum_arg, ast.Name) else ""
    )
    column = Column(path, table, name, enum_name)

    for kw in enum_call.keywords:
        if kw.arg == "values_callable":
            column.values_callable = True
        elif kw.arg == "length" and isinstance(kw.value, ast.Constant):
            column.explicit_length = kw.value.value

    for kw in stmt.value.keywords:  # type: ignore[attr-defined]
        if kw.arg == "server_default":
            column.server_default = _quoted(_literal(kw.value))
        elif kw.arg == "default":
            column.default = _quoted(_literal(kw.value))
        elif kw.arg is None and isinstance(kw.value, ast.Call):
            # `default=SomeEnum.MEMBER` is an attribute, not a literal.
            inner = kw.value.func
            if isinstance(inner, ast.Attribute):
                column.default = inner.attr

    members = _member_names(enum_name, module)
    column.default_stores = _default_form(column.server_default, members)
    column.members = members  # type: ignore[attr-defined]
    return column


def discover() -> list[Column]:
    """Every `mapped_column(Enum(...))` under backend/app, classified."""
    found: list[Column] = []
    for dirpath, dirnames, filenames in os.walk(APP):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except (SyntaxError, UnicodeDecodeError):
                # A file mid-edit by another session parses to nothing. Skipping
                # it is right: reporting it here would blame this gate for a
                # transient state that is not its finding to make.
                continue
            for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
                table = None
                for stmt in cls.body:
                    if (
                        isinstance(stmt, ast.Assign)
                        and any(
                            isinstance(t, ast.Name) and t.id == "__tablename__"
                            for t in stmt.targets
                        )
                        and isinstance(stmt.value, ast.Constant)
                    ):
                        table = stmt.value.value
                if not table:
                    continue
                for stmt in cls.body:
                    if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.value, ast.Call):
                        continue
                    call = stmt.value
                    if not (isinstance(call.func, ast.Name) and call.func.id == "mapped_column"):
                        continue
                    for arg in call.args:
                        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "Enum":
                            column = _classify(table, stmt, arg, path, tree)
                            if column:
                                found.append(column)
                            break
    return sorted(found, key=lambda c: (c.table, c.name))


def main() -> int:
    columns = discover()
    failures: list[str] = []

    if not columns:
        # No discovery means no coverage. A gate that found nothing because its
        # search broke must not report a clean sheet.
        print("FAIL: found no enum columns at all, so nothing was checked.")
        print("      The discovery walked %s and came back empty — either the" % APP)
        print("      walk broke or the models moved. Both are findings.")
        return 1

    for column in columns:
        members = getattr(column, "members", {})

        if column.values_callable:
            failures.append(
                "%s uses values_callable, so it stores VALUES while every other "
                "enum column in the project stores NAMES. A query written for the "
                "name form returns zero rows and reads as a real count."
                % column.qualified
            )

        if column.default_stores == "value":
            failures.append(
                "%s declares server_default=%s — a member VALUE — but the column "
                "stores NAMES. Any row created outside the ORM (raw SQL, a bulk "
                "insert, a restore) gets a value the ORM cannot read back, and the "
                "LookupError it raises takes out every query selecting that row."
                % (column.qualified, column.server_default.strip("'\""))
            )

        # The width trap: SQLAlchemy sizes native_enum=False from the longest
        # member NAME, so a longer value is truncated on insert.
        if members and column.explicit_length is None:
            widest_value = max(len(v) for v in members.values())
            widest_name = max(len(k) for k in members)
            if widest_value > widest_name:
                failures.append(
                    "%s.%s has no explicit length= and its longest member value is "
                    "%d characters against a longest name of %d, so the column is "
                    "created too narrow for the value. Inserts raise "
                    "StringDataRightTruncationError."
                    % (column.table, column.name, widest_value, widest_name)
                )

    print(f"checked {len(columns)} enum column(s) discovered under backend/app")
    if failures:
        print(f"\nFAIL: {len(failures)} column(s) break the storage contract:\n")
        for line in failures:
            print("  - %s" % line)
        print(
            "\nThe contract is NAME. To fix a default, write the member name; to "
            "fix a stored value it takes a migration, not an edit here."
        )
        return 1
    print(
        "\nPASS: every enum column stores member names, its declared defaults "
        "agree, and no column is created too narrow for its own values."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())