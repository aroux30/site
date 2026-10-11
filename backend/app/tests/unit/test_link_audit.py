"""Broken-link crawler: classification, robots, SSRF, re-check window.

Rank Math Pro's Link Genius "Audit" crawler (owner request 2026-10-11). The
pieces pinned here:

* status → category mapping (2xx ok, 3xx redirect, 4xx/5xx broken),
* the robots.txt parser (longest-match, Allow beats Disallow on a tie),
* the SSRF guard: a URL pointing at an internal address is recorded ``blocked``
  and the HTTP client is **never called** (the assertion that matters),
* the 24h re-check window (a URL checked recently is skipped unless forced).

The fetch tests use ``httpx.MockTransport`` so they exercise the real
classification code without touching the network.
"""

from __future__ import annotations

import httpx
import pytest


def test_category_for_status():
    from app.modules.seo.application import link_audit_service as las

    assert las._category_for_status(200) == "ok"
    assert las._category_for_status(204) == "ok"
    assert las._category_for_status(301) == "redirect"
    assert las._category_for_status(404) == "broken"
    assert las._category_for_status(500) == "broken"
    assert las._category_for_status(410) == "broken"


def test_same_host():
    """Hostnames only: a relative Location has no host and is handled by the
    `location.startswith("/")` branch in `_fetch_one`, not here."""
    from app.modules.seo.application import link_audit_service as las

    assert las._same_host("https://a.com/x", "https://a.com/y")
    assert not las._same_host("https://a.com/x", "https://b.com/y")
    assert not las._same_host("https://a.com/x", "/y")


# ── robots.txt parser ───────────────────────────────────────────────────────


def test_robots_allows_when_empty():
    from app.modules.seo.application import link_audit_service as las

    assert las._robots_allows("", "/anything") is True


def test_robots_disallow_blocks_path():
    from app.modules.seo.application import link_audit_service as las

    robots = "User-agent: *\nDisallow: /private/"
    assert las._robots_allows(robots, "/private/x") is False
    assert las._robots_allows(robots, "/public/x") is True


def test_robots_allow_beats_disallow_on_tie():
    """Longest-match wins; on an equal-length tie Allow wins (Google's rule)."""
    from app.modules.seo.application import link_audit_service as las

    robots = "User-agent: *\nDisallow: /a\nAllow: /a\n"
    assert las._robots_allows(robots, "/a") is True


def test_robots_longer_match_wins():
    from app.modules.seo.application import link_audit_service as las

    # A longer Disallow overrides a shorter Allow.
    robots = "User-agent: *\nAllow: /a\nDisallow: /a/secret\n"
    assert las._robots_allows(robots, "/a/secret/x") is False
    assert las._robots_allows(robots, "/a/public") is True


def test_robots_specific_agent_group_wins_over_star():
    from app.modules.seo.application import link_audit_service as las

    robots = (
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: ArouxShop-LinkAudit\nDisallow: /only-me\n"
    )
    # Our specific group is matched, not the blanket "*".
    assert las._robots_allows(robots, "/ok", user_agent="arouxshop-linkaudit/1.0") is True
    assert las._robots_allows(robots, "/only-me", user_agent="arouxshop-linkaudit/1.0") is False


def test_robots_empty_disallow_means_allow_all():
    from app.modules.seo.application import link_audit_service as las

    assert las._robots_allows("User-agent: *\nDisallow:", "/x") is True


# ── fetch classification (MockTransport) ────────────────────────────────────


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)


async def test_fetch_ok():
    from app.modules.seo.application import link_audit_service as las

    async with _client(lambda r: httpx.Response(200)) as c:
        result = await las._fetch_one(c, "https://example.com/page")
    assert result.category == "ok"
    assert result.http_status == 200


async def test_fetch_broken():
    from app.modules.seo.application import link_audit_service as las

    async with _client(lambda r: httpx.Response(404)) as c:
        result = await las._fetch_one(c, "https://example.com/gone")
    assert result.category == "broken"
    assert result.http_status == 404


async def test_fetch_redirect_offhost_flagged():
    from app.modules.seo.application import link_audit_service as las

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"location": "https://other.com/x"})

    async with _client(handler) as c:
        result = await las._fetch_one(c, "https://example.com/page")
    assert result.category == "redirect"
    assert result.http_status == 301
    assert result.detail and "دامنهٔ دیگر" in result.detail


async def test_fetch_timeout():
    from app.modules.seo.application import link_audit_service as las

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    async with _client(handler) as c:
        result = await las._fetch_one(c, "https://example.com/slow")
    assert result.category == "timeout"


async def test_fetch_connect_error():
    from app.modules.seo.application import link_audit_service as las

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    async with _client(handler) as c:
        result = await las._fetch_one(c, "https://example.com/x")
    assert result.category == "error"


# ── SSRF: the guard must stop the fetch BEFORE it goes out ──────────────────


async def test_ssrf_internal_url_never_fetched():
    """A URL pointing at an internal address is recorded ``blocked`` and the
    HTTP client is NEVER called.

    Negative test (the assertion that matters): if the guard were removed, the
    handler below would run and the test would fail on `called` — proving the
    request left. The check is "never fetched", not "returned an error".
    """
    from app.modules.seo.application import link_audit_service as las

    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200)

    async with _client(handler) as c:
        result = await las._fetch_one(c, "http://169.254.169.254/latest/meta-data/")
        result2 = await las._fetch_one(c, "http://127.0.0.1/admin")
        result3 = await las._fetch_one(c, "http://localhost/x")

    assert result.category == "blocked"
    assert result2.category == "blocked"
    assert result3.category == "blocked"
    assert called["n"] == 0, "the SSRF guard let a request reach the network"


async def test_ssrf_decimal_and_hex_loopback_blocked():
    """The guard resolves names; decimal/hex loopback forms must not slip past."""
    from app.modules.seo.application import link_audit_service as las

    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200)

    async with _client(handler) as c:
        # `2130706433` and `0x7f.0.0.1` both resolve to 127.0.0.1 on libc.
        r1 = await las._fetch_one(c, "http://2130706433/")
        r2 = await las._fetch_one(c, "http://0x7f.0.0.1/")
    # Either blocked (guard caught it) or, if the resolver rejects it, error —
    # but NEVER fetched.
    assert r1.category in ("blocked", "error")
    assert r2.category in ("blocked", "error")
    assert called["n"] == 0


# ── Re-check window ─────────────────────────────────────────────────────────


async def test_recent_hashes_skip_window():
    """A URL checked inside the window is in the skip set; an old one is not."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from app.core.database.session import async_session_factory, engine
    from app.modules.seo.application import link_audit_service as las
    from app.modules.seo.domain.link_models import SeoLinkAudit

    fresh_hash = "f" * 32
    old_hash = "0" * 32
    async with async_session_factory() as db:
        try:
            await las._upsert(
                db,
                las.AuditResult("https://fresh.example/", fresh_hash, 200, "ok", None),
                datetime.now(UTC),
                safe=False,
            )
            await las._upsert(
                db,
                las.AuditResult("https://old.example/", old_hash, 200, "ok", None),
                datetime.now(UTC) - timedelta(hours=48),
                safe=False,
            )
            await db.commit()
            recent = await las._recent_hashes(db)
            assert fresh_hash in recent
            assert old_hash not in recent
        finally:
            await db.execute(
                delete(SeoLinkAudit).where(SeoLinkAudit.url_hash.in_([fresh_hash, old_hash]))
            )
            await db.commit()
    await engine.dispose()


async def test_mark_safe_roundtrip():
    from datetime import UTC, datetime

    from sqlalchemy import delete

    from app.core.database.session import async_session_factory, engine
    from app.modules.seo.application import link_audit_service as las
    from app.modules.seo.domain.link_models import SeoLinkAudit

    h = "a1" * 16
    async with async_session_factory() as db:
        try:
            await las._upsert(
                db,
                las.AuditResult("https://safe.example/", h, 403, "broken", "forbidden"),
                datetime.now(UTC),
                safe=False,
            )
            await db.commit()
            from sqlalchemy import select

            row = (
                await db.execute(select(SeoLinkAudit).where(SeoLinkAudit.url_hash == h))
            ).scalar_one()
            assert row.is_marked_safe is False
            ok = await las.mark_safe(db, row.id, True)
            assert ok is True
            await db.refresh(row)
            assert row.is_marked_safe is True
        finally:
            await db.execute(delete(SeoLinkAudit).where(SeoLinkAudit.url_hash == h))
            await db.commit()
    await engine.dispose()


async def test_upsert_preserves_safe_flag_on_recheck():
    """A re-check updates the status but must NOT clear `is_marked_safe`.

    Negative test: drop `is_marked_safe` from the preserved columns (i.e. let
    the insert value overwrite it) and a nightly re-check would resurrect a
    URL the operator silenced — the row comes back on every run.
    """
    from datetime import UTC, datetime

    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.seo.application import link_audit_service as las
    from app.modules.seo.domain.link_models import SeoLinkAudit

    h = "b2" * 16
    async with async_session_factory() as db:
        try:
            await las._upsert(
                db,
                las.AuditResult("https://resurrect.example/", h, 403, "broken", "x"),
                datetime.now(UTC),
                safe=True,  # operator marked it safe
            )
            await db.commit()
            # A later re-check passes safe=False (the operator's flag is read
            # from the DB by run_audit, but a direct _upsert with safe=False
            # must still not clear it).
            await las._upsert(
                db,
                las.AuditResult("https://resurrect.example/", h, 403, "broken", "y"),
                datetime.now(UTC),
                safe=False,
            )
            await db.commit()
            row = (
                await db.execute(select(SeoLinkAudit).where(SeoLinkAudit.url_hash == h))
            ).scalar_one()
            assert row.is_marked_safe is True, "re-check cleared the safe flag"
            assert row.detail == "y"  # but the status detail did update
        finally:
            await db.execute(delete(SeoLinkAudit).where(SeoLinkAudit.url_hash == h))
            await db.commit()
    await engine.dispose()


async def test_run_audit_over_mock_transport():
    """Full run: collect → robots → fetch → upsert, over a mock transport.

    Seeds one link row pointing at a 404 and one at a 200, runs the audit with
    the real httpx client swapped for a MockTransport, and asserts the two
    categories landed in the table. Cleans up.
    """
    import uuid as _uuid
    from datetime import UTC, datetime

    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.seo.application import link_audit_service as las
    from app.modules.seo.domain.link_models import SeoInternalLink, SeoLinkAudit
    from app.modules.users.domain.models import User

    good = f"https://good-{_uuid.uuid4().hex[:8]}.example/page"
    bad = f"https://bad-{_uuid.uuid4().hex[:8]}.example/gone"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.path.endswith("/gone"):
            return httpx.Response(404)
        return httpx.Response(200)

    async with async_session_factory() as db:
        author = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        assert author is not None
        post = BlogPost(
            author_id=author.id,
            title="audit test",
            slug=f"pytest-audit-{_uuid.uuid4().hex[:8]}",
            content="x",
            status=BlogPostStatus.PUBLISHED,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        # Two link rows the collector will pick up.
        for url in (good, bad):
            db.add(
                SeoInternalLink(
                    post_id=post.id,
                    url=url,
                    url_hash=las._hash(url),
                    anchor_text="x",
                    link_type="external",
                )
            )
        await db.commit()

        real_client = httpx.AsyncClient

        def factory(**kw):
            kw.pop("transport", None)
            return real_client(transport=httpx.MockTransport(handler), **kw)

        # DNS resolution is environment-dependent (and `.example` never
        # resolves), so the guard is passed through here — this test covers the
        # classification + persistence flow, and the SSRF guard has its own
        # dedicated tests above. Both hosts are forced to resolve by the
        # passthrough, which returns the URL unchanged.
        async def _passthrough(url: str, *, what: str = "نشانی"):
            from urllib.parse import urlparse

            return url, urlparse(url).hostname or ""

        orig_guard = las.validate_pinned_url
        orig_client = httpx.AsyncClient
        las.validate_pinned_url = _passthrough  # type: ignore[assignment]
        httpx.AsyncClient = factory  # type: ignore[assignment]
        try:
            await las.run_audit(db, batch_size=50, force=True)
        finally:
            httpx.AsyncClient = orig_client  # type: ignore[assignment]
            las.validate_pinned_url = orig_guard  # type: ignore[assignment]

        rows = {
            r.url: r
            for r in (
                await db.execute(
                    select(SeoLinkAudit).where(SeoLinkAudit.url.in_([good, bad]))
                )
            ).scalars().all()
        }
        assert rows[good].category == "ok"
        assert rows[bad].category == "broken"
        await db.execute(
            delete(SeoInternalLink).where(SeoInternalLink.post_id == post.id)
        )
        await db.execute(delete(SeoLinkAudit).where(SeoLinkAudit.url.in_([good, bad])))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()
    await engine.dispose()
