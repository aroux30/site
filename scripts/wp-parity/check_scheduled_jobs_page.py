"""The scheduled-jobs screen: list, a real run, and a refusal that explains.

WordPress's Tools → Cron Events. The feature is checked end to end because the
failure modes are all "looks done": a list that renders but cannot run, a run
button that 404s, a "dispatched" answer for a task that is not registered (so
the worker rejects it and the operator trusts a lie).

    python scripts/wp-parity/check_scheduled_jobs_page.py
"""

from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

SERVICE = os.path.join(ROOT, "backend", "app", "modules", "automation",
                       "application", "scheduler_service.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "automation", "api", "routes.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "automation.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "scheduled-jobs", "page.tsx")
NAV = os.path.join(ROOT, "frontend", "app", "admin", "layout.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    # Static wiring.
    routes = open(ROUTES, encoding="utf-8").read() if os.path.isfile(ROUTES) else ""
    check("the list route exists", "/admin/scheduled-jobs" in routes)
    check("the run route exists", "/scheduled-jobs/{name}/run" in routes)
    client = open(CLIENT, encoding="utf-8").read() if os.path.isfile(CLIENT) else ""
    check("the client has both methods",
          "scheduledJobsApi" in client and "/scheduled-jobs" in client)
    page = open(PAGE, encoding="utf-8").read() if os.path.isfile(PAGE) else ""
    check("the page exists and calls the client",
          "scheduledJobsApi" in page and "scheduledJobsApi.run" in page,
          "no page, or a page that never runs a job")
    nav = open(NAV, encoding="utf-8").read() if os.path.isfile(NAV) else ""
    check("the page is linked from the sidebar", "/admin/scheduled-jobs" in nav,
          "an admin route with no sidebar link is unreachable")

    # Behaviour: the service lists real jobs, runs a registered one, and refuses
    # an unknown name with a reason.
    from app.modules.automation.application.scheduler_service import SchedulerService

    jobs = SchedulerService.list_jobs()
    check("the service lists the beat schedule", len(jobs) > 0, f"{len(jobs)} jobs")
    check("every listed job carries a schedule and a task",
          all(j["schedule"] and j["task"] for j in jobs),
          "a job with no schedule or task")

    # The registry must agree with the worker's: after the include-import, no
    # job should read as unregistered. (Before that fix every job did.)
    unregistered = [j["name"] for j in jobs if not j["registered"]]
    check("no job reads as unregistered after the task import",
          not unregistered, f"unregistered: {unregistered[:5]}")

    # A real dispatch of a harmless job.
    if any(j["name"] == "record-beat-heartbeat" for j in jobs):
        res = SchedulerService.run_job("record-beat-heartbeat")
        check("a registered job dispatches", res.get("dispatched") is True, str(res))

    # An unknown name is refused with a reason, not a silent success.
    res = SchedulerService.run_job("definitely-not-a-real-job")
    check("an unknown job is refused with a reason",
          res.get("dispatched") is False and bool(res.get("reason")), str(res))

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the scheduled-jobs screen lists, runs, and refuses honestly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())