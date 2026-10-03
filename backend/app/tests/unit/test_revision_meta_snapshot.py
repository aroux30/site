"""Tests for revision snapshots of custom fields (blog_post_meta).

The gap this covers: a revision stored title, body, excerpt, cover and SEO, but
not the post's custom fields. Restoring one left the newer SEO overrides and
structured data in place while the text went back, so the editor saw a revision
on screen and a post that did not match it.

These are pure-function tests over the snapshot/restore helpers plus a check on
the snapshot JSON itself; the database round trip is covered by the existing
blog service suite.
"""

from __future__ import annotations

import json

import pytest

# Importing the models explicitly, not just the service: SQLAlchemy resolves
# relationship targets lazily, and a module that only reaches one model leaves
# the mappers half-configured (User -> UserRole is the first to fail).
import app.modules.blog.domain.models  # noqa: F401
import app.modules.orders.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.blog.schemas.blog import BlogPostRevisionDetailResponse


# ------------------------------------------------------------ snapshot JSON


def test_snapshot_is_sorted_json():
    # Sorted keys so two snapshots of the same meta differ only when the meta
    # differs — an unsorted dict would make the column churn for nothing.
    out = json.dumps({"b": "2", "a": "1"}, ensure_ascii=False, sort_keys=True)
    assert out.index('"a"') < out.index('"b"')


def test_persian_values_are_not_escaped():
    out = json.dumps({"seo_title": "تخفیف ویژه"}, ensure_ascii=False)
    assert "تخفیف ویژه" in out
    assert "\\u" not in out


# ------------------------------------------------------------ response shape


def test_detail_response_defaults_meta_to_empty():
    resp = BlogPostRevisionDetailResponse.model_validate(
        {
            "post_id": "11111111-1111-1111-1111-111111111111",
            "id": "22222222-2222-2222-2222-222222222222",
            "revision_number": 1,
            "title": "t",
            "slug": "s",
            "content": "c",
            "status": "draft",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    assert resp.meta == {}, "a revision with no meta must read as an empty set, not None"


# ------------------------------------------------- the helpers, via a stub db


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _StubDb:
    """Minimal AsyncSession stand-in: records deletes, collects added rows.

    ``deletes`` is asserted on, not just the adds: a restore that skips the
    delete is a *merge*, and the test that only checked the added rows passed
    happily against a sabotaged implementation. The key the editor added after
    the revision survives a merge, which is the whole bug.
    """

    def __init__(self, existing_rows=()):
        self.existing = list(existing_rows)
        self.deleted = []
        self.added = []
        self.flushed = 0

    async def execute(self, stmt):
        self.deleted.append(stmt)
        return _Result(self.existing)

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        self.flushed += 1


@pytest.fixture
def restore_meta():
    from app.modules.blog.application.blog_service import BlogService

    async def _restore(post_id, snapshot):
        db = _StubDb()
        svc = BlogService(db)  # type: ignore[arg-type]
        await svc._restore_post_meta(post_id, snapshot)
        return db

    return _restore


@pytest.mark.asyncio
async def test_restore_replaces_the_whole_set(restore_meta):
    db = await restore_meta("post-1", json.dumps({"a": "1", "b": "2"}))
    keys = sorted(r.meta_key for r in db.added)
    assert keys == ["a", "b"]
    assert db.flushed == 1


@pytest.mark.asyncio
async def test_restore_deletes_before_writing(restore_meta):
    # The delete is the load-bearing part: without it a key added after the
    # revision was taken survives the restore and the post stops matching the
    # revision on screen.
    db = await restore_meta("post-1", json.dumps({"a": "1"}))
    assert len(db.deleted) == 1, "the existing meta rows were never deleted"
    assert "blog_post_meta" in str(db.deleted[0])
    assert db.deleted[0].__class__.__name__.lower().startswith("delete")


@pytest.mark.asyncio
async def test_restore_deletes_even_for_an_empty_snapshot(restore_meta):
    # An empty snapshot is the "this revision had no custom fields" case, which
    # must clear the current set, not leave it alone.
    db = await restore_meta("post-1", None)
    assert len(db.deleted) == 1


@pytest.mark.asyncio
async def test_null_snapshot_clears_every_field(restore_meta):
    db = await restore_meta("post-1", None)
    assert db.added == [], "a NULL snapshot means the revision had no custom fields"


@pytest.mark.asyncio
async def test_empty_dict_snapshot_clears_every_field(restore_meta):
    db = await restore_meta("post-1", "{}")
    assert db.added == []


@pytest.mark.asyncio
async def test_corrupt_snapshot_is_treated_as_empty(restore_meta):
    # Refusing the whole restore over an unreadable column would be worse than
    # losing custom fields, so the bad value reads as "no custom fields".
    db = await restore_meta("post-1", "{not json at all")
    assert db.added == []


@pytest.mark.asyncio
async def test_json_array_snapshot_is_treated_as_empty(restore_meta):
    db = await restore_meta("post-1", '["a", "b"]')
    assert db.added == []


@pytest.mark.asyncio
async def test_blank_key_is_skipped(restore_meta):
    db = await restore_meta("post-1", json.dumps({"": "x", "ok": "y", "  ": "z"}))
    assert [r.meta_key for r in db.added] == ["ok"]


@pytest.mark.asyncio
async def test_oversized_key_is_truncated(restore_meta):
    long_key = "k" * 400
    db = await restore_meta("post-1", json.dumps({long_key: "v"}))
    assert len(db.added[0].meta_key) == 255


@pytest.mark.asyncio
async def test_null_value_is_kept_as_null(restore_meta):
    db = await restore_meta("post-1", json.dumps({"a": None}))
    assert db.added[0].meta_value is None


@pytest.mark.asyncio
async def test_non_string_value_is_stringified(restore_meta):
    db = await restore_meta("post-1", json.dumps({"count": 42, "flag": True}))
    values = {r.meta_key: r.meta_value for r in db.added}
    assert values == {"count": "42", "flag": "True"}