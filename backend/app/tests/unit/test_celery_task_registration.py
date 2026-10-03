"""Tests for Celery task registration.

The worker had ``autodiscover_tasks(packages=[...], related_name=
"application.tasks")`` doing the registration, and it registered nothing:
``packages`` is a list of modules, autodiscover only looks for
``<package>.tasks``, and a top-level module has no ``tasks`` attribute. So the
worker booted with zero business tasks and every one of the 25 beat jobs fired
into "Received unregistered task" and died — no cart expired, no media purged,
no daily report, no site-health run, and nothing but a log line to show it.

Two properties are pinned here, because either one alone is what a refactor
breaks:

* every ``beat_schedule`` job names a task that is actually registered, and
* the include list is checked at import time, so a stale entry cannot take the
  rest of the list down with it again.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def app():
    from app.worker.celery_app import celery_app

    # import_default_modules is what a worker does on boot; finalize is what
    # runs on every .delay(). Without the first, `include` is never imported.
    celery_app.loader.import_default_modules()
    celery_app.finalize()
    return celery_app


# ------------------------------------------------------- the schedule resolves


def test_every_beat_job_names_a_registered_task(app):
    schedule = app.conf.beat_schedule or {}
    missing = {
        name: entry.get("task")
        for name, entry in schedule.items()
        if entry.get("task") and entry["task"] not in app.tasks
    }
    assert not missing, (
        f"{len(missing)} beat job(s) point at a task that is not registered; "
        f"they fire and die silently: {missing}"
    )


def test_the_schedule_is_not_empty(app):
    # A passing assertion over zero jobs would look like a healthy schedule.
    assert len(app.conf.beat_schedule or {}) >= 10


def test_the_heartbeat_canary_is_registered(app):
    # The scheduler-liveness canary every content check reads. If it is not
    # registered, "the beat has never fired" is the only thing any page can
    # report, forever.
    assert "app.worker.celery_app.record_heartbeat" in app.tasks


def test_the_site_health_run_is_registered(app):
    # P2 gap: the daily Site Health run. Its beat entry existed with no
    # registered task, so the one scheduled check this project added could
    # never have run.
    assert "app.modules.settings.application.tasks.run_site_health" in app.tasks


# ------------------------------------------------------- the include list


def test_every_include_entry_exists_on_disk():
    from app.worker.celery_app import TASK_MODULES

    missing = [
        m for m in TASK_MODULES if not os.path.isfile(m.replace(".", os.sep) + ".py")
    ]
    assert not missing, (
        f"{missing} are in celery include but not on disk. Celery aborts the "
        f"import at the first bad entry, so the modules after it never "
        f"register and the worker loses most of its tasks."
    )


def test_the_include_list_is_not_a_module_list():
    from app.worker.celery_app import TASK_MODULES

    # The original mistake: `packages=[...]` takes module names, and
    # autodiscover then looks for `<name>.tasks` — which does not exist for a
    # top-level module. `include` takes the full path and imports it directly.
    for name in TASK_MODULES:
        assert ".tasks" in name or name.endswith("celery_app"), (
            f"{name} looks like a module autodiscover would search, not a path "
            f"to import"
        )


def test_the_include_list_covers_every_module_that_defines_a_task():
    """No task module may be left out of the include list.

    This is the check that would have caught the original bug the first time.
    It walks the filesystem instead of trusting the list, so a new module with
    tasks and no list entry fails here rather than at three in the morning.
    """
    from app.worker.celery_app import TASK_MODULES

    # This file lives at backend/app/tests/unit/, so the package root that holds
    # "modules" is four levels up.
    root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    modules_root = os.path.join(root, "app", "modules")
    on_disk: set[str] = set()
    for pkg in sorted(os.listdir(modules_root)):
        candidate = os.path.join(modules_root, pkg, "application", "tasks.py")
        if os.path.isfile(candidate):
            on_disk.add(f"app.modules.{pkg}.application.tasks")

    declared = set(TASK_MODULES)
    unregistered = on_disk - declared
    assert not unregistered, (
        f"these modules define tasks but are not in celery include, so their "
        f"tasks never register: {sorted(unregistered)}"
    )
    stale = {m for m in declared - on_disk if "celery_app" not in m}
    assert not stale, f"include lists modules with no tasks file: {sorted(stale)}"
