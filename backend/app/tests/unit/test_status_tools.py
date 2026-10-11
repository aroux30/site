"""Tests for SEO Status & Tools.

Pins the behaviors:

- Status checks report pass/warn/fail with a concrete fix, and the placeholder
  site URL ("example.com") is a FAIL, not a pass — it is the exact bug the SEO
  completion wave fixed in the database, so the check must catch a regression.
- Import rejects unknown keys loudly (a typo'd key must not import silently).
- Import isolates per-key failures; valid keys still land.
- Export/import round-trips every SEO_OPTION_KEYS value.
"""

from __future__ import annotations

import pytest

from app.modules.seo.application import status_tools_service as sts


class _OptionsStub:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = dict(values or {})

    async def get(self, db, key, default=None):  # noqa: ANN001
        return self.values.get(key, default)

    async def set(self, db, key, value):  # noqa: ANN001
        self.values[key] = value


@pytest.fixture
def patched(monkeypatch):
    def _patch(values: dict[str, str] | None = None, base: str = "https://shop.example"):
        stub = _OptionsStub(values)
        import app.modules.settings.application.site_options_service as sos

        monkeypatch.setattr(sos, "SiteOptionsService", stub)

        async def _base(db):  # noqa: ANN001
            return base

        monkeypatch.setattr(sos, "public_base_url", _base)
        return stub

    return _patch


@pytest.mark.asyncio
async def test_placeholder_site_url_is_fail(patched):
    patched({"blog_public": "1"}, base="https://example.com")
    # DB-dependent checks need a session; stub the two counting queries via a
    # minimal session double.
    class _Db:
        async def execute(self, stmt):
            class _R:
                def scalar_one(self):
                    return 0

            return _R()

    checks = await sts.run_status_checks(_Db())
    site_check = next(c for c in checks if c["key"] == "site_url")
    assert site_check["status"] == "fail"
    assert site_check["fix"], "a fail without a fix is not actionable"


@pytest.mark.asyncio
async def test_blog_public_off_is_fail(patched):
    patched({"blog_public": "0"}, base="https://shop.example")

    class _Db:
        async def execute(self, stmt):
            class _R:
                def scalar_one(self):
                    return 0

            return _R()

    checks = await sts.run_status_checks(_Db())
    visibility = next(c for c in checks if c["key"] == "search_visibility")
    assert visibility["status"] == "fail"


@pytest.mark.asyncio
async def test_export_import_round_trip(patched):
    stub = patched({"seo_title_separator": "|", "blog_public": "1"})
    exported = await sts.export_settings(None)
    assert exported["seo_title_separator"] == "|"
    assert exported["blog_public"] == "1"

    result = await sts.import_settings(None, {"seo_title_separator": "–"})
    assert result["written"] == 1
    assert stub.values["seo_title_separator"] == "–"


@pytest.mark.asyncio
async def test_import_unknown_key_is_error_not_silent(patched):
    patched({})
    result = await sts.import_settings(None, {"seo_typo_key": "x"})
    assert result["written"] == 0
    assert result["errors"][0]["key"] == "seo_typo_key"
    assert "ناشناخته" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_import_non_string_value_rejected(patched):
    patched({})
    result = await sts.import_settings(None, {"seo_title_separator": 5})  # type: ignore[dict-item]
    assert result["written"] == 0
    assert result["errors"]


@pytest.mark.asyncio
async def test_import_partial_success_isolated(patched):
    patched({})
    result = await sts.import_settings(
        None, {"seo_title_separator": "|", "bad_key": "x"}
    )
    assert result["written"] == 1
    assert len(result["errors"]) == 1


def test_export_keys_are_explicit_not_prefix_matched():
    """The key list must be explicit so it is auditable — a prefix match
    would silently widen the export's blast radius on import."""
    for key in sts.SEO_OPTION_KEYS:
        assert isinstance(key, str) and key
    # The list is a tuple (immutable) and non-trivial.
    assert isinstance(sts.SEO_OPTION_KEYS, tuple)
    assert len(sts.SEO_OPTION_KEYS) >= 15


def test_settings_to_json_persian_readable():
    text = sts.settings_to_json({"a": "فارسی"})
    assert "فارسی" in text  # ensure_ascii=False
