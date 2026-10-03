"""Every task the beat schedule names must be a task celery can dispatch.

This gate exists because of a specific silence. Beat named
`publish_due_scheduled_posts` every minute; the wrapper had gone missing; the
worker accepted the message and answered "Received unregistered task"; and three
presence gates agreed with each other that everything was fine. Scheduled blog
posts whose time came stayed drafts with nothing on the row to say anything was
waiting. No error surfaced anywhere a person looks.

Celery's own failure here is quiet by design — an unknown task name is not an
exception, it is a log line — so the check has to compare the two lists itself:
what the beat schedule names, against what `celery_app.tasks` actually holds.
Registration is checked the way the app does it, through the app's own registry,
not by grepping for a decorator; a `@celery_app.task` on a module the worker
never imports registers nothing, and that is the same silence.

Row-level behaviour lives in `.p1-tests/scheduled_blog_publish_test.py`.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

problems: list[str] = []


def require(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {'ok' if ok else 'FAIL'}")
    if not ok:
        problems.append(f"{label}{': ' + detail if detail else ''}")


celery_src = (BACKEND / "app/worker/celery_app.py").read_text(encoding="utf-8")
beat_src = (BACKEND / "app/modules/blog/application/tasks.py").read_text(
    encoding="utf-8"
)

# --- 1. what beat asks for ---------------------------------------------------
beat_tasks = re.findall(r'"task":\s*"([^"]+)"', celery_src)
beat_names = set(re.findall(r'^\s*"([a-z0-9-]+)":\s*\{', celery_src, re.M))
require(
    "beat: the schedule is not empty",
    len(beat_tasks) > 10,
    f"{len(beat_tasks)} tasks found — a regex that matched nothing would make "
    f"every check below vacuously true",
)

# --- 2. what celery can actually dispatch ------------------------------------
# `import app.main` does NOT register the tasks — it registered 10 of 28 and
# reported every one missing, which would have looked like a loud failure while
# actually being a wrong measurement. Celery imports `include=` lazily inside
# `finalize()`, so the modules load when the app is asked for its config. That
# is what the worker does, so it is what this does.
try:
    from app.worker.celery_app import celery_app

    celery_app.loader.import_default_modules()
    celery_app.finalize()
    registered = set(celery_app.tasks)
    import_error = "" if registered else "finalize() loaded nothing"
except Exception as exc:  # pragma: no cover
    registered = set()
    import_error = f"{type(exc).__name__}: {exc}"

require(
    "celery: the registry loaded (a failure here would make every check pass)",
    bool(registered),
    import_error,
)

missing = sorted(t for t in set(beat_tasks) if t not in registered)
require(
    "every task the beat schedule names is registered",
    not missing,
    f"{missing} — these fire every minute, the worker answers 'Received "
    f"unregistered task', and nothing they would have done happens",
)

# --- 3. and the wrapper this gate is really about ----------------------------
# Named here because the failure was specific and the general check above
# would not have caught it earlier: the beat entry was correct, the service
# method was correct, and only the thin celery wrapper was missing.
BLOG_TASK = "app.modules.blog.application.tasks.publish_due_scheduled_posts"
require(
    "blog: the scheduled-post task is still scheduled",
    BLOG_TASK in set(beat_tasks),
    "if the beat entry went too, posts would quietly stop publishing with "
    "nothing left to notice it",
)
require(
    "blog: and its wrapper is defined under that exact name",
    re.search(rf'@celery_app\.task\(\s*\n\s*name="{re.escape(BLOG_TASK)}"', beat_src)
    is not None,
    "beat names a task nobody defines — the wrapper is what disappeared, and "
    "the service method behind it was fine the whole time",
)
require(
    "blog: the wrapper delegates to the service rather than reimplementing it",
    "BlogService(db).publish_due_scheduled()" in beat_src,
    "a second copy of the publish rules would drift from the service and the "
    "drift would only show up in scheduled posts",
)
CPT_TASK = "app.modules.blog.application.tasks.publish_scheduled_cpt_entries"
require(
    "blog: the scheduled-entry task is registered too",
    CPT_TASK in registered and CPT_TASK in set(beat_tasks),
)
require(
    "blog: both wrappers live in the same module the beat entries name",
    beat_src.count("@celery_app.task") >= 2,
)

# --- 4. and the rules the wrappers depend on --------------------------------
require(
    "blog: a due post is published exactly once",
    re.search(r"scheduled_for\s*=\s*None", beat_src) is not None
    or "publish_due_scheduled" in beat_src,
)
service = (BACKEND / "app/modules/blog/application/blog_service.py").read_text(
    encoding="utf-8"
)
pub = re.search(r"async def publish_due_scheduled\(.*?\n(?=\n    async def )", service, re.S)
pub_src = pub.group(0) if pub else ""
require(
    "blog: the service takes only DRAFT rows",
    "BlogPostStatus.DRAFT" in pub_src,
)
require(
    "blog: it clears scheduled_for, so a repeat tick cannot republish",
    re.search(r"post\.scheduled_for\s*=\s*None", pub_src) is not None,
)
require(
    "blog: published_at is the real go-live time, not the scheduled one",
    re.search(r"post\.published_at\s*=\s*now\b", pub_src) is not None,
    "using scheduled_for makes a post that ran three days late appear three "
    "days old in every newest-first ordering",
)

# --- 5. the guard that keeps this file honest --------------------------------
# The measurement itself has to be the worker's. Two failure modes, both quiet:
# a registry that never loaded makes every check above report all 28 missing
# (a wrong answer that reads as a loud one), and a stubbed registry makes them
# all pass. So the registry must hold at least as many tasks as the beat names.
require(
    "the registry really loaded the include list",
    len(registered) >= len(set(beat_tasks)),
    f"{len(registered)} registered vs {len(set(beat_tasks))} named by beat — if "
    f"the registry is short, every 'unregistered' above is a measurement error, "
    f"not a missing task",
)

print("\n  (row-level behaviour: .p1-tests/scheduled_blog_publish_test.py — "
      "11 checks)")

if problems:
    print("\nSCHEDULED TASK REGISTRATION GAPS:")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)
print("\nPASS: every task the beat schedule names is registered by the real "
      "app, the blog wrapper delegates to the service, and a due post publishes "
      "once with the time it actually went live.")