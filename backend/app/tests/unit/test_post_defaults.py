"""Tests for the default category and post format on a new post.

``default_category`` and ``default_post_format`` were seeded and never read, so
every new post had to have its category picked by hand and always landed on the
"standard" format. These tests cover the resolution helpers, which are the part
that can be wrong quietly.

The category option holds a *slug*, not an id: an id is meaningless across
installs, and the settings card is written by a person who has the slug in front
of them.
"""

from __future__ import annotations

import uuid

import pytest

import app.modules.blog.domain.models  # noqa: F401
import app.modules.orders.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.blog.application.blog_service import (
    OPTION_DEFAULT_CATEGORY,
    OPTION_DEFAULT_POST_FORMAT,
    BlogService,
)
from app.modules.blog.domain.models import PostFormat


class _Result:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _OptionsStub:
    """Stands in for SiteOptionsService; records the keys that were read."""

    def __init__(self, values: dict[str, str]):
        self.values = values
        self.read: list[str] = []

    async def get(self, db, key, default=None):
        self.read.append(key)
        return self.values.get(key, default)


class _DbStub:
    """Answers only the category lookup; the options read is patched."""

    def __init__(self, category_id=None):
        self.category_id = category_id
        self.queries: list[str] = []

    async def execute(self, stmt):
        sql = str(stmt)
        self.queries.append(sql)
        return _Result(self.category_id)

    async def get(self, model, pk):
        return None


@pytest.fixture
def options(monkeypatch):
    """Install a SiteOptionsService stub and hand it back for configuration."""
    stub = _OptionsStub({})
    monkeypatch.setattr(
        "app.modules.settings.application.site_options_service.SiteOptionsService", stub
    )
    return stub


def _svc(db: _DbStub) -> BlogService:
    return BlogService(db)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_no_category_option_means_no_default(options):
    db = _DbStub()
    assert await _svc(db)._default_category_id() is None
    assert OPTION_DEFAULT_CATEGORY in options.read


@pytest.mark.asyncio
async def test_blank_option_means_no_default(options):
    # A store that deliberately has no default category sets the option to "".
    # Treating that as a slug would produce a lookup for a category named "".
    options.values[OPTION_DEFAULT_CATEGORY] = "   "
    assert await _svc(_DbStub())._default_category_id() is None


@pytest.mark.asyncio
async def test_slug_resolves_to_an_id(options):
    options.values[OPTION_DEFAULT_CATEGORY] = "news"
    found = uuid.uuid4()
    assert await _svc(_DbStub(category_id=found))._default_category_id() == found


@pytest.mark.asyncio
async def test_unresolvable_slug_returns_none_instead_of_raising(options):
    # The default category was deleted. Blocking post creation over a stale
    # setting would be worse than writing an uncategorised post, which is what
    # happened before the option was read at all.
    options.values[OPTION_DEFAULT_CATEGORY] = "gone"
    assert await _svc(_DbStub(category_id=None))._default_category_id() is None


@pytest.mark.asyncio
async def test_the_query_filters_on_slug_not_id(options):
    # The option holds a slug, not an id: an id is meaningless across installs
    # and the settings card is written by a person who has the slug to hand.
    options.values[OPTION_DEFAULT_CATEGORY] = "news"
    db = _DbStub(category_id=uuid.uuid4())
    await _svc(db)._default_category_id()
    assert "slug" in db.queries[0]


# ----------------------------------------------------------- post format


@pytest.mark.asyncio
async def test_an_explicit_format_is_kept(options):
    got = await _svc(_DbStub())._default_post_format(PostFormat.GALLERY.value)
    assert got == PostFormat.GALLERY.value
    assert OPTION_DEFAULT_POST_FORMAT not in options.read, (
        "an explicit choice must not consult the option"
    )


@pytest.mark.asyncio
async def test_the_configured_format_is_used_when_none_is_given(options):
    options.values[OPTION_DEFAULT_POST_FORMAT] = "quote"
    assert await _svc(_DbStub())._default_post_format(None) == "quote"


@pytest.mark.asyncio
async def test_no_option_means_standard(options):
    assert await _svc(_DbStub())._default_post_format(None) == PostFormat.STANDARD.value


@pytest.mark.asyncio
async def test_an_unknown_configured_format_falls_back_to_standard(options):
    # A typo in the options table must not produce a post whose format no
    # renderer recognises.
    options.values[OPTION_DEFAULT_POST_FORMAT] = "galaury"
    assert await _svc(_DbStub())._default_post_format(None) == PostFormat.STANDARD.value


@pytest.mark.asyncio
async def test_a_blank_option_falls_back_to_standard(options):
    options.values[OPTION_DEFAULT_POST_FORMAT] = "  "
    assert await _svc(_DbStub())._default_post_format(None) == PostFormat.STANDARD.value
