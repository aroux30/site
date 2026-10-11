"""Tests for Instant Indexing — IndexNow submission + Google skeleton.

The rules pinned here:

- A disabled setting means no request is made at all (the check happens
  before the HTTP call, so "disabled" cannot burn a request).
- A 200/202 counts as submitted; 429 is rate_limited (not an error to
  retry immediately); 422 is rejected with the body as the reason.
- A transport failure returns status=error and never raises — a publish
  must not fail because a search engine's endpoint is down.
- The key is generated once and reused; the key file endpoint serves it
  only at the exact key path.
- Google is a status read, never a request: `connected` is False until
  credentials exist, and no code path calls Google without them.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.modules.seo.application import indexing_service as idx


class _OptionsStub:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = dict(values or {})
        self.set_calls: list[tuple[str, str]] = []

    async def get(self, db, key, default=None):  # noqa: ANN001
        return self.values.get(key, default)

    async def set(self, db, key, value):  # noqa: ANN001
        self.values[key] = value
        self.set_calls.append((key, value))


@pytest.fixture
def patched(monkeypatch):
    """Patch SiteOptionsService + public_base_url inside the service module."""
    holder: dict[str, _OptionsStub] = {}

    def _patch(values: dict[str, str] | None = None, base: str = "https://shop.example"):
        stub = _OptionsStub(values)
        holder["stub"] = stub

        import app.modules.settings.application.site_options_service as sos

        monkeypatch.setattr(sos, "SiteOptionsService", stub)

        async def _base(db):  # noqa: ANN001
            return base

        monkeypatch.setattr(sos, "public_base_url", _base)
        return stub

    return _patch


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_disabled_makes_no_request(patched, monkeypatch):
    patched({"indexnow_enabled": "0"})
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200)

    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(transport=_transport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    result = await idx.submit_urls(None, ["https://shop.example/blog/x"])
    assert result["status"] == "skipped"
    assert result["reason"] == "disabled"
    assert called is False, "a disabled setting must not fire a request"


@pytest.mark.asyncio
async def test_successful_submission(patched, monkeypatch):
    patched({"indexnow_enabled": "1", "indexnow_key": "a" * 32})
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200)

    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(transport=_transport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    result = await idx.submit_urls(None, ["https://shop.example/blog/x"])
    assert result["status"] == "ok"
    assert result["submitted"] == 1
    assert captured["url"] == idx.INDEXNOW_ENDPOINT
    assert captured["body"]["host"] == "shop.example"
    # The keyLocation must be the REAL route path, not the domain root — the
    # root has no key file and IndexNow would reject every submission.
    assert (
        captured["body"]["keyLocation"]
        == f"https://shop.example/api/v1/seo/indexnow/{'a' * 32}.txt"
    )
    assert captured["body"]["urlList"] == ["https://shop.example/blog/x"]


def test_key_location_matches_the_registered_route():
    """The advertised keyLocation must equal the path FastAPI registers.

    A drift between the two (e.g. root vs /api/v1/seo/...) means IndexNow's
    verifier fetches a 404 and silently rejects submissions — this test is
    the cross-check the mock-transport tests cannot provide.
    """
    from app.main import app
    from fastapi.routing import APIRoute

    registered = [
        r.path for r in app.routes if isinstance(r, APIRoute) and "indexnow" in r.path
    ]
    # The public router path (legacy alias excluded — same handler).
    canonical = next(p for p in registered if p.startswith("/api/v1/"))
    assert canonical == idx.KEY_FILE_PATH_TEMPLATE, (
        f"KEY_FILE_PATH_TEMPLATE ({idx.KEY_FILE_PATH_TEMPLATE}) does not match "
        f"the registered route ({canonical}) — IndexNow would fetch a 404."
    )


@pytest.mark.asyncio
async def test_rate_limited_reported_not_error(patched, monkeypatch):
    patched({"indexnow_enabled": "1", "indexnow_key": "b" * 32})
    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(transport=_transport(lambda r: httpx.Response(429)), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    result = await idx.submit_urls(None, ["https://shop.example/x"])
    assert result["status"] == "rate_limited"
    assert result["submitted"] == 0


@pytest.mark.asyncio
async def test_rejected_reports_body(patched, monkeypatch):
    patched({"indexnow_enabled": "1", "indexnow_key": "c" * 32})
    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(
            transport=_transport(lambda r: httpx.Response(422, text="key mismatch")), **kw
        )

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    result = await idx.submit_urls(None, ["https://shop.example/x"])
    assert result["status"] == "rejected"
    assert "key mismatch" in result["reason"]


@pytest.mark.asyncio
async def test_transport_failure_never_raises(patched, monkeypatch):
    patched({"indexnow_enabled": "1", "indexnow_key": "d" * 32})

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(transport=_transport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    result = await idx.submit_urls(None, ["https://shop.example/x"])
    assert result["status"] == "error"
    assert result["submitted"] == 0


@pytest.mark.asyncio
async def test_empty_urls_skipped(patched):
    patched({"indexnow_enabled": "1"})
    result = await idx.submit_urls(None, [])
    assert result["status"] == "skipped"
    assert result["reason"] == "no_urls"


@pytest.mark.asyncio
async def test_key_generated_once_and_reused(patched):
    stub = patched({})
    key1 = await idx.get_or_create_key(None)
    key2 = await idx.get_or_create_key(None)
    assert key1 == key2
    assert len(key1) == 32
    # stored exactly once
    assert sum(1 for k, _ in stub.set_calls if k == idx.KEY_OPTION) == 1


@pytest.mark.asyncio
async def test_url_cap_enforced(patched, monkeypatch):
    patched({"indexnow_enabled": "1", "indexnow_key": "e" * 32})
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["count"] = len(json.loads(request.content)["urlList"])
        return httpx.Response(200)

    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(transport=_transport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    urls = [f"https://shop.example/p/{i}" for i in range(idx.MAX_URLS_PER_REQUEST + 50)]
    result = await idx.submit_urls(None, urls)
    assert result["submitted"] == idx.MAX_URLS_PER_REQUEST
    assert captured["count"] == idx.MAX_URLS_PER_REQUEST


@pytest.mark.asyncio
async def test_google_status_not_connected_without_credentials(patched):
    patched({})
    status = await idx.google_status(None)
    assert status["connected"] is False
    assert "service account" in status["note"] or "حساب سرویس" in status["note"]


@pytest.mark.asyncio
async def test_google_status_connected_with_credentials(patched):
    patched({"google_indexing_credentials": "{}"})
    status = await idx.google_status(None)
    assert status["connected"] is True


def test_no_google_request_code_path():
    """The module must not contain a hardcoded Google API call — the skeleton
    is a status read, and a credential-less request would fail silently."""
    import inspect

    source = inspect.getsource(idx)
    assert "indexing.googleapis.com" not in source
    assert "googleapis.com/v3/urlNotifications" not in source
