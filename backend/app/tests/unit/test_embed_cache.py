"""Tests for the oEmbed result cache.

Resolving an embed is an outbound request to a third party, done once for the
preview and again for the published page, often for the same URL across several
pages. The cache has to be fail-open in both directions: a Redis outage must
slow an embed down, never break the page that embeds it.

The key is hashed. A raw URL can carry a token in its query string, and cache
keys end up in memory dumps and slow logs.
"""

from __future__ import annotations

import json

import pytest

import app.modules.content.application.embed_service as es


# ------------------------------------------------------------- the key


def test_the_key_is_not_the_raw_url():
    key = es._cache_key("https://example.com/v/abc?token=SECRET")
    assert "SECRET" not in key
    assert "example.com" not in key


def test_the_key_is_stable():
    a = es._cache_key("https://example.com/x")
    b = es._cache_key("https://example.com/x")
    assert a == b


def test_different_urls_get_different_keys():
    assert es._cache_key("https://example.com/a") != es._cache_key(
        "https://example.com/b"
    )


def test_the_key_is_versioned():
    # So a change to the cached shape cannot serve old payloads into new code.
    assert es._cache_key("https://example.com").startswith("embed:v1:")


# ------------------------------------------------------------- the TTLs


def test_a_successful_embed_is_cached_for_a_week():
    assert es.EMBED_CACHE_TTL_SECONDS == 7 * 24 * 3600


def test_a_failure_is_cached_briefly():
    # A URL that failed is usually a provider hiccup. Caching it for a week
    # would make one bad response permanent in the page's markup.
    assert es.EMBED_NEGATIVE_TTL_SECONDS < 3600
    assert es.EMBED_NEGATIVE_TTL_SECONDS < es.EMBED_CACHE_TTL_SECONDS


# ------------------------------------------------------------- the reads


class _FakeRedis:
    def __init__(self, value=None, fail=False):
        self.value = value
        self.fail = fail
        self.writes: list[tuple[str, str, int]] = []

    async def get(self, key):
        if self.fail:
            raise RuntimeError("redis is down")
        return self.value

    async def set(self, key, value, ex=None):
        if self.fail:
            raise RuntimeError("redis is down")
        self.writes.append((key, value, ex))


@pytest.fixture
def fake_redis(monkeypatch):
    def _install(redis):
        async def _get_redis():
            return redis

        monkeypatch.setattr("app.core.cache.redis.get_redis", _get_redis)
        return redis

    return _install


@pytest.mark.asyncio
async def test_a_cached_result_is_returned(fake_redis):
    payload = {"type": "rich", "html": "<iframe>", "title": "t"}
    fake_redis(_FakeRedis(value=json.dumps(payload)))
    assert await es._cache_get("https://example.com/v/1") == payload


@pytest.mark.asyncio
async def test_a_miss_is_none(fake_redis):
    fake_redis(_FakeRedis(value=None))
    assert await es._cache_get("https://example.com/v/1") is None


@pytest.mark.asyncio
async def test_a_corrupt_cached_value_is_a_miss(fake_redis):
    # A payload from an older shape, or a truncated write, must not raise in
    # front of the editor.
    fake_redis(_FakeRedis(value="{not json"))
    assert await es._cache_get("https://example.com/v/1") is None


@pytest.mark.asyncio
async def test_a_cached_payload_without_a_type_is_a_miss(fake_redis):
    # "type" is what every consumer branches on; without it the value is not a
    # result this function produced.
    fake_redis(_FakeRedis(value=json.dumps({"html": "<iframe>"})))
    assert await es._cache_get("https://example.com/v/1") is None


@pytest.mark.asyncio
async def test_a_json_array_is_a_miss(fake_redis):
    fake_redis(_FakeRedis(value=json.dumps([1, 2, 3])))
    assert await es._cache_get("https://example.com/v/1") is None


# ------------------------------------------------------------- the writes


@pytest.mark.asyncio
async def test_a_rich_result_gets_the_long_ttl(fake_redis):
    redis = _FakeRedis()
    fake_redis(redis)
    await es._cache_put("https://example.com/v/1", {"type": "rich", "html": "<i>"})
    assert redis.writes[0][2] == es.EMBED_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_a_result_without_html_gets_the_short_ttl(fake_redis):
    redis = _FakeRedis()
    fake_redis(redis)
    # A link card, or a provider that resolved with no embed markup: it can
    # still change, so it does not get a week's lease.
    await es._cache_put("https://example.com", {"type": "link", "title": "t"})
    assert redis.writes[0][2] == es.EMBED_NEGATIVE_TTL_SECONDS


@pytest.mark.asyncio
async def test_an_oversized_payload_is_not_cached(fake_redis):
    # A provider returning a whole page instead of oEmbed JSON would otherwise
    # put megabytes into Redis under a key that looks like every other embed.
    redis = _FakeRedis()
    fake_redis(redis)
    await es._cache_put(
        "https://example.com/v/1",
        {"type": "rich", "html": "x" * (es.EMBED_CACHE_MAX_BYTES + 1)},
    )
    assert redis.writes == []


@pytest.mark.asyncio
async def test_a_redis_outage_does_not_raise_on_write(fake_redis):
    fake_redis(_FakeRedis(fail=True))
    # The caller is building a page. An embed that cannot be cached is a slow
    # embed, not a broken one.
    await es._cache_put("https://example.com/v/1", {"type": "rich", "html": "<i>"})


@pytest.mark.asyncio
async def test_a_redis_outage_does_not_raise_on_read(fake_redis):
    fake_redis(_FakeRedis(fail=True))
    assert await es._cache_get("https://example.com/v/1") is None
