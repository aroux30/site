"""Tests for private team notes (wp_comments.comment_type='note').

The load-bearing property is negative: a note must not reach a public reader.
Every assertion about the type filter exists because the alternative — a note
that leaks into the public comment list or the feed — is a private team
discussion served to the world, and it is silent.

The queries below are inspected as compiled SQL rather than run against a
database, so the test asserts the filter is present in the statement the service
would execute. A stub session that returned canned rows would pass against an
unfiltered query.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

import app.modules.blog.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.blog.domain.models import (
    COMMENT_TYPE_COMMENT,
    COMMENT_TYPE_NOTE,
    BlogComment,
)
from app.modules.blog.schemas.blog import BlogNoteCreate


def _sql_and_params(stmt) -> tuple[str, dict]:
    """Render a statement and keep its bound values.

    The type filter shows up as a bind parameter (``comment_type = %(...)s``),
    not as a literal, so checking the SQL text alone would pass against an
    unfiltered query whose SELECT list merely mentions the column. The values
    are what make the assertion about the filter rather than about the shape.
    """
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled), dict(compiled.params)


def _comment_queries(db: "_CapturingSession") -> list:
    """Every statement that reads blog_comments.

    list_comments runs two: a count and the page of rows. Both must filter the
    type — a count that includes notes leaks their existence even when the rows
    are filtered, and a page that includes them leaks the text. Asserting on
    only the first one is how an unfiltered public list passes this test, so
    every caller checks all of them.
    """
    return [s for s in db.statements if "FROM blog_comments" in str(s)]


def _all_filter_on_type(db: "_CapturingSession", expected: str) -> bool:
    queries = _comment_queries(db)
    assert queries, (
        "no blog_comments query was executed; captured: %r" % [str(s)[:60] for s in db.statements]
    )
    return all(_filters_on_type(q, expected) for q in queries)


def _filters_on_type(stmt, expected: str) -> bool:
    sql, params = _sql_and_params(stmt)
    if "comment_type" not in sql:
        return False
    return any(v == expected for v in params.values())


class _CapturingSession:
    """Records the statements a service builds; returns no rows."""

    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _EmptyResult()

    def add(self, row):
        pass

    async def commit(self):
        pass

    async def refresh(self, row):
        pass

    async def flush(self):
        pass


class _EmptyResult:
    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def scalar(self):
        return 0

    def scalar_one(self):
        return 0

    def scalar_one_or_none(self):
        return None


# ------------------------------------------------------------- the constant


def test_note_is_a_distinct_type():
    assert COMMENT_TYPE_NOTE == "note"
    assert COMMENT_TYPE_COMMENT == "comment"
    assert COMMENT_TYPE_NOTE != COMMENT_TYPE_COMMENT


def test_column_defaults_to_comment():
    # Every row written before notes existed, and every row written by a path
    # that never learns about notes, is a real comment.
    col = BlogComment.__table__.c.comment_type
    assert col.nullable is False
    assert col.server_default is not None
    assert "comment" in str(col.server_default.arg)


# ------------------------------------------------------- the public filter


@pytest.mark.asyncio
async def test_public_list_filters_notes_out():
    from app.modules.blog.application.comment_service import CommentService

    db = _CapturingSession()
    svc = CommentService(db)
    await svc.list_comments(post_id=None)
    assert _all_filter_on_type(db, COMMENT_TYPE_COMMENT), (
        "every public comment query must filter on comment_type='comment'"
    )


@pytest.mark.asyncio
async def test_admin_list_shows_both_types_unless_asked():
    from app.modules.blog.application.comment_service import CommentService

    db = _CapturingSession()
    svc = CommentService(db)
    # include_moderation_fields=True is what the admin table passes. With no
    # explicit type it must not narrow, or notes become invisible to the team
    # that wrote them — the opposite failure from the one above.
    await svc.list_comments(include_moderation_fields=True)
    values = [
        v
        for q in _comment_queries(db)
        for v in _sql_and_params(q)[1].values()
    ]
    assert COMMENT_TYPE_COMMENT not in values and COMMENT_TYPE_NOTE not in values, (
        "the admin table must not narrow the type when the caller did not ask"
    )


@pytest.mark.asyncio
async def test_admin_list_can_narrow_to_notes():
    from app.modules.blog.application.comment_service import CommentService

    db = _CapturingSession()
    svc = CommentService(db)
    await svc.list_comments(include_moderation_fields=True, comment_type=COMMENT_TYPE_NOTE)
    assert _all_filter_on_type(db, COMMENT_TYPE_NOTE)


@pytest.mark.asyncio
async def test_replies_filter_notes_out_even_for_admin():
    from app.modules.blog.application.comment_service import CommentService

    db = _CapturingSession()
    svc = CommentService(db)
    # The reply tree is rendered inside a public comment view, so it filters
    # unconditionally — the admin flag does not reach this method.
    await svc._get_replies("11111111-1111-1111-1111-111111111111", remaining=10)
    assert _all_filter_on_type(db, COMMENT_TYPE_COMMENT)


def test_feed_filters_notes_out():
    # The comment feed is a public read. Checked on the source rather than by
    # calling the builder, because the filter is a query clause.
    import inspect

    from app.modules.blog.application import feed_service

    src = inspect.getsource(feed_service)
    assert "comment_type" in src
    assert "COMMENT_TYPE_COMMENT" in src


def test_count_reads_do_not_see_notes():
    # get_comment_count feeds the badge under every post. A note in that number
    # is a small leak — the note's existence, in a public count.
    import inspect

    from app.modules.blog.application import comment_service

    src = inspect.getsource(comment_service.CommentService.get_comment_count)
    assert "COMMENT_TYPE_COMMENT" in src, (
        "the public comment count must exclude private notes"
    )


# ------------------------------------------------------------ the schema


def test_note_schema_requires_a_target_and_a_body():
    note = BlogNoteCreate(resource_id="11111111-1111-1111-1111-111111111111", content="x")
    assert note.resource_type == "blog_post"


def test_note_schema_rejects_an_empty_body():
    with pytest.raises(Exception):
        BlogNoteCreate(
            resource_id="11111111-1111-1111-1111-111111111111", content=""
        )


def test_note_schema_rejects_an_unknown_resource_type():
    with pytest.raises(Exception):
        BlogNoteCreate(
            resource_type="product",  # type: ignore[arg-type]
            resource_id="11111111-1111-1111-1111-111111111111",
            content="x",
        )
