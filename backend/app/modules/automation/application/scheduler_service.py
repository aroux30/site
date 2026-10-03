"""The scheduled-jobs screen: what Celery beat runs, and a manual trigger.

WordPress's "Cron Events" screen under Tools. The storefront's scheduled work
(expiring carts, purging the media trash, running health checks, sending
abandoned-cart reminders) lived only in ``celery_app.conf.beat_schedule`` and a
read-only slice of the Site Health info tab — so an operator who wanted to run
"expire stale carts" *now*, after fixing the thing that made it fail, had no
button for it, and an operator debugging a job could not see its schedule
without reading source.

Two operations, both honest about their limits:

* **list** — name, task path, and a human-readable schedule for every entry.
* **run** — dispatch one task by the beat entry's *name*. It sends by name
  through Celery, so it lands on the worker the same way the beat entry does;
  the alternative (importing the task and calling it) would run it in the web
  process, which is not where it runs in production and would not exercise the
  queue at all.
"""

from __future__ import annotations

import importlib
from typing import Any

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_tasks_imported = False


def _ensure_tasks_registered() -> None:
    """Import every task module the worker autodiscovers, once.

    Celery populates ``app.tasks`` lazily: at import time only the handful of
    tasks defined in ``celery_app`` itself are present, and the rest appear
    only when their modules are imported — which the worker does from the
    ``include`` list, but a web process does not. Without this, every job on
    the screen reads as "unregistered/stale" in the API while the worker runs
    them fine, which is a false alarm an operator would act on. Importing the
    same list the worker uses is what makes the two agree.
    """
    global _tasks_imported
    if _tasks_imported:
        return
    from app.worker.celery_app import celery_app

    for module_path in celery_app.conf.get("include", []) or []:
        try:
            importlib.import_module(module_path)
        except Exception as exc:  # noqa: BLE001 — a module that fails to import
            # leaves fewer tasks registered, not a broken screen; the job it
            # owns will simply read as unregistered, which is true.
            logger.warning("scheduler_task_module_import_failed", module=module_path, error=str(exc))
    _tasks_imported = True


def _humanise(schedule: Any) -> str:
    """A readable form of a beat schedule entry's ``schedule``.

    Celery's ``crontab`` and ``timedelta`` objects both have a serviceable
    repr, and reaching into their internals to build "every 15 minutes" would
    break on the next Celery version. The repr is honest and stable.
    """
    if schedule is None:
        return "—"
    return str(schedule)


class SchedulerService:
    """Read the beat schedule and dispatch entries on demand."""

    @staticmethod
    def list_jobs() -> list[dict[str, Any]]:
        """Every beat entry: its name, task path and schedule.

        ``registered`` says whether the task is actually in the worker's
        registry. A beat entry whose task was renamed or removed fires into
        "unregistered task" and dies silently — the exact failure this project
        has hit before — so the screen marks it rather than listing a job that
        cannot run.
        """
        _ensure_tasks_registered()
        from app.worker.celery_app import celery_app

        known = set(celery_app.tasks.keys())
        jobs: list[dict[str, Any]] = []
        for name, entry in (celery_app.conf.beat_schedule or {}).items():
            task = entry.get("task")
            jobs.append(
                {
                    "name": name,
                    "task": task,
                    "schedule": _humanise(entry.get("schedule")),
                    "queue": (entry.get("options") or {}).get("queue"),
                    "registered": task in known if task else False,
                }
            )
        return sorted(jobs, key=lambda j: j["name"])

    @staticmethod
    def run_job(name: str) -> dict[str, Any]:
        """Dispatch the beat entry called ``name`` now. Returns a small report.

        Refuses an unknown name rather than guessing, and reports whether the
        task is registered so the operator is not told "sent" for a dispatch
        that will land as an unregistered task.
        """
        _ensure_tasks_registered()
        from app.worker.celery_app import celery_app

        entry = (celery_app.conf.beat_schedule or {}).get(name)
        if entry is None:
            return {"dispatched": False, "reason": f"no scheduled job named {name!r}"}

        task = entry.get("task")
        if not task:
            return {"dispatched": False, "reason": f"{name!r} has no task"}

        if task not in celery_app.tasks:
            # Sending anyway would put a message on the queue that the worker
            # rejects as unregistered — a "success" the operator would act on.
            return {
                "dispatched": False,
                "reason": f"task {task!r} is not registered; the beat entry is stale",
            }

        options = entry.get("options") or {}
        celery_app.send_task(task, queue=options.get("queue"))
        logger.info("scheduled_job_dispatched_manually", job=name, task=task)
        return {"dispatched": True, "task": task}
