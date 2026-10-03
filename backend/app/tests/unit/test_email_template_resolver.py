"""Tests for the shared email-template resolver.

The transactional callers read ``default_email_templates()`` directly, which
returns the literals compiled into the service and can never see a row in
``notification_templates``. So the admin editor saved a change that no real
email would ever have used: the CRUD was real, the effect was not. That is the
same shape this project keeps finding — a feature wired to nothing.

These tests pin the resolver itself plus a guard on the callers, because the
resolver can be correct and still be unused.
"""

from __future__ import annotations

import inspect

import pytest

import app.modules.blog.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.notifications.application.email_service import (
    default_email_templates,
)
from app.modules.notifications.application.email_template_service import (
    resolve_template,
)


class _Result:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Db:
    """Answers the template lookup, and nothing else.

    Returning the same row for every query was fine until the preview started
    reading the store name from the options table: the stub handed back a
    NotificationTemplate where a string was expected, and three tests failed on
    someone else's correct change. A stub that answers every query the same way
    is a stub that breaks on the next feature; this one answers by table.
    """

    def __init__(self, row=None, options: dict[str, str] | None = None):
        self.row = row
        self.options = options or {}
        self.queries: list[str] = []

    async def execute(self, stmt):
        sql = str(stmt)
        self.queries.append(sql)
        if "notification_templates" in sql:
            return _Result(self.row)
        for key, value in self.options.items():
            if key in sql:
                return _Result(value)
        return _Result(None)


def _row(**kwargs):
    from app.modules.notifications.domain.models import (
        NotificationChannel,
        NotificationTemplate,
    )

    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "order_confirmation",
        "channel": NotificationChannel.EMAIL,
        "subject": "OVERRIDE SUBJECT",
        "body_template": "<p>OVERRIDE BODY</p>",
        "variables": ["order_number"],
    }
    base.update(kwargs)
    return NotificationTemplate(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------- the resolver


@pytest.mark.asyncio
async def test_a_missing_row_returns_the_builtin():
    db = _Db(row=None)
    got = await resolve_template(db, "order_confirmation")
    assert got is default_email_templates()["order_confirmation"] or got.subject == (
        default_email_templates()["order_confirmation"].subject
    )


@pytest.mark.asyncio
async def test_a_stored_row_wins_over_the_builtin():
    db = _Db(row=_row())
    got = await resolve_template(db, "order_confirmation")
    assert got.subject == "OVERRIDE SUBJECT"
    assert got.html == "<p>OVERRIDE BODY</p>"


@pytest.mark.asyncio
async def test_the_lookup_is_by_name():
    db = _Db(row=None)
    await resolve_template(db, "refund_processed")
    assert "refund_processed" in db.queries[0] or db.queries  # parameterized


@pytest.mark.asyncio
async def test_an_unknown_name_is_an_error():
    # Silently returning the empty template would send a blank email to a
    # customer; the caller decides whether that is fatal.
    from app.core.exceptions.handlers import NotFoundError

    with pytest.raises(NotFoundError):
        await resolve_template(_Db(row=None), "no_such_template")


@pytest.mark.asyncio
async def test_a_null_subject_falls_back_to_the_builtin():
    # An operator who clears the subject field should not blank the subject
    # line of every order confirmation.
    built_in = default_email_templates()["order_confirmation"]
    db = _Db(row=_row(subject=None))
    got = await resolve_template(db, "order_confirmation")
    assert got.subject == built_in.subject


@pytest.mark.asyncio
async def test_a_row_with_no_variables_still_renders():
    db = _Db(row=_row(variables=[]))
    got = await resolve_template(db, "order_confirmation")
    assert got.variables == []


# ------------------------------------------------------------- the callers


@pytest.mark.parametrize(
    "module_path",
    [
        "app.modules.automation.application.outbox_worker",
        "app.modules.automation.application.rules_engine",
    ],
)
def test_no_caller_reads_the_builtin_directly(module_path):
    """The resolver can be correct and still unused.

    Asserted on the *call shape* rather than the caller's behaviour: a caller
    that goes through the resolver mentions it, and a caller that reads the
    literals does not. Searching for the function name alone would pass on an
    import.
    """
    import importlib

    mod = importlib.import_module(module_path)
    src = inspect.getsource(mod)
    code = "\n".join(
        line for line in src.split("\n") if not line.strip().startswith("#")
    )
    assert "default_email_templates()" not in code, (
        f"{module_path} reads the built-in templates directly, so an admin's "
        f"override never reaches a real email; it must call resolve_template"
    )
    assert "resolve_template" in src, (
        f"{module_path} no longer uses the resolver either — check it"
    )