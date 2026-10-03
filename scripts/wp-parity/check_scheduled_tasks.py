"""Guard: every task on the beat schedule is registered and importable.

The project's own note in celery_app.py records the trap this guards against:
a module missing from autodiscover means the worker registers none of its
tasks, and every beat entry for it fails at fire time with "Received
unregistered task" — a job that has never run and never will, while the
schedule reads like it is working.

The first version of this guard checked one hand-listed task, so 23 others
could break silently. It now reads the schedule itself and checks all of them,
which also means a task added tomorrow is covered without editing this file.

`MUST_EXIST` is kept for the narrower question "did the media trash purge
survive an edit", which a self-referential check cannot ask: a schedule that
lost its entry would otherwise look perfectly consistent.

    python scripts/wp-parity/check_scheduled_tasks.py
"""

from __future__ import annotations

import ast
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.worker.celery_app import celery_app  # noqa: E402

# Tasks that must be on the schedule, independent of what the schedule says.
MUST_EXIST = {
    "app.modules.media.application.tasks.purge_expired_media_trash": (
        "the media trash never empties on its own, so deleted files keep their "
        "bytes forever"
    ),
    "app.modules.settings.application.tasks.purge_expired_privacy_results": (
        "a GDPR export that is requested and never collected keeps a full copy of "
        "the subject's personal data in the table forever, under a retention "
        "window that nothing enforces"
    ),
    "app.modules.settings.application.tasks.mask_expired_comment_ips": (
        "comment IPs are personal data, and without a schedule nothing shortens "
        "them -- the erasure path only covers the one subject who asked"
    ),
}


def _autodiscover_packages_from_source() -> set[str]:
    """The packages celery_app.py passes to `autodiscover`.

    Read from the source because Celery only evaluates that lambda inside
    ``finalize()`` and exposes no accessor before then — so asking the app
    would silently return nothing, which is what an earlier version of this
    guard did and then treated as "nothing to check".
    """
    path = os.path.join(ROOT, "backend", "app", "worker", "celery_app.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in ("autodiscover", "autodiscover_tasks")
        ):
            continue
        for kw in node.keywords:
            if kw.arg != "packages":
                continue
            # Collect every entry, not the first: an earlier version returned
            # on the first string constant, so it saw one package out of forty
            # and reported every other module as undiscovered.
            for elt in getattr(kw.value, "elts", []):
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    found.add(elt.value)
    return found


def _listed_package(module_path: str, discovered: set[str]) -> str | None:
    """The autodiscover entry that covers this task module, if any.

    Walks the module path from longest to shortest, so
    `app.modules.search.application.tasks` resolves against the listed
    `app.modules.search` rather than being compared verbatim and failing.
    """
    # An exact entry wins: `include` holds full task-module paths, so
    # `app.modules.media.application.tasks` is listed verbatim.
    if module_path in discovered:
        return module_path
    parts = module_path.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in discovered:
            return candidate
    return None


def main() -> int:
    failures: list[str] = []

    # Autodiscover is configured inside `finalize()`, and celery_app's include
    # list reads empty until then — so neither `conf.include` nor
    # `conf.autodiscover_tasks` can be tested here. Instead each task module is
    # imported directly, which is exactly what autodiscover does at worker
    # start: the decorator registers the task as a side effect of the import.
    schedule = celery_app.conf.beat_schedule or {}
    scheduled = {
        entry["task"]
        for entry in schedule.values()
        if isinstance(entry, dict) and entry.get("task")
    }
    if not scheduled:
        print("FAIL: the beat schedule is empty, so no periodic job runs at all.")
        return 1

    # A task defined in the worker's own module is imported by definition: the
    # worker loads that file to exist. `record_heartbeat` lives there, so asking
    # autodiscover to cover it is a question with no answer by construction.
    SELF_HOSTED = ("app.worker.celery_app",)

    modules = sorted({name.rsplit(".", 1)[0] for name in scheduled})

    # 1a. The module backing each task must be in autodiscover's package list.
    #     Importing it here is not a substitute: the import proves the decorator
    #     runs, not that the *worker* will run it. A module dropped from
    #     autodiscover leaves this guard green — a colleague found exactly that
    #     by deleting one line and watching the check pass — while the worker
    #     registers nothing from it and the job never fires.
    #
    #     The list is read from celery_app.py's own source rather than from a
    #     Celery API: `autodiscover_packages` is a lambda evaluated inside
    #     `finalize()`, and there is no public accessor before that.
    discovered = _autodiscover_packages_from_source()
    if not discovered:
        failures.append(
            "could not read autodiscover's package list out of celery_app.py, so "
            "this guard cannot tell whether the worker's discovery is complete"
        )
    else:
        for module_path in modules:
            if module_path.startswith(SELF_HOSTED):
                continue
            # A task module looks like `app.modules.search.application.tasks`;
            # the autodiscover list holds `app.modules.search`. Walking up to
            # the longest listed prefix compares the right thing — an earlier
            # version compared the full task module against the package and
            # reported 20 false failures on a schedule where nothing was wrong.
            package = _listed_package(module_path, discovered)
            if package is None:
                failures.append(
                    "%s is scheduled but no autodiscover package covers it, so the "
                    "worker never imports it and every task in it never runs"
                    % module_path
                )

    for module_path in modules:
        try:
            importlib.import_module(module_path)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                "could not import %s, so its tasks cannot be registered: %s"
                % (module_path, exc)
            )

    registered = set(celery_app.tasks.keys())
    for name in sorted(scheduled):
        if name not in registered:
            failures.append(
                "%s is scheduled but not registered on the worker — a beat entry "
                "for an unregistered task fails at fire time and nobody notices"
                % name
            )

    for name, consequence in MUST_EXIST.items():
        if name not in scheduled:
            failures.append("%s has no beat entry: %s" % (name, consequence))

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d scheduled task(s) are not wired up." % len(failures))
        return 1

    print(
        "PASS: all %d scheduled task(s) are registered, and the %d that must exist do."
        % (len(scheduled), len(MUST_EXIST))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())