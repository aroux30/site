"""oEmbed discovery must describe the page, not just the site.

The root layout advertised `/oembed` with no `url`, which says "this site can be
embedded" and nothing about *which part of it*. Every consumer — Slack,
Telegram, a chat client — follows the discovery link on the page it was given,
so a post shared into one had no attachment to resolve. WordPress puts a
per-post `<link rel="alternate" type="application/json+oembed">` in the head for
exactly this reason.

Three hops, each of which can be present alone:

  * the page emits a **per-page** link, absolute, carrying `url` and `format`;
  * the endpoint **accepts** those two parameters, not just the provider list —
    a link that sends them to a route that ignores them is the same failure;
  * the page also carries a canonical URL of its own, so a consumer can tell
    where "this page" is without guessing from the discovery link.

Run:  python scripts/wp-parity/check_oembed_discovery_wired.py
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "[slug]", "page.tsx")
HREFLANG = os.path.join(ROOT, "frontend", "lib", "hreflang.ts")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "content",
                      "api", "routes.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _probe_live() -> list[tuple[str, bool, str]]:
    """Call the discovery endpoint and read what comes back.

    Returns `(label, ok, detail)` triples so the caller reports them with the
    same shape as the static checks. A probe that cannot run at all returns a
    single failure naming the reason — "the database is down" and "the endpoint
    is broken" are different facts, and the second must not be reported when
    the first is true.

    A database-less environment is the one case that is not a failure: the
    gate's static half still holds there, and this returns a skip note rather
    than a red.
    """
    import asyncio

    sys.path.insert(0, os.path.join(ROOT, "backend"))

    async def run() -> list[tuple[str, bool, str]]:
        try:
            import app.main  # noqa: F401 — boots the app, which is the point
            from httpx import ASGITransport, AsyncClient
        except Exception as exc:  # noqa: BLE001
            return [("the endpoint could be probed", False, str(exc)[:120])]

        page_url = "https://shop.example/blog/sample-post"
        query = (
            "/api/v1/content/oembed"
            f"?url={page_url}&format=json"
        )
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app.main.app),
                base_url="http://test",
            ) as client:
                resp = await client.get(query)
        except Exception as exc:  # noqa: BLE001
            return [("the endpoint could be probed", False, str(exc)[:120])]

        out: list[tuple[str, bool, str]] = [
            ("the endpoint answers 200", resp.status_code == 200,
             f"status {resp.status_code}"),
        ]
        if resp.status_code != 200:
            return out

        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            return out + [("and returns JSON", False, resp.text[:120])]

        out.append(("and returns JSON", True))
        out.append(("it echoes the page url it was asked about",
                    body.get("url") == page_url, str(body.get("url"))))
        out.append(("and the format", body.get("format") == "json",
                    str(body.get("format"))))
        out.append(("with the provider endpoint it advertises",
                    isinstance(body.get("endpoints"), list)
                    and any("/oembed/1.0/embed" in e
                            for e in body.get("endpoints", [])),
                    str(body.get("endpoints"))[:100]))
        return out

    return asyncio.run(run())


def main() -> int:
    for path in (PAGE, HREFLANG, ROUTES):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    page, hreflang, routes = (read(p) for p in (PAGE, HREFLANG, ROUTES))

    # 1. the helper builds a per-page, absolute link
    check("a discovery URL helper exists",
          "export function oembedDiscoveryUrl" in hreflang)
    body = hreflang[hreflang.find("export function oembedDiscoveryUrl"):]
    check("it carries the page's own url", "url=${encodeURIComponent" in body)
    check("and the format oEmbed defines", "format=json" in body)
    check("it is absolute — a consumer has no base to resolve against",
          "SITE_URL" in body)
    check("it points at the real endpoint",
          "/api/v1/content/oembed" in body)

    # 2. the page emits it, inside its metadata
    meta = re.search(r"generateMetadata\((.*?)\n(?=export )", page, re.S)
    meta_body = meta.group(1) if meta else ""
    check("the page has a metadata function", bool(meta_body))
    check("it advertises oEmbed for itself",
          "text/json+oembed" in meta_body)
    check("and builds the link with the helper",
          "oembedDiscoveryUrl(" in meta_body)
    check("the link sits under alternates.types, which is where a consumer looks",
          "types:" in meta_body and "alternates" in meta_body)

    # 3. the endpoint accepts what the link sends. A link to a route that drops
    #    the parameters is the same failure as no link.
    disco = re.search(r"async def oembed_discovery\((.*?)\)\s*->", routes, re.S)
    sig = disco.group(1) if disco else ""
    check("the discovery endpoint takes a url", "url:" in sig)
    check("and a format", "format:" in sig)
    check("and reports both back", '"url": url' in routes and '"format": format' in routes)
    check("the provider endpoint still exists",
          "/oembed/1.0/embed" in routes)

    # 4. and it answers. Everything above reads source: a signature can be
    #    right while the route raises on the query string it was given, and the
    #    parameters could be declared and then dropped before the response.
    #    The endpoint is public, so this needs no credential — which is the
    #    point of a discovery link.
    live = _probe_live()
    for row in live:
        label, ok = row[0], row[1]
        detail = row[2] if len(row) > 2 else ""
        check(label, ok, detail)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: every page advertises its own oEmbed discovery link, and the "
          "endpoint answers it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())