"""A guard on the test suite's own discovery.

``testpaths`` pointed at a ``tests`` directory that does not exist, so pytest
fell back to its rootdir collection and found the suite by accident. The day
anyone created ``backend/tests/`` the whole suite would have stopped running
and a green build would have meant nothing was executed — the failure mode this
project keeps finding, aimed at the tests themselves.
"""

from __future__ import annotations

import os
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def test_testpaths_points_at_a_directory_that_exists():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        config = tomllib.load(fh)
    paths = (config.get("tool", {}).get("pytest", {}).get("ini_options", {})
             .get("testpaths") or [])
    assert paths, "testpaths is empty, so discovery depends on the working directory"
    for rel in paths:
        assert os.path.isdir(os.path.join(ROOT, rel)), (
            f"testpaths lists {rel!r}, which does not exist; pytest will fall "
            f"back to rootdir collection and may collect nothing at all"
        )


def test_the_test_files_are_where_testpaths_says():
    from app.tests.unit import test_celery_task_registration  # noqa: F401

    unit_dir = os.path.join(ROOT, "app", "tests", "unit")
    files = [f for f in os.listdir(unit_dir) if f.startswith("test_")]
    assert len(files) >= 10, (
        f"only {len(files)} test files found under app/tests/unit — if this "
        f"count dropped, the suite is not being discovered"
    )
