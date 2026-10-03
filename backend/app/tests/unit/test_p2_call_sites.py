"""Guards on the *call sites* of the P2 helpers, not on the helpers.

Found by ``scripts/audit_p2_guards.py``: three of the P2 guards passed when
their sabotage was applied, and all three had the same shape — they tested a
helper in isolation and never checked that anything calls it. A helper can be
perfect and unreachable, which is the same failure as a route with no consumer,
one level down.

Each test here reads the source of the method that has to *use* the helper and
fails if the call is gone. That is weaker than exercising it, and deliberately
so: these are wiring guards, and a wiring guard's job is to notice when a line
is deleted, not to re-test the logic the helper's own suite already covers.
"""

from __future__ import annotations

import inspect

import pytest

# --------------------------------------------------------------- quick edit


def test_quick_edit_allows_the_custom_fields():
    """Dropping "meta" from the allow-list makes the dialog's fields vanish.

    The form still renders, still posts, and the save still succeeds — the
    values are simply discarded, which is the failure mode the UI cannot show.
    """
    from app.modules.blog.application.quick_edit_service import QUICK_EDIT_FIELDS

    assert "meta" in QUICK_EDIT_FIELDS, (
        "quick edit no longer accepts 'meta', so the custom-fields section of "
        "the dialog saves nothing and the save still reports success"
    )
    # And it has to be applied as a table replace, not a setattr on the ORM row.
    src = inspect.getsource(
        __import__(
            "app.modules.blog.application.quick_edit_service",
            fromlist=["QuickEditService"],
        ).QuickEditService.quick_edit_post
    )
    assert "BlogPostMeta" in src, (
        "quick edit accepts 'meta' but no longer writes the rows it implies"
    )


def test_quick_edit_handles_tags_too():
    """The dialog has a tag picker; the allow-list is what makes it save."""
    from app.modules.blog.application.quick_edit_service import QUICK_EDIT_FIELDS

    assert "tag_ids" in QUICK_EDIT_FIELDS, (
        "the quick-edit dialog shows a tag picker, so dropping tag_ids makes "
        "the picker inert while still looking functional"
    )


# ------------------------------------------------------------ upload ceiling


def test_the_upload_path_uses_the_configurable_limit():
    """The resolver can be correct and unreachable.

    ``upload_file`` had a hard-coded ceiling with the resolver beside it: the
    setting was stored, editable, and never consulted, which is exactly what the
    store operator would report as "I changed it and nothing happened".
    """
    from app.modules.media.application import media_service

    src = inspect.getsource(media_service.MediaService.upload_file)
    assert "resolve_size_limit(" in src, (
        "upload_file no longer consults the site option, so the ceiling is a "
        "module constant again and the setting does nothing"
    )
    assert "max_size_for(content_type)" not in src, (
        "upload_file went back to the pure default, bypassing the setting"
    )


def test_the_caller_cannot_widen_the_ceiling():
    src = inspect.getsource(
        __import__(
            "app.modules.media.application.media_service", fromlist=["MediaService"]
        ).MediaService.upload_file
    )
    # A narrow route (a thumbnail generator) passes its own cap; the code has to
    # hand it to the resolver, which is what keeps it a tightening.
    assert "max_bytes" in src


# --------------------------------------------------------------- site health


def test_recording_a_run_actually_writes_one():
    """A report that is computed and not stored leaves the history empty.

    Nothing about the check itself changes — it still finds the disk problem —
    but there is no longer any evidence it ever ran, which is the whole point of
    the table.
    """
    from app.modules.settings.application import site_health_service as svc

    import ast

    src = inspect.getsource(svc.SiteHealthService.record_run)
    assert "await db.commit()" in src, "the run row is never committed"

    # ``db.add(row)`` on its own proves nothing: a careless ``if False:`` around
    # it keeps the text and silences the write, and a substring check passes.
    # Found by the guard audit, which did exactly that.
    #
    # Reachability is measured by *ancestor* ids, not by the ids of the dead
    # branch's direct children: the call sits inside an ``Expr`` inside a
    # ``Pass``-or-what, so comparing the call's own id against the branch's
    # statement ids never matches and everything reads as live.
    tree = ast.parse(inspect.cleandoc(src))

    class _Ancestors(ast.NodeVisitor):
        """Every node id that sits under an ``if False`` body."""

        def __init__(self) -> None:
            self.dead: set[int] = set()

        def visit_If(self, node: ast.If) -> None:  # noqa: N802
            if isinstance(node.test, ast.Constant) and node.test.value is False:
                for stmt in node.body:
                    for child in ast.walk(stmt):
                        self.dead.add(id(child))
            self.generic_visit(node)

    visitor = _Ancestors()
    visitor.visit(tree)

    adds = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "add"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "db"
    ]
    assert adds, "the run row is never handed to the session"
    live = [n for n in adds if id(n) not in visitor.dead]
    assert live, (
        "the run row is added only inside a dead branch, so the history stays "
        "empty while the report is still returned"
    )


def test_the_scheduled_task_calls_the_recorder():
    """A beat entry can name a task that exists and still not record anything."""
    import importlib

    tasks = importlib.import_module("app.modules.settings.application.tasks")
    src = inspect.getsource(tasks.run_site_health)
    assert "record_run" in src, (
        "the scheduled task does not call record_run, so the daily job runs and "
        "the history stays empty"
    )
    assert 'trigger="scheduled"' in src, (
        "a run must record that it was scheduled, not that someone pressed the "
        "button: a reader comparing two rows needs to tell them apart"
    )
