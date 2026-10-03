"""oEmbed discovery: a page's own endpoint is followed, safely.

P2 "فید: بدون کش نتیجه‌ی oEmbed و پروکسی عمومی برای هر نشانی". The cache half
was already shipped; this covers the discovery half — a page that advertises
its own oEmbed endpoint gets a real embed instead of a link card, which is
what makes any self-hosted CMS work rather than only the thirteen known
providers.

The second hop is a second SSRF surface: the endpoint URL comes out of HTML
the far end controls. The load-bearing test here is #2 — a discovery tag
pointing at the cloud metadata address must be refused, and refused quietly
(the page itself was public and still deserves its OG card).

No real network: ``httpx.AsyncClient`` is monkeypatched so the test controls
every response. A test that reaches YouTube is flaky and untestable offline.

Run:  python .p1-tests/oembed_discovery_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from app.modules.content.application import embed_service

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


#: Pages the fake fetcher knows, keyed by URL.
PAGES: dict[str, str] = {
    "https://blog.example/post": (
        '<html><head><title>Blog post</title>'
        '<meta property="og:title" content="OG title">'
        '<link rel="alternate" type="application/json+oembed" '
        'href="https://blog.example/wp-json/oembed/1.0/embed?url=post">'
        "</head><body>hi</body></html>"
    ),
    "https://plain.example/post": (
        '<html><head><title>Plain</title>'
        '<meta property="og:title" content="Plain OG">'
        "</head></html>"
    ),
    "https://evil.example/post": (
        '<html><head><title>Evil</title>'
        '<link rel="alternate" type="application/json+oembed" '
        'href="http://169.254.169.254/latest/meta-data/">'
        "</head></html>"
    ),
    "https://broken.example/post": (
        '<html><head><title>Broken</title>'
        '<meta property="og:title" content="Broken OG">'
        '<link rel="alternate" type="application/json+oembed" '
        'href="https://broken.example/oembed">'
        "</head></html>"
    ),
}

#: oEmbed endpoint answers, keyed by URL.
ENDPOINTS: dict[str, tuple[int, dict]] = {
    "https://blog.example/wp-json/oembed/1.0/embed?url=post": (
        200,
        {
            "type": "rich",
            "title": "Embedded post",
            "html": '<iframe src="https://blog.example/embed/post"></iframe>',
            "width": 600,
            "height": 400,
        },
    ),
    "https://broken.example/oembed": (500, {}),
}


class FakeResponse:
    def __init__(self, status_code: int, text: str = "", json_data: dict | None = None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


#: Every URL the fake client was asked to fetch, in order. The SSRF test
#: asserts against this — "was the metadata URL ever requested" — rather than
#: against the outcome, because a fake that simply 404s an unguarded fetch
#: produces the same fallback the guard produces, and the test would pass
#: while the hole was open. (It did, the first time this was written.)
FETCHED: list[str] = []


class FakeClient:
    """Stands in for httpx.AsyncClient; resolves from PAGES/ENDPOINTS."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        FETCHED.append(str(url))
        if url in PAGES:
            return FakeResponse(200, text=PAGES[url])
        if url in ENDPOINTS:
            status, payload = ENDPOINTS[url]
            return FakeResponse(status, json_data=payload)
        return FakeResponse(404, text="not found")


async def main() -> int:
    # Monkeypatch httpx.AsyncClient inside the module's namespace.
    import httpx
    import ipaddress as _ip

    from app.core.security import url_guard

    real_client = httpx.AsyncClient
    real_addresses_for = url_guard._addresses_for

    async def fake_addresses_for(host: str):
        # Every fake name resolves to a public address, so the SSRF guard's
        # DNS check passes for the pages under test. The metadata case needs
        # no patch: 169.254.169.254 is an IP literal, which the guard vets
        # directly and refuses — exactly the path the SSRF test exercises.
        return [_ip.ip_address("93.184.216.34")]

    httpx.AsyncClient = FakeClient  # type: ignore[assignment]
    url_guard._addresses_for = fake_addresses_for  # type: ignore[assignment]
    try:
        # 1. Happy path: discovery found, endpoint answers → rich, not OG.
        result = await embed_service.resolve_embed(
            "https://blog.example/post", use_cache=False
        )
        check("1. a page with a working discovery link yields a rich embed",
              result.get("provider") == "discovery" and result.get("type") == "rich",
              f"result={ {k: result.get(k) for k in ('provider','type','title')} }")
        check("1b. the embed HTML comes from the discovered endpoint",
              "blog.example/embed/post" in (result.get("html") or ""),
              f"html={result.get('html')!r}")

        # 2. SSRF: the discovery tag points at the metadata service. The
        #    load-bearing assertion is that the URL was NEVER FETCHED — not
        #    that the result fell back, because an unguarded fetch of a
        #    non-existent metadata URL also falls back. (The first version of
        #    this test asserted the outcome and passed while the guard was
        #    removed; it is the recorded fetch list that catches it.)
        FETCHED.clear()
        result = await embed_service.resolve_embed(
            "https://evil.example/post", use_cache=False
        )
        check("2. the metadata URL was never fetched",
              not any("169.254.169.254" in u for u in FETCHED),
              f"fetched={FETCHED}")
        check("2b. and the page still embeds as its OG card",
              result.get("title") == "Evil" and result.get("type") == "link",
              f"result={ {k: result.get(k) for k in ('type','title')} }")

        # 3. Fallback: discovery tag present but the endpoint 500s → OG card.
        result = await embed_service.resolve_embed(
            "https://broken.example/post", use_cache=False
        )
        check("3. a broken discovered endpoint falls back to the OG card",
              result.get("type") == "link" and result.get("title") == "Broken OG",
              f"result={ {k: result.get(k) for k in ('type','title')} }")

        # 4. A page with no discovery tag is unchanged (OG as before).
        result = await embed_service.resolve_embed(
            "https://plain.example/post", use_cache=False
        )
        check("4. a page with no discovery tag still yields its OG card",
              result.get("type") == "link" and result.get("title") == "Plain OG",
              f"result={ {k: result.get(k) for k in ('type','title')} }")
    finally:
        httpx.AsyncClient = real_client  # type: ignore[assignment]
        url_guard._addresses_for = real_addresses_for  # type: ignore[assignment]

    if bad:
        print("\nOEMBED DISCOVERY GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: oEmbed discovery follows a page's own endpoint, refuses an "
          "internal target, and falls back to OG on every failure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))