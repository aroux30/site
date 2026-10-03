"""The oEmbed channel list covers the common providers, and a tokenless one
falls back instead of 400ing.

P1 "فید: فهرست کانال‌های oEmbed". Four providers shipped (YouTube, Aparat,
Twitter, Instagram) against WordPress's ~34. The gap is invisible until
someone pastes a Vimeo link into the editor and gets a bare link card where
every other platform gives an embed.

Two things are checked, and the second is the one that bites:

  * the provider list grew, and each pattern matches its own URLs and not
    another provider's;
  * a provider with no usable endpoint (Facebook needs an app token) falls
    through to the Open Graph card rather than being sent to an endpoint that
    answers 400 — a named miss, not a broken embed.

    python scripts/wp-parity/check_oembed_channels.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent; a plain TextIOWrapper
# here is closed by any later module that wraps stdout.

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


#: URLs that must resolve to a named provider, and their provider.
EXPECTED = [
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://www.aparat.com/v/xyz", "aparat"),
    ("https://twitter.com/user/status/1", "twitter"),
    ("https://x.com/user/status/1", "twitter"),
    ("https://www.instagram.com/p/abc/", "instagram"),
    ("https://vimeo.com/123456789", "vimeo"),
    ("https://www.dailymotion.com/video/x8abc", "dailymotion"),
    ("https://soundcloud.com/artist/track", "soundcloud"),
    ("https://open.spotify.com/track/abc", "spotify"),
    ("https://www.flickr.com/photos/user/12345", "flickr"),
    ("https://www.tumblr.com/blog/123456", "tumblr"),
    ("https://www.reddit.com/r/python/comments/abc/x", "reddit"),
    ("https://wordpress.tv/2024/01/talk/", "wordpress-tv"),
    ("https://www.facebook.com/page/videos/123", "facebook"),
]

#: URLs that must NOT match any provider (they fall through to OG).
NOT_MATCHED = [
    "https://example.com/article",
    "https://vimeo.com/notavideo",  # no numeric id
]


def main() -> int:
    from app.modules.content.application.embed_service import _OEMBED_PROVIDERS

    check("the provider list grew past the original four",
          len(_OEMBED_PROVIDERS) >= 13, f"{len(_OEMBED_PROVIDERS)} providers")

    for url, expected in EXPECTED:
        got = None
        for pattern, provider, _tpl in _OEMBED_PROVIDERS:
            if pattern.match(url):
                got = provider
                break
        check(f"{url[:44]} -> {expected}", got == expected,
              f"got {got!r}")

    for url in NOT_MATCHED:
        got = None
        for pattern, provider, _tpl in _OEMBED_PROVIDERS:
            if pattern.match(url):
                got = provider
                break
        check(f"{url[:44]} falls through", got is None, f"matched {got!r}")

    # The tokenless-provider branch: facebook must be listed with an empty
    # endpoint template, and the resolver must skip the fetch for it.
    fb = [p for p in _OEMBED_PROVIDERS if p[1] == "facebook"]
    check("facebook is listed with no endpoint template",
          len(fb) == 1 and fb[0][2] == "",
          "facebook has an endpoint it cannot call without a token")

    source = open(os.path.join(
        ROOT, "backend", "app", "modules", "content", "application", "embed_service.py"
    ), encoding="utf-8").read()
    check("the resolver skips the fetch for an endpoint-less provider",
          "if not endpoint_tpl:" in source,
          "an empty endpoint would be GET-ed and 400")

    # The configurable half: cache window and host allowlist. Both were
    # constants the operator could not touch.
    check("the cache window reads a site option",
          "_cache_ttl_seconds" in source and "embed_cache_ttl_hours" in source,
          "the TTL is still a module constant")
    check("the allowlist reads a site option",
          "_allowed_hosts" in source and "embed_allowed_hosts" in source,
          "there is no host allowlist")
    check("the allowlist does not replace the SSRF guard",
          "validate_public_url" in source and "_allowed_hosts(db)" in source,
          "the allowlist must sit after the SSRF guard, never instead of it")

    # Behaviour of the pure matcher: subdomains yes, lookalikes no.
    from app.modules.content.application.embed_service import _host_matches

    allowed = {"youtube.com", "aparat.com"}
    check("a subdomain matches its listed domain",
          _host_matches("www.youtube.com", allowed)
          and _host_matches("m.youtube.com", allowed))
    check("a lookalike domain does not match",
          not _host_matches("notyoutube.com", allowed)
          and not _host_matches("youtube.com.evil.example", allowed))
    check("an unlisted host does not match",
          not _host_matches("vimeo.com", allowed))

    # The options are seeded, or the reads fall back to defaults silently.
    seeds = open(os.path.join(
        ROOT, "backend", "app", "modules", "settings", "application", "default_options.py"
    ), encoding="utf-8").read()
    check("both options are seeded",
          "embed_cache_ttl_hours" in seeds and "embed_allowed_hosts" in seeds,
          "an option with no seed row reads as its fallback forever")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the oEmbed list covers the common providers, a tokenless one "
          "falls back rather than 400ing, and the cache window and host "
          "allowlist are configurable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())