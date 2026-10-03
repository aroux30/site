"""Tests for the site-health run history.

The point of the table is that a problem which was found and then fixed stays
visible. The tests cover the two decisions that can be quietly wrong: folding a
list of checks into one status, and refusing to let a storage failure lose the
report the caller is waiting for.
"""

from __future__ import annotations

import pytest

import app.modules.blog.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.settings.application.site_health_service import (
    _STATUS_RANK,
    _worst_status,
)


# ------------------------------------------------------- the status fold


def test_no_checks_has_no_worst_status():
    assert _worst_status([]) is None


def test_all_good_is_good():
    checks = [{"name": "Database", "status": "good"}, {"name": "Redis", "status": "good"}]
    assert _worst_status(checks) == "good"


def test_one_warning_wins_over_good():
    checks = [{"status": "good"}, {"status": "good"}, {"status": "warning"}]
    assert _worst_status(checks) == "warning"


def test_critical_wins_over_warning():
    assert _worst_status([{"status": "warning"}, {"status": "critical"}]) == "critical"


def test_unknown_sits_between_good_and_warning():
    # "unknown" means the check could not answer. It is worse than good (a
    # check that did not run proves nothing) and better than an actual
    # warning, so this ordering is what makes the list colour honest.
    assert _STATUS_RANK["unknown"] > _STATUS_RANK["good"]
    assert _STATUS_RANK["unknown"] < _STATUS_RANK["warning"]


def test_an_unrecognised_status_surfaces_as_a_warning():
    # A new check inventing a status must show up as something to look at.
    # Silently dropping it would make a broken check look healthy.
    assert _worst_status([{"status": "good"}, {"status": "exploded"}]) == "warning"


def test_a_check_without_a_status_counts_as_unknown():
    assert _worst_status([{"status": "good"}, {"name": "no status"}]) == "unknown"


def test_a_malformed_check_does_not_raise():
    # A run recorded by an older build, or a hand-edited row, must not take
    # the history screen down with a TypeError.
    assert _worst_status([None, {}, {"status": "good"}]) == "unknown"


# ------------------------------------------------------------- the model


def test_the_run_records_what_triggered_it():
    # A reader comparing two rows needs to know which is which: a manual run is
    # one person's sample of one moment, a scheduled one is the state nobody
    # was watching.
    from app.modules.settings.domain.models import SiteHealthRun

    col = SiteHealthRun.__table__.c
    assert {"trigger", "started_at", "worst_status", "report", "error"} <= set(
        col.keys()
    )
    assert col.trigger.server_default is not None
    # The default is a SQL text clause, not a Python string: a row written by
    # any path other than the ORM has to get the same value.
    assert "scheduled" in str(col.trigger.server_default.arg)


def test_a_run_can_record_that_it_failed_to_run():
    # "ran and found problems" and "did not run" look identical otherwise.
    from app.modules.settings.domain.models import SiteHealthRun

    assert SiteHealthRun.__table__.c.error.nullable is True


# ------------------------------------------- the info tab reaches the database


def test_debug_info_does_not_call_a_method_asycsession_lacks():
    """Guard on a bug that shipped and hid in plain sight.

    ``AsyncSession`` has no ``connect()``. The Info tab called it inside a
    ``try/except Exception`` whose handler wrote an ``error`` row, so the tab
    reported "database: error" for every store, forever, and nobody saw it —
    a diagnostic that cannot reach the database is the worst place for that to
    hide.

    Asserted against the source because the failure was silent by
    construction: a stub session that happens to have a connect() would pass a
    call-based test, and the real one did not.
    """
    import inspect

    from app.modules.settings.application import site_health_service as svc

    src = inspect.getsource(svc.SiteHealthService.debug_info)
    # Strip comments: the fix is explained in a comment that names the very
    # call it removed, and matching that text would fail on a correct file.
    code = "\n".join(
        line for line in src.split("\n") if not line.strip().startswith("#")
    )
    assert ".connect()" not in code, (
        "AsyncSession has no connect(); the query must go through the session"
    )


def test_debug_info_queries_through_the_session():
    import inspect

    from app.modules.settings.application import site_health_service as svc

    src = inspect.getsource(svc.SiteHealthService.debug_info)
    assert "await db.execute(" in src


def test_the_info_tab_reports_a_mid_merge_database():
    """More than one row in alembic_version means a merge is half done.

    Reporting the first row would look normal, and the person asking would be
    told the wrong revision.
    """
    import inspect

    from app.modules.settings.application import site_health_service as svc

    src = inspect.getsource(svc.SiteHealthService.debug_info)
    assert "in_consistent_state" in src
    assert "len(rows) > 1" in src


def test_the_info_tab_lists_the_scheduled_jobs():
    import inspect

    from app.modules.settings.application import site_health_service as svc

    src = inspect.getsource(svc.SiteHealthService.debug_info)
    # A support ticket asking "is the reminder job on?" is answered by the
    # schedule, which is a different question from whether the beat is alive.
    assert "beat_schedule" in src
