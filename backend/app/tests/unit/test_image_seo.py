"""Tests for Image SEO — the upload-time alt/title/caption filler.

Rank Math Pro parity feature: an image without alt is invisible to image
search and a WCAG failure, so the upload path fills blanks from the file name
per site options. The dangerous failure mode is the opposite — overwriting
text a person wrote — so the "operator value wins" cases are pinned first.
"""

from __future__ import annotations

import pytest

from app.modules.media.application import image_seo_service as svc


# ── clean_filename_for_seo ────────────────────────────────────────────────


def test_cleans_dashes_and_underscores():
    assert svc.clean_filename_for_seo("my-product_photo.jpg") == "my product photo"


def test_strips_extension_and_size_suffix():
    assert svc.clean_filename_for_seo("photo-1024x768.jpg") == "photo"


def test_strips_leading_hex_token():
    """The upload pipeline stores hex disk names; they carry no meaning."""
    assert svc.clean_filename_for_seo("a1b2c3d4e5f6-my-photo.png") == "my photo"


def test_keeps_version_like_dots():
    """Only the last dot is an extension: v1.2-final is a name, not a type."""
    assert svc.clean_filename_for_seo("v1.2-final.jpg") == "v1.2 final"


def test_returns_empty_for_too_short_name():
    """A one-character name is noise; the caller must fill nothing."""
    assert svc.clean_filename_for_seo("a.jpg") == ""
    assert svc.clean_filename_for_seo("1.png") == ""


def test_returns_empty_for_uuid_only_name():
    assert svc.clean_filename_for_seo("a1b2c3d4e5f6a7b8.jpg") == ""


def test_persian_filename_kept():
    """Persian names are real names; the cleaner must not eat them."""
    assert svc.clean_filename_for_seo("کاور-محصول.jpg") == "کاور محصول"


def test_empty_separators_means_no_conversion():
    """An empty separator set must not turn into a character-class wildcard."""
    assert svc.clean_filename_for_seo("my-product.jpg", separators="") == "my-product"


# ── apply_case / apply_replacements ───────────────────────────────────────


def test_case_none_is_identity():
    assert svc.apply_case("My Photo", "none") == "My Photo"


def test_case_lower_and_upper():
    assert svc.apply_case("My Photo", "lower") == "my photo"
    assert svc.apply_case("My Photo", "upper") == "MY PHOTO"


def test_replacements_applied_in_order():
    pairs = [{"from": "shoe", "to": "کفش"}, {"from": "red", "to": "قرمز"}]
    assert svc.apply_replacements("red shoe", pairs) == "قرمز کفش"


def test_malformed_replacements_skipped():
    pairs = [{"from": "", "to": "x"}, "not-a-dict", {"from": "a", "to": "b"}]  # type: ignore[list-item]
    assert svc.apply_replacements("aaa", pairs) == "bbb"


# ── generate_text ─────────────────────────────────────────────────────────


def _options(**overrides) -> svc._Options:
    base = dict(
        auto_alt=True,
        auto_title=True,
        auto_caption=False,
        auto_description=False,
        case="none",
        separators=svc.DEFAULT_SEPARATORS,
        replacements=[],
    )
    base.update(overrides)
    return svc._Options(**base)


def test_generate_text_full_pipeline():
    opts = _options(case="upper", replacements=[{"from": "product", "to": "ITEM"}])
    assert svc.generate_text(opts, "my-product.jpg") == "MY ITEM"


def test_generate_text_empty_when_name_useless():
    assert svc.generate_text(_options(), "a.jpg") == ""


# ── fill_metadata (with a stubbed options loader) ─────────────────────────


class _Db:
    """Placeholder session — fill_metadata is tested with load_settings patched."""


@pytest.fixture
def patched_settings(monkeypatch):
    def _patch(opts: svc._Options):
        async def _load(db):
            return opts

        monkeypatch.setattr(svc, "load_settings", _load)

    return _patch


@pytest.mark.asyncio
async def test_fill_sets_alt_when_empty(patched_settings):
    patched_settings(_options())
    alt, title, caption, desc = await svc.fill_metadata(
        _Db(),
        filename="my-product.jpg",
        alt_text=None,
        title=None,
        caption=None,
        description=None,
    )
    assert alt == "my product"
    assert title == "my product"
    # Caption/description default OFF — must stay None.
    assert caption is None
    assert desc is None


@pytest.mark.asyncio
async def test_operator_alt_is_never_overwritten(patched_settings):
    """The critical case: text a person wrote always wins."""
    patched_settings(_options(auto_caption=True))
    alt, title, caption, _desc = await svc.fill_metadata(
        _Db(),
        filename="my-product.jpg",
        alt_text="متن دستی اپراتور",
        title="عنوان دستی",
        caption="",
        description=None,
    )
    assert alt == "متن دستی اپراتور"
    assert title == "عنوان دستی"
    # An empty string counts as blank and gets filled (that is the point).
    assert caption == "my product"


@pytest.mark.asyncio
async def test_whitespace_only_alt_counts_as_blank(patched_settings):
    patched_settings(_options())
    alt, *_ = await svc.fill_metadata(
        _Db(),
        filename="my-product.jpg",
        alt_text="   ",
        title=None,
        caption=None,
        description=None,
    )
    assert alt == "my product"


@pytest.mark.asyncio
async def test_useless_filename_fills_nothing(patched_settings):
    patched_settings(_options(auto_caption=True, auto_description=True))
    alt, title, caption, desc = await svc.fill_metadata(
        _Db(),
        filename="a.jpg",
        alt_text=None,
        title=None,
        caption=None,
        description=None,
    )
    assert (alt, title, caption, desc) == (None, None, None, None)


@pytest.mark.asyncio
async def test_disabled_flags_fill_nothing(patched_settings):
    patched_settings(_options(auto_alt=False, auto_title=False))
    alt, title, *_ = await svc.fill_metadata(
        _Db(),
        filename="my-product.jpg",
        alt_text=None,
        title=None,
        caption=None,
        description=None,
    )
    assert alt is None
    assert title is None
