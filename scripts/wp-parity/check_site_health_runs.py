#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the Site Health run history: a run that is stored but unreadable is
as useless as a run that never happened.

The screen had a history list, and it showed the same two things for every
entry: a status badge and a timestamp. That answers "is it broken right now"
and nothing else, which is the question the live report already answers. What a
support thread actually opens with is "what broke last night?" — and to answer
it you need two facts the row had but nothing surfaced:

* **which check failed.** `error` covers a run that *raised*, which is the rare
  case. The common one is a run that completed with several checks in warning
  and the operator had to expand every entry to find out which.
* **how long it took.** A check that passes after twelve seconds and one that
  returns in milliseconds are indistinguishable in that list, so a slow disk
  reads exactly like a healthy site.

Both are derived, not stored: the duration is computed from the two timestamps
already on the row, and the failing names from the report already on the row.
So this gate does not need a migration, and it checks the whole chain — the
service that produces them, the API that serialises them, the TypeScript type
that declares them, and the page that renders them.

Read-only: reads source, imports nothing, touches no database.

    python scripts/wp-parity/check_site_health_runs.py
"""

from __future__ import annotations

import ast
import os
import re
import sys

# No `sys.stdout` rebinding here. It is tempting on a Windows console, where a
# Persian message can raise UnicodeEncodeError and abort a gate mid-report —
# but a second TextIOWrapper closes the first one's buffer, and every module
# imported after this one prints into a closed stream. `check_stdout_guards_are_
# idempotent` exists because that has bitten this suite before. The runner sets
# PYTHONIOENCODING and captures output, so nothing here needs it.

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "settings", "application", "site_health_service.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "settings", "api", "routes.py")
TYPES = os.path.join(ROOT, "frontend", "lib", "api", "wp-parity.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "system-health", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, why: str) -> None:
    if not ok:
        failures.append(f"{label}: {why}")


def read(path: str) -> str:
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""


def method_body(source: str, name: str) -> str:
    """The source of one method, and nothing after it.

    Slicing to the end of the file makes every later function count as evidence
    about the one being checked — that mistake has already been made twice in
    this repository, once in a gate that passed while the read it asserted on
    had been deleted.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = node.lineno - 1
            return "\n".join(source.splitlines()[start : node.end_lineno or start + 1])
    return ""


def main() -> int:
    service = read(SERVICE)
    routes = read(ROUTES)
    types = read(TYPES)
    page = read(PAGE)

    for label, path in (
        ("the service", SERVICE),
        ("the routes", ROUTES),
        ("the API types", TYPES),
        ("the page", PAGE),
    ):
        check(f"{label} is readable", bool(path.strip()), f"{path} is missing or empty")

    listing = method_body(service, "list_runs")
    recorder = method_body(service, "record_run")

    # ── 1. the service produces both facts ─────────────────────────────────
    check(
        "list_runs reports how long each run took",
        "duration_ms" in listing,
        "a run that took 12s and one that took 12ms are indistinguishable in "
        "the history, so a slow check that passes reads as a healthy site",
    )
    check(
        "list_runs names the checks that failed",
        "failing_checks" in listing,
        "'critical' is a badge, not an answer; the operator still has to expand "
        "every entry to learn which check is unhappy",
    )
    check(
        "the failing list is built from the stored report, not invented",
        'c.get("status")' in listing and "warning" in listing,
        "a list of failures that is not derived from the report can claim a "
        "check failed when the run says otherwise",
    )

    # ── 2. the duration is computed from the stored timestamps ─────────────
    # Not a new column: the two timestamps are already on the row, and a second
    # source of truth for "how long" would be one more thing to keep in step.
    check(
        "the duration comes from started_at and finished_at",
        "finished_at" in listing and "started_at" in listing,
        "an invented duration is worse than none — it looks like a measurement",
    )
    check(
        "the returned report carries the duration too",
        "duration_ms" in recorder,
        "the admin screen shows the run it just triggered without refetching "
        "the history, so the run in front of the operator would have no time",
    )
    # Scoped to `record_run`, not to the file. Three other methods in this
    # module stamp `datetime.now(UTC)` for their own reasons — checked_at,
    # generated_at — and counting across the file made a correct method look
    # like it took two samples. That mistake has been made twice in this
    # repository already, both times by a check that passed because it was
    # looking at the wrong span of source.
    check(
        "one timestamp feeds both the row and the report",
        recorder.count("datetime.now(UTC)") == 2,
        "record_run should sample the clock exactly twice — once for `started`, "
        "once for `finished`. A third call means the stored duration and the "
        "reported one were taken at different moments, so two numbers from one "
        "run can contradict each other.",
    )

    # ── 3. the API does not drop them ──────────────────────────────────────
    # Checked on the runs route's own body, and by *passing the list through*
    # rather than naming the fields. This route returns `{"items": items}`
    # verbatim, which is the right shape: a route that re-listed every key would
    # be a place to forget one, and a run's shape is the service's to decide.
    # So the assertion is that the service's dict reaches the response intact —
    # a route that rebuilt the dict key by key could still drop a field, and
    # that is what this catches.
    runs_route = method_body(routes, "list_site_health_runs")
    check(
        "the runs route exists",
        bool(runs_route),
        "list_site_health_runs is gone from settings/api/routes.py, so the "
        "history the page shows has no source",
    )
    check(
        "the runs route passes each run through rather than rebuilding it",
        '"items"' in runs_route and "list_runs" in runs_route,
        "a route that re-lists every key of a run is a place to forget one; "
        "the whole dict must reach the response",
    )

    # ── 4. the frontend declares and renders them ──────────────────────────
    for field in ("duration_ms", "failing_checks"):
        check(
            f"the TypeScript type declares {field}",
            field in types,
            f"the response carries {field} and no type declares it, so the page "
            f"either lies to the compiler or skips the field",
        )
    # Where, not just whether. A check that only asked "does the page mention
    # failing_checks?" passed on a page that rendered it inside the expanded
    # <details> body — which is exactly the answer the screen already gave, and
    # exactly what the change was meant to stop. The collapsed row is the
    # <summary>; the expanded one is everything after it.
    #
    # Matched with a regex, not `split("<summary>")`. The JSX is
    # `<summary className="...">`, so the literal tag never appears: the split
    # found nothing, returned the whole file, and every "is it in the summary"
    # assertion was satisfied by any mention anywhere — the exact vacuity this
    # block exists to prevent, reproduced inside the check for it.
    summary_match = re.search(r"<summary\b[^>]*>([\s\S]*?)</summary>", page)
    summary_body = summary_match.group(1) if summary_match else ""
    # No summary means the placement assertions below have nothing to assert
    # on, and a check that cannot find its subject must not report a pass on
    # it. This is how the first version of this gate passed every sabotage.
    check(
        "the history row's collapsed summary can be located",
        bool(summary_match),
        "no <summary> found in the page, so 'is it shown before expanding?' "
        "cannot be answered — the gate would be reading a subject that is not "
        "there and calling it agreement",
    )

    check(
        "the page renders the duration",
        "duration_ms" in page,
        "the fact is stored and typed and never shown, which is the same shape "
        "as the shipped-but-dead endpoint",
    )
    check(
        "the duration is in the collapsed summary too",
        "formatDuration(run.duration_ms)" in summary_body,
        "read but not formatted, or read only after expanding: either way the "
        "operator cannot see how long a run took without opening it",
    )
    check(
        "the page names the failing checks at all",
        "failing_checks" in page,
        "the service computes them and the page never reads them, which is the "
        "shipped-but-dead shape: a fact produced, typed and never shown",
    )
    check(
        "the failing checks are named in the collapsed summary",
        "failing_checks" in summary_body and "join" in summary_body,
        "the field is read in the summary but never rendered — a length "
        "counter with no names answers 'how many?' and not 'which?', which is "
        "the question this was added for",
    )
    check(
        "the failing checks are guarded before being read",
        "failing_checks.length" in page or "failing_checks?.length" in page,
        "a row without the field reads as undefined and .length on it throws "
        "the whole history away",
    )
    check(
        "the duration is formatted rather than printed raw",
        "formatDuration" in page and "run.duration_ms" in page,
        "a raw millisecond count is not something a person scans",
    )

    # ── report ──────────────────────────────────────────────────────────────
    print("checked the Site Health run history end to end")
    if failures:
        print(f"\nFAIL: {len(failures)} link(s) of the chain are missing:\n")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(
        "\nPASS: a run records what failed and how long it took, the API "
        "passes both through, and the page shows them."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
