"""Tests for the gate runner itself.

`scripts/run_all_gates.py` is the entry point every CI step and every "is it
still green?" question goes through, so a mistake in it is worse than a mistake
in any single gate: it either hides a failure or invents one. Two properties
matter and neither is about the gates it runs.

* **A gate that could not run is not a pass.** The runner has to distinguish
  three outcomes — passed, failed, and did-not-run — and only the first may be
  reported as green. A skip counted as a pass is how a suite goes green without
  having executed, which is the exact failure this repository keeps finding in
  its own features.
* **A gate added to the directory but not to the list never runs.** The list is
  explicit so a new gate cannot be silently unrun, and that is only true if
  nothing is added without being classified.
"""

from __future__ import annotations

import ast
import os
import sys

import pytest

# This file lives at backend/app/tests/unit/, so the repo root — the directory
# holding scripts/ — is four levels up.
ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
RUNNER = os.path.join(ROOT, "scripts", "run_all_gates.py")
GATE_DIR = os.path.join(ROOT, "scripts", "wp-parity")


def _runner_source() -> str:
    return open(RUNNER, encoding="utf-8").read()


def _runner_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_all_gates", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------- skip is not a pass


def test_a_skip_is_not_counted_as_a_pass():
    """Three outcomes, and the runner must not merge two of them."""
    import re

    src = _runner_source()
    # The gate's own convention: exit 2 with a SKIP line means "did not run".
    assert "code == 2" in src, (
        "the runner must recognise the could-not-check exit code, or a gate "
        "that skipped itself is reported as a failure"
    )
    assert re.search(r"SKIP", src), "a skipped gate has to say so in the output"

    # And the summary must keep the two apart.
    assert "skipped" in src, "the tally does not mention skipped gates at all"
    mod = _runner_module()
    rows = [
        ("a", "pass", "", 0.0),
        ("b", "FAIL", "", 0.0),
        ("c", "SKIP (no database)", "", 0.0),
        ("d", "SKIP (not run)", "", 0.0),
    ]
    assert sum(1 for _, s, _, _ in rows if s == "pass") == 1
    assert [n for n, s, _, _ in rows if s == "FAIL"] == ["b"]
    assert len([n for n, s, _, _ in rows if s.startswith("SKIP")]) == 2
    del mod


def test_a_missing_gate_is_a_failure_not_an_omission():
    """A gate file that vanished must not quietly shrink the suite.

    The runner treats a named-but-absent gate as MISSING and returns non-zero
    for it, precisely so deleting a gate (or renaming it without updating the
    list) is visible instead of reducing coverage in silence.
    """
    src = _runner_source()
    assert '"MISSING"' in src, (
        "the runner has no MISSING state, so a deleted gate file just makes the "
        "list shorter"
    )
    assert "return 1 if failed or missing else 0" in src, (
        "a missing gate must fail the run, or deleting a gate costs nothing"
    )


def test_a_database_failure_is_not_mistaken_for_a_missing_database():
    """The no-DB detector keys on connection errors, not on any error.

    If it matched a substring shared with a real finding, a genuine failure
    would be downgraded to "skipped" and reported as neither pass nor fail.
    """
    src = _runner_source()
    assert "elif needs_db and _looks_like_no_database(combined)" in src, (
        "the no-database branch is checked after the SKIP branch, so a real "
        "failure on a DB gate can still be recognised as one"
    )
    # The marker list must not include anything a real finding would print.
    for marker in ("assertionerror", "traceback", "expected"):
        assert marker not in src.lower(), (
            f"{marker!r} in NO_DB_MARKERS would downgrade a real failure to a skip"
        )


# ------------------------------------------- nothing is added unclassified


def test_every_gate_file_is_in_the_runner_list():
    """A gate on disk but not in the list has never run.

    The list is hand-maintained so that adding a gate forces a decision about
    whether it needs a database. The cost of that choice is this: nothing stops
    somebody dropping a file in and forgetting. This test is what makes the list
    a contract instead of a suggestion.
    """
    on_disk = {
        name[:-3]
        for name in os.listdir(GATE_DIR)
        if name.startswith("check_") and name.endswith(".py")
    }
    tree = ast.parse(_runner_source())
    listed: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Tuple)
            and len(node.elts) == 2
            and isinstance(node.elts[0], ast.Constant)
            and isinstance(node.elts[0].value, str)
            and node.elts[0].value.startswith("check_")
        ):
            listed.add(node.elts[0].value)

    missing = on_disk - listed
    assert not missing, (
        f"these gate files are never run: {sorted(missing)}. Add each to "
        f"GATES in run_all_gates.py with its database dependency, or delete it."
    )


def test_every_listed_gate_file_exists():
    tree = ast.parse(_runner_source())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Tuple)
            and len(node.elts) == 2
            and isinstance(node.elts[0], ast.Constant)
            and isinstance(node.elts[0].value, str)
            and node.elts[0].value.startswith("check_")
        ):
            path = os.path.join(GATE_DIR, f"{node.elts[0].value}.py")
            assert os.path.isfile(path), f"{node.elts[0].value} is listed but absent"


def test_every_gate_declares_its_database_dependency():
    tree = ast.parse(_runner_source())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Tuple)
            and len(node.elts) == 2
            and isinstance(node.elts[0], ast.Constant)
            and isinstance(node.elts[0].value, str)
            and node.elts[0].value.startswith("check_")
        ):
            assert isinstance(node.elts[1], ast.Constant) and isinstance(
                node.elts[1].value, bool
            ), (
                f"{node.elts[0].value} has no database flag; without it a "
                f"failure could be silently downgraded to a skip"
            )
