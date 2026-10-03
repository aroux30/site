#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the P2 deliveries against regression.

Written after three measured regressions in one day, each caught only because
somebody happened to look:

* a Celery task vanished from a rewritten module while its ``beat_schedule``
  entry stayed, so the daily job fired into "unregistered task" forever;
* three plugin hooks were declared and shipped in the admin plugins page, and
  never dispatched;
* the email-template resolver was bypassed by its three callers, so an admin's
  saved wording was stored and no real email would ever use it.

The other gates cover P0 and P1. This one covers the P2 list specifically, and
every assertion is a *call site* check rather than a "does the helper work"
check — a helper can be correct and unreachable, which is the shape all three
of the above had.

Read-only: it imports modules and reads source. It writes nothing and touches
no database.

    python scripts/wp-parity/check_p2_deliveries.py
"""

from __future__ import annotations

import ast
import inspect
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "backend"))

failures: list[str] = []
checks = 0


def check(label: str, ok: bool, why: str = "") -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(f"{label}: {why}" if why else label)


def src_of(module: str, *path: str) -> str:
    """The source of a module attribute, e.g. ("svc", "SiteHealthService", "x")."""
    import importlib

    mod = importlib.import_module(module)
    obj: object = mod
    for part in path:
        obj = getattr(obj, part)
    return inspect.getsource(obj)


# ── 1. the declared hooks all have a dispatch site ───────────────────────────
# Owned by check_hooks_dispatched.py, which is the authority on this. Listed
# here so a P2 run fails if that gate is ever removed from the set.
check(
    "the hook-dispatch gate is present",
    os.path.isfile(os.path.join(HERE, "check_hooks_dispatched.py")),
    "without it a declared-but-dead hook is indistinguishable from a live one",
)

# ── 2. the scheduled task exists and is registered ───────────────────────────
# Both halves, and they fail differently: the task can be gone (a rewrite of
# tasks.py) while its beat entry stays, or registered under a name the schedule
# does not use.


def _beat_task_names() -> set[str]:
    """Every task name the worker will register.

    The task modules are imported first, before celery_app: they import it for
    the ``@celery_app.task`` decorator, so reaching them the other way round
    leaves them half-initialised and the tasks silently missing from the
    registry. This is the same ordering a worker uses.
    """
    import importlib

    from app.worker.celery_app import TASK_MODULES, celery_app

    for module in TASK_MODULES:
        try:
            importlib.import_module(module)
        except Exception:  # noqa: BLE001 — reported as a missing task below
            pass
    celery_app.loader.import_default_modules()
    celery_app.finalize()
    return set(celery_app.tasks)


def _beat_schedule_tasks() -> set[str]:
    from app.worker.celery_app import celery_app

    return {
        entry.get("task")
        for entry in (celery_app.conf.beat_schedule or {}).values()
        if isinstance(entry, dict) and entry.get("task")
    }


scheduled = _beat_schedule_tasks()
registered = _beat_task_names()
unregistered = scheduled - registered
check(
    "every beat job's task is registered",
    not unregistered,
    f"{sorted(unregistered)} are scheduled but not registered; they fire and die "
    f"with 'Received unregistered task'",
)

# The two the P2 work added, named explicitly: a generic check above can pass
# while a rewrite moves one of these and another module happens to cover it.
for task in (
    "app.modules.settings.application.tasks.run_site_health",
    # Same module: the GDPR purge was added alongside the health run, and a
    # rewrite of tasks.py took it first. Naming the module it actually lives in
    # is the point — a wrong module here reports a task that exists as missing.
    "app.modules.settings.application.tasks.purge_expired_privacy_results",
):
    check(f"{task.rsplit('.', 1)[-1]} is registered", task in registered, "not in the registry")
    check(f"{task.rsplit('.', 1)[-1]} is scheduled", task in scheduled, "not on the beat")


# ── 3. the email-template resolver reaches the real callers ──────────────────
try:
    worker_src = src_of("app.modules.automation.application.outbox_worker")
    rules_src = src_of("app.modules.automation.application.rules_engine")
except Exception as exc:  # noqa: BLE001
    worker_src = rules_src = ""
    check("the automation modules import", False, str(exc))

for name, src in (("outbox_worker", worker_src), ("rules_engine", rules_src)):
    code = "\n".join(l for l in src.split("\n") if not l.strip().startswith("#"))
    check(
        f"{name} resolves templates through the DB",
        "resolve_template" in src and "default_email_templates()" not in code,
        "it reads the built-in literals, so an admin's saved template never "
        "reaches a real email",
    )

check(
    "the order confirmation attaches the invoice",
    "attachments=await _invoice_attachment(" in worker_src,
    "no attachment is passed, so the customer gets a confirmation with no "
    "document even though the capability exists",
)
check(
    "the attachment helper cannot fail the outbox",
    "except Exception" in src_of(
        "app.modules.automation.application.outbox_worker", "_invoice_attachment"
    ),
    "a missing PDF would re-queue a notification the customer already saw",
)


# ── 4. the media edit chain is written, not just declared ────────────────────
try:
    derived = src_of(
        "app.modules.media.application.media_service",
        "MediaService",
        "register_derived_asset",
    )
except Exception as exc:  # noqa: BLE001
    derived = ""
    check("register_derived_asset exists", False, str(exc))

check(
    "a derived asset records its parent",
    "source_asset_id=source.id" in derived,
    "the edit chain does not exist, so neither the history nor "
    "restore-original can work",
)
check(
    "a derived asset records the operation",
    "edit_operation=suffix" in derived,
    "the history cannot read as a list of steps",
)


# ── 5. the upload ceiling is configurable, and actually consulted ─────────────
try:
    upload = src_of("app.modules.media.application.media_service", "MediaService", "upload_file")
except Exception as exc:  # noqa: BLE001
    upload = ""
    check("MediaService.upload_file exists", False, str(exc))

check(
    "the upload path consults the site option",
    "resolve_size_limit(" in upload and "max_size_for(content_type)" not in upload,
    "the ceiling is a module constant again, so the setting the operator "
    "edited does nothing",
)


# ── 6. a recorded health run is actually stored ────────────────────────────
try:
    record = src_of("app.modules.settings.application.site_health_service", "SiteHealthService", "record_run")
except Exception as exc:  # noqa: BLE001
    record = ""
    check("record_run exists", False, str(exc))

tree = ast.parse(inspect.cleandoc(record)) if record else None
adds = []
dead: set[int] = set()
if tree is not None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "db"
        ):
            adds.append(node)
    for outer in ast.walk(tree):
        if isinstance(outer, ast.If) and isinstance(outer.test, ast.Constant) and outer.test.value is False:
            for stmt in outer.body:
                for child in ast.walk(stmt):
                    dead.add(id(child))

check(
    "a health run reaches the session on a live line",
    bool([n for n in adds if id(n) not in dead]),
    "db.add(row) is only inside a dead branch, so the history stays empty "
    "while the report is still returned",
)
check("a health run is committed", "await db.commit()" in record, "never persisted")


# ── 7. the configured post defaults are read ────────────────────────────────
for label, snippet in (
    ("the default category", "OPTION_DEFAULT_CATEGORY"),
    ("the default post format", "OPTION_DEFAULT_POST_FORMAT"),
):
    try:
        src = src_of("app.modules.blog.application.blog_service", "BlogService")
    except Exception as exc:  # noqa: BLE001
        check(f"{label} option is read", False, str(exc))
        continue
    check(
        f"{label} option is read",
        snippet in src,
        "the option exists and nothing reads it, so every new post has to be "
        "filed by hand again",
    )


# ── 8. private notes cannot reach a public read ─────────────────────────────
try:
    from app.modules.blog.application import comment_service

    for method in (
        "list_comments",
        "_get_replies",
        "get_comment_count",
        "get_resource_comment_count",
    ):
        body = inspect.getsource(
            getattr(comment_service.CommentService, method)
        )
        check(
            f"{method} filters on comment_type",
            "COMMENT_TYPE_COMMENT" in body,
            "a private note is reachable through this read path",
        )
except Exception as exc:  # noqa: BLE001
    check("the comment service imports", False, str(exc))


# ── report ──────────────────────────────────────────────────────────────────
print(f"checked {checks} assertions across the P2 deliveries")
if failures:
    print(f"\nFAIL: {len(failures)} assertion(s) do not hold:\n")
    for line in failures:
        print(f"  - {line}")
    raise SystemExit(1)
print("\nPASS: every P2 delivery is still wired to a caller.")