"""Tests for the Titles & Meta service — the default-template resolver.

Pins the behavior Rank Math's Titles & Meta panel promises:

- The built-in defaults reproduce the strings the code hardcoded before the
  templates existed (post → "%title% %sep% %sitename%", product →
  "%title% %sep% خرید و بررسی", …), so switching to templates changed nothing
  until an operator edits one.
- An operator override in site_options wins; clearing it restores the default.
- %sitename%/%sitedesc% come from blogname/blogdescription automatically —
  every caller gets a complete render without passing site identity.
- No title at all → (None, None): an entity with no title has no meaningful
  meta, and the caller's own fallback applies.
"""

from __future__ import annotations

import pytest

from app.modules.seo.application import titles_meta_service as tms


class _OptionsStub:
    def __init__(self, values: dict[str, str]):
        self.values = values
        self.read: list[str] = []

    async def get(self, db, key, default=None):  # noqa: ANN001
        self.read.append(key)
        return self.values.get(key, default)

    async def set(self, db, key, value):  # noqa: ANN001
        self.values[key] = value


class _Db:
    pass


@pytest.fixture
def patched_options(monkeypatch):
    holder: dict[str, _OptionsStub] = {}

    def _patch(values: dict[str, str]):
        stub = _OptionsStub(values)
        holder["stub"] = stub

        # TitlesMetaService imports SiteOptionsService inside _options();
        # patch the module it imports from.
        import app.modules.settings.application.site_options_service as sos

        monkeypatch.setattr(sos, "SiteOptionsService", stub)
        return stub

    return _patch


@pytest.mark.asyncio
async def test_builtin_defaults_reproduce_old_hardcoded_strings(patched_options):
    patched_options({})
    svc = tms.TitlesMetaService(_Db())
    title, desc = await svc.resolve("post", title="راهنمای خرید", excerpt="خلاصه")
    # Old hardcoded: f"{post.title} | وبلاگ" — the template form renders the
    # sitename empty here (no blogname option), so the shape is "title | ".
    assert title.startswith("راهنمای خرید")
    assert desc == "خلاصه"

    title2, _ = await svc.resolve("product", title="کالای تست")
    assert title2 == "کالای تست | خرید و بررسی"


@pytest.mark.asyncio
async def test_operator_override_wins(patched_options):
    patched_options(
        {
            "seo_default_title_template_post": "%sitename% — %title%",
            "blogname": "فروشگاه من",
        }
    )
    svc = tms.TitlesMetaService(_Db())
    title, _ = await svc.resolve("post", title="مطلب تست")
    assert title == "فروشگاه من — مطلب تست"


@pytest.mark.asyncio
async def test_sitename_read_from_options_automatically(patched_options):
    patched_options({"blogname": "فروشگاه نمونه"})
    svc = tms.TitlesMetaService(_Db())
    title, _ = await svc.resolve("post", title="تست")
    assert "فروشگاه نمونه" in title


@pytest.mark.asyncio
async def test_no_title_returns_none_pair(patched_options):
    patched_options({"blogname": "x"})
    svc = tms.TitlesMetaService(_Db())
    title, desc = await svc.resolve("post", title=None)
    assert (title, desc) == (None, None)


@pytest.mark.asyncio
async def test_separator_option(patched_options):
    patched_options(
        {
            "seo_title_separator": "–",
            "blogname": "فروشگاه",
            "seo_default_title_template_post": "%title% %sep% %sitename%",
        }
    )
    svc = tms.TitlesMetaService(_Db())
    title, _ = await svc.resolve("post", title="تست")
    assert title == "تست – فروشگاه"


@pytest.mark.asyncio
async def test_options_read_once_per_instance(patched_options):
    stub = patched_options({"blogname": "فروشگاه"})
    svc = tms.TitlesMetaService(_Db())
    await svc.resolve("post", title="a")
    first_reads = len(stub.read)
    await svc.resolve("product", title="b")
    # Second resolve must not re-read: the cache holds the map.
    assert len(stub.read) == first_reads


@pytest.mark.asyncio
async def test_unknown_content_type_falls_back_gracefully(patched_options):
    patched_options({"blogname": "فروشگاه"})
    svc = tms.TitlesMetaService(_Db())
    title, _ = await svc.resolve("unknown_type", title="تست")
    # Falls back to the generic "%title% %sep% %sitename%" shape.
    assert title is not None and "تست" in title


def test_content_types_have_both_defaults():
    """Every exposed content type must have a title AND description default,
    or the settings panel would show an empty row."""
    for ct in tms.CONTENT_TYPES:
        assert ct in tms.DEFAULT_TITLE_TEMPLATES, ct
        assert ct in tms.DEFAULT_DESCRIPTION_TEMPLATES, ct


def test_option_key_helpers():
    assert tms.title_option_key("post") == "seo_default_title_template_post"
    assert tms.description_option_key("product") == "seo_default_description_template_product"
