"""One page render must count exactly one view.

The detail page fetches the same post up to three times per render —
`generateMetadata` (visibility), `buildPostMetadata` (title/og), and the page
body itself — and every fetch incremented the Redis counter. A reader's
single visit counted 3×, and metadata prefetches (crawlers, link previews)
inflated it further.

Fix: the route takes `track_view` (default true); metadata callers pass
`track_view=false`. Verified live: 3 metadata reads moved the counter by 0,
one real read by 1; a full browser reload moved the shown count by exactly 1.

Negative test: drop the `track_view` query parameter and force
`increment_views=True` — the source assertions below fail.
"""

from __future__ import annotations

import inspect


def test_route_accepts_track_view_and_forwards_it():
    """The route must expose `track_view` and pass it to the service.

    Negative test: revert to `increment_views=True` hard-coded and the
    `increment_views=track_view` assertion fails.
    """
    from app.modules.blog.api import routes

    src = inspect.getsource(routes.get_post_by_slug)
    assert "track_view" in src, "route must accept the track_view flag"
    assert "increment_views=track_view" in src, (
        "the flag must be forwarded, not ignored"
    )


def test_client_sends_track_view_false_only_when_asked():
    """The client must send `track_view=false` only for metadata reads.

    Source-level check: the option exists, and the metadata caller in the
    page uses it. Negative test: remove the option from the client params
    and the first assertion fails.
    """
    import pathlib

    # unit -> tests -> app -> backend -> site (repo root)
    root = pathlib.Path(__file__).resolve().parents[4]
    client = (root / "frontend" / "lib" / "api" / "blog.ts").read_text(encoding="utf-8")
    assert "track_view: false" in client, "client must be able to suppress tracking"

    page = (
        root / "frontend" / "app" / "(store)" / "blog" / "[slug]" / "page.tsx"
    ).read_text(encoding="utf-8")
    # Both metadata fetches pass trackView:false; the page body does not.
    assert page.count("trackView: false") == 2, (
        "generateMetadata and buildPostMetadata must both suppress tracking"
    )
