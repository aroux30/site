"""Tests for breadcrumb settings (Rank Math's Breadcrumbs panel).

The home label, separator and blog-crumb toggle shape both the visible trail
and the BreadcrumbList JSON-LD — one source, so the two cannot disagree (a
structured trail that disagrees with the page is a Rich Results mismatch).
"""

from __future__ import annotations

import pytest

from app.shared.content import breadcrumbs as bc


class _OptionsStub:
    def __init__(self, values: dict[str, str]):
        self.values = values

    async def get(self, db, key, default=None):  # noqa: ANN001
        return self.values.get(key, default)


@pytest.fixture
def patched(monkeypatch):
    def _patch(values: dict[str, str]):
        import app.modules.settings.application.site_options_service as sos

        monkeypatch.setattr(sos, "SiteOptionsService", _OptionsStub(values))

    return _patch


@pytest.mark.asyncio
async def test_defaults_when_unset(patched):
    patched({})
    opts = await bc.settings(None)
    assert opts["home_label"] == "خانه"
    assert opts["show_blog"] is True
    assert opts["separator"] == "/"


@pytest.mark.asyncio
async def test_custom_home_label(patched):
    patched({"seo_breadcrumb_home_label": "صفحه اصلی"})
    opts = await bc.settings(None)
    assert opts["home_label"] == "صفحه اصلی"


@pytest.mark.asyncio
async def test_show_blog_toggle_off(patched):
    patched({"seo_breadcrumb_show_blog": "0"})
    opts = await bc.settings(None)
    assert opts["show_blog"] is False


@pytest.mark.asyncio
async def test_post_trail_respects_show_blog_off(patched):
    patched({"seo_breadcrumb_show_blog": "0", "seo_breadcrumb_home_label": "خانه"})
    crumbs = await bc.BreadcrumbService.for_blog_post(
        None, title="پست", slug="p", category_name="آموزش", category_slug="edu"
    )
    labels = [c.label for c in crumbs]
    assert "وبلاگ" not in labels
    assert labels == ["خانه", "آموزش", "پست"]


@pytest.mark.asyncio
async def test_post_trail_uses_custom_home_label(patched):
    patched({"seo_breadcrumb_home_label": "شروع"})
    crumbs = await bc.BreadcrumbService.for_blog_post(None, title="پست", slug="p")
    assert crumbs[0].label == "شروع"
    assert crumbs[0].url == "/"


@pytest.mark.asyncio
async def test_settings_fail_open_on_error(patched, monkeypatch):
    """An options outage must not blank every trail on the site."""

    class _Boom:
        async def get(self, db, key, default=None):  # noqa: ANN001
            raise RuntimeError("db down")

    import app.modules.settings.application.site_options_service as sos

    monkeypatch.setattr(sos, "SiteOptionsService", _Boom())
    opts = await bc.settings(None)
    assert opts == {"home_label": "خانه", "show_blog": True, "separator": "/"}


def test_to_json_ld_positions_are_sequential():
    crumbs = [
        bc.Breadcrumb(label="خانه", url="/"),
        bc.Breadcrumb(label="پست", is_current=True),
    ]
    node = bc.BreadcrumbService.to_json_ld(crumbs, base_url="https://x.example")
    positions = [i["position"] for i in node["itemListElement"]]
    assert positions == [1, 2]
    # The current crumb has no item URL (it IS the page).
    assert "item" not in node["itemListElement"][1]
