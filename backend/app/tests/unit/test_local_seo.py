"""Tests for Local SEO — business profile → LocalBusiness JSON-LD.

Rules pinned:

- No business name → NO node at all (a nameless LocalBusiness is a
  structured-data error; the generic Organization node already covers the
  store).
- Empty fields are OMITTED, never emitted blank — an empty telephone is a
  Google error against a node that looks filled in the form.
- Bad coordinates are dropped (not emitted as NaN), the rest of the node
  survives.
- Unknown save keys are rejected loudly: a typo'd field would otherwise be
  write-only.
"""

from __future__ import annotations

import pytest

from app.modules.seo.application import local_seo_service as ls


class _OptionsStub:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = dict(values or {})

    async def get(self, db, key, default=None):  # noqa: ANN001
        return self.values.get(key, default)

    async def set(self, db, key, value):  # noqa: ANN001
        self.values[key] = value


@pytest.fixture
def patched(monkeypatch):
    def _patch(values: dict[str, str] | None = None):
        stub = _OptionsStub(values)
        import app.modules.settings.application.site_options_service as sos

        monkeypatch.setattr(sos, "SiteOptionsService", stub)
        return stub

    return _patch


@pytest.mark.asyncio
async def test_no_name_means_no_node(patched):
    patched({})
    node = await ls.build_local_business_jsonld(None, base_url="https://shop.example")
    assert node is None


@pytest.mark.asyncio
async def test_minimal_node_has_name_url_type(patched):
    patched({"local_seo_business_name": "فروشگاه من", "local_seo_business_type": "OnlineStore"})
    node = await ls.build_local_business_jsonld(None, base_url="https://shop.example")
    assert node is not None
    assert node["@type"] == "OnlineStore"
    assert node["name"] == "فروشگاه من"
    assert node["url"] == "https://shop.example"


@pytest.mark.asyncio
async def test_empty_fields_omitted_not_blank(patched):
    patched({"local_seo_business_name": "فروشگاه", "local_seo_telephone": ""})
    node = await ls.build_local_business_jsonld(None, base_url="https://x.example")
    assert "telephone" not in node, "an empty field must be absent, not ''"
    assert "address" not in node


@pytest.mark.asyncio
async def test_full_profile_builds_complete_node(patched):
    patched(
        {
            "local_seo_business_name": "فروشگاه",
            "local_seo_address": "تهران",
            "local_seo_telephone": "021-12345678",
            "local_seo_opening_hours": "Mo-Fr 09:00-18:00",
            "local_seo_price_range": "$$",
            "local_seo_latitude": "35.6892",
            "local_seo_longitude": "51.3890",
        }
    )
    node = await ls.build_local_business_jsonld(None, base_url="https://x.example")
    assert node["telephone"] == "021-12345678"
    assert node["address"]["streetAddress"] == "تهران"
    assert node["geo"]["latitude"] == 35.6892
    assert node["openingHours"] == "Mo-Fr 09:00-18:00"


@pytest.mark.asyncio
async def test_bad_coordinates_dropped_rest_survives(patched):
    patched(
        {
            "local_seo_business_name": "فروشگاه",
            "local_seo_latitude": "not-a-number",
            "local_seo_longitude": "51.3890",
            "local_seo_telephone": "021-1",
        }
    )
    node = await ls.build_local_business_jsonld(None, base_url="https://x.example")
    assert "geo" not in node
    assert node["telephone"] == "021-1", "a bad geo must not take the node down"


@pytest.mark.asyncio
async def test_partial_coordinates_dropped(patched):
    patched({"local_seo_business_name": "ف", "local_seo_latitude": "35.0"})
    node = await ls.build_local_business_jsonld(None, base_url="https://x.example")
    assert "geo" not in node, "lat without lng is not a location"


@pytest.mark.asyncio
async def test_save_rejects_unknown_keys(patched):
    patched({})
    from app.core.exceptions.handlers import ValidationError

    with pytest.raises(ValidationError, match="ناشناخته"):
        await ls.save_business_info(None, {"local_seo_typo": "x"})


@pytest.mark.asyncio
async def test_save_writes_known_keys(patched):
    stub = patched({})
    written = await ls.save_business_info(
        None, {"local_seo_business_name": "فروشگاه تست"}
    )
    assert written == 1
    assert stub.values["local_seo_business_name"] == "فروشگاه تست"


def test_business_types_reasonable():
    assert "Store" in ls.BUSINESS_TYPES
    assert "OnlineStore" in ls.BUSINESS_TYPES
    # Not the full ~100-type schema.org list; a curated shortlist.
    assert len(ls.BUSINESS_TYPES) <= 10
