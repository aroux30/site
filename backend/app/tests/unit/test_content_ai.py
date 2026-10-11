"""Tests for Content AI — honest skeleton around a configurable LLM.

Rules pinned:

- **No key → no request.** The refusal happens before any HTTP call, so a
  credential-less setup cannot fire a doomed request.
- The suggestion is length-clamped (a chatty model must not produce a
  400-char "description") and trimmed.
- A rejected/error response returns status + reason, never raises.
- The key is never echoed back in the status payload.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.modules.seo.application import content_ai_service as ai


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


def _patch_client(monkeypatch, handler) -> None:
    real_client = httpx.AsyncClient

    def factory(**kw):
        kw.pop("transport", None)
        return real_client(transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_no_key_makes_no_request(patched, monkeypatch):
    patched({})
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200)

    _patch_client(monkeypatch, handler)
    result = await ai.generate_meta_suggestion(None, title="x", content="y")
    assert result["status"] == "not_connected"
    assert result["suggestion"] is None
    assert called is False, "no key must mean no HTTP request"


@pytest.mark.asyncio
async def test_successful_generation(patched, monkeypatch):
    patched({"content_ai_api_key": "sk-test"})

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == ai.DEFAULT_MODEL
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  یک توضیح خوب فارسی  "}}]},
        )

    _patch_client(monkeypatch, handler)
    result = await ai.generate_meta_suggestion(None, title="x", content="y")
    assert result["status"] == "ok"
    assert result["suggestion"] == "یک توضیح خوب فارسی"  # trimmed


@pytest.mark.asyncio
async def test_suggestion_length_clamped(patched, monkeypatch):
    patched({"content_ai_api_key": "sk-test"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ط" * 500}}]}
        )

    _patch_client(monkeypatch, handler)
    result = await ai.generate_meta_suggestion(None, title="x", content="y", kind="description")
    assert len(result["suggestion"]) == 160

    result_title = await ai.generate_meta_suggestion(
        None, title="x", content="y", kind="title"
    )
    assert len(result_title["suggestion"]) == 60


@pytest.mark.asyncio
async def test_rejected_response_reported(patched, monkeypatch):
    patched({"content_ai_api_key": "sk-test"})
    _patch_client(monkeypatch, lambda r: httpx.Response(401, text="bad key"))
    result = await ai.generate_meta_suggestion(None, title="x", content="y")
    assert result["status"] == "rejected"
    assert "401" in result["reason"]


@pytest.mark.asyncio
async def test_malformed_response_reported(patched, monkeypatch):
    patched({"content_ai_api_key": "sk-test"})
    _patch_client(monkeypatch, lambda r: httpx.Response(200, json={"nope": True}))
    result = await ai.generate_meta_suggestion(None, title="x", content="y")
    assert result["status"] == "error"
    assert result["suggestion"] is None


@pytest.mark.asyncio
async def test_transport_failure_never_raises(patched, monkeypatch):
    patched({"content_ai_api_key": "sk-test"})

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    _patch_client(monkeypatch, handler)
    result = await ai.generate_meta_suggestion(None, title="x", content="y")
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_status_never_echoes_key(patched):
    patched({"content_ai_api_key": "sk-secret-value"})
    result = await ai.status(None)
    assert result["connected"] is True
    assert "sk-secret-value" not in json.dumps(result)


@pytest.mark.asyncio
async def test_custom_base_url_and_model_used(patched, monkeypatch):
    patched(
        {
            "content_ai_api_key": "sk-test",
            "content_ai_base_url": "https://gateway.internal/v1",
            "content_ai_model": "custom-model",
        }
    )
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    _patch_client(monkeypatch, handler)
    await ai.generate_meta_suggestion(None, title="x", content="y")
    assert captured["url"] == "https://gateway.internal/v1/chat/completions"
    assert captured["model"] == "custom-model"
