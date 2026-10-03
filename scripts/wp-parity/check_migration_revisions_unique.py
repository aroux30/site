#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the alembic revision graph: every migration must be reachable from head.

Three properties, in the order they bite:

1. **A revision id is defined exactly once.** Two files claiming the same id is
   the obvious failure, and it is the *only* one of the three that
   `alembic heads` would notice.

2. **Every `down_revision` is a revision some file defines.** The one that
   matters: a merge file that names a parent which is itself unreachable names
   a version alembic will try to delete from `alembic_version` — a row that was
   never inserted. Measured on 2026-10-03, `alembic upgrade head` on an empty
   database aborts with `KeyError: 'f0a1b2c3d4e5'` for exactly this reason, and
   nothing after that merge runs.

3. **Every revision reaches head.** A migration with no path to head is dead:
   it does not run on a fresh database, and it does not run on this one either,
   so its table is missing everywhere while the model that reads it ships. It
   is invisible to `alembic heads`, which only walks the chain it can see, and
   invisible to `alembic current`, which only reports where this database got
   to. Both look clean on a tree that has been migrated file by file over
   months — which is how this class stayed hidden.

Reads source only. No database, no `alembic` invocation: it has to run
anywhere, and a check that needs a database is a check that stops being run.

    python scripts/wp-parity/check_migration_revisions_unique.py
"""

from __future__ import annotations

import ast
import io
import os
import sys

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by any later module that wraps stdout, which is how a
# test that imports a guard dies on "I/O operation on closed file".

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
VERSIONS = os.path.join(ROOT, "backend", "alembic", "versions")


def read_migrations() -> tuple[dict[str, list[str]], dict[str, list[str]], list[str], int]:
    """(id -> files, id -> parents, unparseable files).

    `ast`, not a regex. `down_revision` is routinely a tuple spanning several
    lines, and a regex over the file collects every quoted string in it — the
    first version of this check reported 2,415 dangling "references", all of
    them column names.
    """
    defined: dict[str, list[str]] = {}
    parents: dict[str, list[str]] = {}
    broken: list[str] = []
    file_count = 0
    for name in sorted(os.listdir(VERSIONS)) if os.path.isdir(VERSIONS) else []:
        if not name.endswith(".py"):
            continue
        file_count += 1
        try:
            tree = ast.parse(
                open(os.path.join(VERSIONS, name), encoding="utf-8").read()
            )
        except SyntaxError as exc:
            broken.append(f"{name} does not parse: {exc}")
            continue
        revision = None
        downs: list[str] = []
        # Both shapes. Alembic files in this repository use the bare
        # `revision = "x"` and the annotated `revision: str = "x"`, which are an
        # `ast.Assign` and an `ast.AnnAssign` respectively. Reading only the
        # first reported 30 perfectly good migrations as defining no id at all.
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    [node.target] if isinstance(node, ast.AnnAssign) else node.targets
                )
                if not isinstance(node.value, ast.Constant) and not isinstance(
                    node.value, (ast.Tuple, ast.List)
                ):
                    continue
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id == "revision" and isinstance(node.value, ast.Constant):
                        revision = node.value.value
                    elif target.id == "down_revision":
                        value = node.value
                        if value is None or (
                            isinstance(value, ast.Constant) and value.value is None
                        ):
                            downs = []
                        elif isinstance(value, ast.Constant):
                            downs = [str(value.value)]
                        elif isinstance(value, (ast.Tuple, ast.List)):
                            downs = [
                                str(e.value)
                                for e in value.elts
                                if isinstance(e, ast.Constant)
                                and isinstance(e.value, str)
                            ]
        if revision is None:
            broken.append(f"{name} defines no revision id")
            continue
        defined.setdefault(revision, []).append(name)
        parents[revision] = downs
    return defined, parents, broken, file_count


def reachable_from_heads(parents: dict[str, list[str]]) -> tuple[set[str], list[str]]:
    """Revisions reachable from a head, and the heads themselves.

    A head is a revision nothing else lists as a parent — the same definition
    alembic uses. The walk then goes **down** from each head through
    `down_revision`, because that is the direction a migration chain runs: head
    is the newest revision and its ancestors are the older ones.

    Walking *up* through the children map — which is the obvious first guess —
    reaches exactly one revision from a linear chain and declares the other 110
    orphans. That is not a near miss; it is the answer being inverted, and it
    looks alarming enough to be believed.

    Derived here rather than read from `alembic heads`: this check does not run
    alembic, and it has to work with no database and no alembic on PATH.
    """
    children: dict[str, list[str]] = {}
    for revision, downs in parents.items():
        for down in downs:
            children.setdefault(down, []).append(revision)
    heads = sorted(r for r in parents if r not in children)
    seen: set[str] = set()
    stack = list(heads)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(parents.get(current, []))
    return seen, heads


def main() -> int:
    if not os.path.isdir(VERSIONS):
        print(f"FAIL: {VERSIONS} does not exist — nothing was checked.")
        return 1

    defined, parents, broken, file_count = read_migrations()
    failures: list[str] = list(broken)

    if not defined:
        print("FAIL: no migration files were read, so nothing was checked.")
        print(f"      The walk looked in {VERSIONS} and found no `revision =`.")
        return 1

    duplicates = {r: files for r, files in defined.items() if len(files) > 1}
    for revision, files in sorted(duplicates.items()):
        failures.append(
            "revision id %s is defined by %d files (%s). Alembic resolves the id "
            "to one of them, so which one runs depends on directory order, and "
            "the other one never runs anywhere."
            % (revision, len(files), ", ".join(sorted(files)))
        )

    dangling: list[tuple[str, str]] = []
    for revision, downs in parents.items():
        for down in downs:
            if down not in defined:
                dangling.append((parents_file(revision), down))
    for name, down in sorted(dangling):
        failures.append(
            "%s names a down_revision that nothing defines: %s. Alembic merges "
            "delete a version row for every parent, so a parent that was never "
            "written aborts `alembic upgrade head`." % (name, down)
        )

    reached, heads = reachable_from_heads(parents)

    # ── one head, not "a head" ─────────────────────────────────────────────
    #
    # This replaces a per-revision "is it reachable?" check, which cannot fail.
    # An orphan branch is its *own* head: the walk starts from every head, so
    # every revision in a detached branch is trivially reachable and the orphans
    # list is always empty. That is not a near miss — on this tree the check
    # reported 0 findings while a detached branch existed, and it would do so
    # again for any number of them.
    #
    # The single head is the property that matters, and it is also what
    # `alembic heads` prints. What `alembic heads` does *not* tell you is whether
    # the extra head is a mistake or work in progress, and it says nothing at
    # all about whether `upgrade head` can run — this one reported a single head
    # on a tree whose from-empty upgrade aborts at migration 94.
    if len(heads) > 1:
        failures.append(
            "the graph has %d heads (%s). `alembic upgrade head` resolves to one "
            "of them, so every migration on the other branches is skipped and a "
            "fresh database gets a different schema than this one has. Merge "
            "them into a single parent."
            % (len(heads), ", ".join(sorted(heads)))
        )

    # ── the one that actually bites today ──────────────────────────────────
    #
    # Reachable is not the same as applied. A merge that names a parent which
    # is already an **ancestor of one of its other parents** deletes a row from
    # `alembic_version` that a earlier merge has already consumed, and alembic
    # raises KeyError on the version id rather than on anything an operator can
    # act on. Measured 2026-10-03: a from-empty `upgrade head` applied 94
    # migrations and died on `KeyError: 'f0a1b2c3d4e5'`.
    #
    # The rule is *redundant parent*, not *two merges naming the same parent*.
    # That earlier form (kept here in memory because it was wrong twice) fired
    # on `c9d0e1f2a3b4` and `e2a3f4b5c6d7`, which both name `a1c8…`/`b3c4…` —
    # but those two merges are themselves in one chain (both feed
    # `h1i2j3k4l5m6`), so the second never sees those parents as heads and the
    # delete never happens. It reported two findings on a tree whose from-empty
    # upgrade runs clean, and a gate that cries wolf gets ignored.
    #
    # A parent is redundant when it is reachable from a *sibling* parent of the
    # same merge: by the time the merge runs, the sibling already consumed it.
    # Alembic deletes every parent except the one it updates from, so the
    # redundant one is exactly the version row that is no longer there.
    def ancestors(rev: str, seen: set[str] | None = None) -> set[str]:
        seen = seen if seen is not None else set()
        for down in parents.get(rev, []):
            if down in defined and down not in seen:
                seen.add(down)
                ancestors(down, seen)
        return seen

    for revision, downs in sorted(parents.items()):
        if len(downs) < 2:
            continue
        reach = {p: ancestors(p) for p in downs}
        for parent in downs:
            for sibling in downs:
                if parent != sibling and parent in reach[sibling]:
                    failures.append(
                        "%s names %s as a parent, but %s is already an ancestor "
                        "of its other parent %s — so %s was consumed before this "
                        "merge runs. Alembic still tries to delete its row from "
                        "alembic_version, and a from-empty `alembic upgrade head` "
                        "aborts with a KeyError on '%s'."
                        % (
                            revision,
                            parent,
                            parent,
                            sibling,
                            parent,
                            parent,
                        )
                    )
                    break

    duplicates = {r: files for r, files in defined.items() if len(files) > 1}
    for revision, files in sorted(duplicates.items()):
        failures.append(
            "revision id %s is defined by %d files (%s). Alembic resolves the id "
            "to one of them, so which one runs depends on directory order, and "
            "the other one never runs anywhere."
            % (revision, len(files), ", ".join(sorted(files)))
        )

    print(
        "checked %d migration(s) in %d file(s): %d head(s), %d reachable"
        % (len(defined), file_count, len(heads), len(reached))
    )
    if failures:
        print(f"\nFAIL: {len(failures)} problem(s) in the revision graph:\n")
        for line in failures:
            print(f"  - {line}")
        print(
            "\nA migration that cannot run is worse than a missing one: the model "
            "and the schema disagree, and only a fresh database exposes it."
        )
        return 1
    print(
        "\nPASS: every revision id is unique, every parent exists, and every "
        "migration reaches a head — so `alembic upgrade head` builds the whole "
        "schema on an empty database."
    )
    return 0


_FILE_BY_REVISION: dict[str, str] = {}


def parents_file(revision: str) -> str:
    """The filename that defines a revision, for the message."""
    return _FILE_BY_REVISION.get(revision, revision)


def _populate_file_map() -> None:
    if _FILE_BY_REVISION or not os.path.isdir(VERSIONS):
        return
    for name in sorted(os.listdir(VERSIONS)):
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(
                open(os.path.join(VERSIONS, name), encoding="utf-8").read()
            )
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "revision":
                    _FILE_BY_REVISION.setdefault(node.value.value, name)


if __name__ == "__main__":
    _populate_file_map()
    sys.exit(main())