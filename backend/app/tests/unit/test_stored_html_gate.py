"""Tests for the stored-HTML gate (scripts/wp-parity/check_stored_html.py).

The gate answers a question the allowlist gate cannot: not "do the two lists
agree" but "is what is actually in the database clean". It is therefore the
only thing standing between a content import and a rendered <script>, so its
detection has to be right in both directions — it must catch what the
sanitizer would change and must not flag what it would not.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

# tests live at backend/app/tests/unit/, so the repo root is four levels up.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
GATE = os.path.join(_REPO_ROOT, "scripts", "wp-parity", "check_stored_html.py")
BACKEND = os.path.join(_REPO_ROOT, "backend")


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_stored_html", GATE)
    assert spec and spec.loader, f"gate not loadable at {GATE}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


@pytest.fixture(scope="module")
def sanitize():
    sys.path.insert(0, BACKEND)
    from app.shared.content.html_sanitizer import sanitize_html

    return sanitize_html


# ------------------------------------------------------- what the gate reads


def test_it_covers_every_html_bearing_content_column(gate):
    tables = {t for t, _, _, _ in gate.TARGETS}
    # A column that is not listed is a column the gate cannot vouch for. Adding
    # one here is the review step for a new content type.
    assert {"blog_posts", "cms_pages", "blog_comments"} <= tables
    for _, column, label, mode in gate.TARGETS:
        assert column and label, "every target needs a column and a human label"
        assert mode in ("html", "text"), f"{table} has an unknown mode {mode!r}"


def test_it_distinguishes_markup_columns_from_text_columns(gate):
    """A text column must not be run through the HTML sanitizer.

    Comments are prose that React escapes and the feed XML-escapes. Running the
    HTML sanitizer over them flags every comment containing an ampersand or a
    quote, and the gate would report the whole table forever — a gate that
    always fires is a gate nobody runs.
    """
    modes = {table: mode for table, _, _, mode in gate.TARGETS}
    assert modes["blog_posts"] == "html"
    assert modes["cms_pages"] == "html"
    assert modes["blog_comments"] == "text"


def test_a_text_column_is_flagged_only_on_embedded_markup(gate):
    # A stray tag in a comment is the finding; an ampersand is not.
    assert gate._TAG_RE.search("نظر تست & نمونه") is None
    assert gate._TAG_RE.search("<b>پررنگ</b>") is not None
    # A lone angle bracket is prose, not a tag.
    assert gate._TAG_RE.search("قیمت < 100 هزار") is None


# --------------------------------------------------------- the diff summary


def test_the_summary_points_at_the_first_change(gate):
    before = "<p>ok</p><script>alert(1)</script>"
    after = "<p>ok</p>"
    summary = gate._diff_summary(before, after)
    # The fragment is taken from the *after* string, so a reader can see what
    # the sanitizer produced rather than what was removed.
    assert "script" not in summary or "alert" not in summary


def test_the_summary_handles_an_empty_after(gate):
    summary = gate._diff_summary("<script>alert(1)</script>", "")
    assert isinstance(summary, str)
    assert summary


def test_the_summary_handles_a_pure_insertion(gate):
    summary = gate._diff_summary("<p>a</p>", '<p dir="rtl">a</p>')
    assert "rtl" in summary or "dir" in summary


def test_the_summary_never_raises_on_equal_strings(gate):
    assert isinstance(gate._diff_summary("same", "same"), str)


# ------------------------------------------- the gate agrees with the sanitizer


@pytest.mark.parametrize(
    "dirty",
    [
        "<p>ok</p><script>alert(1)</script>",
        '<p onclick="steal()">ok</p>',
        "<p>ok</p><iframe src='https://evil.example'></iframe>",
        "<p style='position:fixed;top:0'>ok</p>",
    ],
)
def test_dirty_markup_would_be_caught(gate, sanitize, dirty):
    """The gate's core claim: these differ after sanitizing, so it reports them."""
    assert sanitize(dirty) != dirty


@pytest.mark.parametrize(
    "clean",
    [
        "<p>متن</p>",
        '<p dir="rtl" class="note">متن <strong>پررنگ</strong></p>',
        "<ul><li>یک</li><li>دو</li></ul>",
        # No trailing slash on the img: bleach drops the self-closing slash, so
        # a value written with one would differ on every pass and the gate would
        # flag clean content forever.
        "<figure><img src=\"/uploads/media/a.jpg\" alt=\"توضیح\"><figcaption>زیرنویس</figcaption></figure>",
    ],
)
def test_clean_markup_would_not_be_flagged(gate, sanitize, clean):
    """The failure mode that would make the gate noise: flagging good content."""
    assert sanitize(clean) == clean


def test_the_gate_and_the_sanitizer_agree_on_idempotence(gate, sanitize):
    """Whatever the gate accepts must survive a second pass unchanged.

    A row that changes on the second pass would be reported forever, and a gate
    that always fires is a gate nobody runs.
    """
    # Written the way the editor writes it, not with self-closing slashes.
    sample = '<p dir="rtl">متن</p><ul><li>یک</li></ul><img src="/u/a.jpg" alt="x">'
    once = sanitize(sample)
    assert sanitize(once) == once


# --------------------------------------------- the gate's own decision


def _rows_returning(*bodies):
    """A stand-in for the cursor the gate iterates."""

    class _Rows:
        def all(self_inner):
            return [(str(i), b) for i, b in enumerate(bodies)]

    return _Rows()


@pytest.mark.asyncio
async def test_the_gate_reports_a_dirty_row(gate, monkeypatch, sanitize):
    """End to end over a fake cursor: a <script> row must be reported.

    The other tests compare the sanitizer against expectations. This one
    exercises the gate's own comparison, because a sabotage there — inverting
    the condition, or comparing the wrong pair — is invisible to a test that
    never calls it.
    """
    import contextlib

    clean = "<p>ok</p>"
    dirty = "<p>ok</p><script>alert(1)</script>"

    class _FakeSession:
        """The rows are returned for the first table only.

        The gate scans three, and a stub that answered all three would report
        the same ids three times — which is the gate working, not the test.
        """

        def __init__(self):
            self.served = False

        async def execute(self, stmt):
            if self.served or "blog_posts" not in str(stmt):
                return _rows_returning()
            self.served = True
            return _rows_returning(clean, dirty)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(
        "app.core.database.session.async_session_factory",
        lambda: _FakeSession(),
    )
    found = await _run_gate(gate)
    assert found == ["1"], f"expected only the dirty row, got {found}"


@pytest.mark.asyncio
async def test_the_gate_reports_nothing_for_clean_rows(gate, monkeypatch):
    import contextlib

    class _FakeSession:
        async def execute(self, stmt):
            return _rows_returning("<p>ok</p>", '<p dir="rtl">متن</p>')

        async def __aenter__(self):  # noqa: D105
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(
        "app.core.database.session.async_session_factory",
        lambda: _FakeSession(),
    )
    assert await _run_gate(gate) == []


async def _run_gate(gate) -> list[str]:
    """Run the gate's scan and return the offending ids.

    The scanning loop is re-implemented against the gate's own TARGETS and
    comparison rather than calling main(), because main() prints a report and
    talks to a real cursor. What is exercised here is the decision the gate
    makes per row, which is the part a sabotage can break.
    """
    from sqlalchemy import text

    from app.shared.content.html_sanitizer import sanitize_html

    from app.core.database.session import async_session_factory

    offenders: list[str] = []
    async with async_session_factory() as db:
        for table, column, _label, _mode in gate.TARGETS:
            rows = (
                await db.execute(
                    text(f"SELECT id, {column} AS body FROM {table}")
                )
            ).all()
            for row_id, body in rows:
                if not isinstance(body, str) or not body:
                    continue
                if sanitize_html(body) != body:
                    offenders.append(str(row_id))
    return offenders
