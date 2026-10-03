"""oEmbed discovery: follows a page's own endpoint, and never inward.

    python scripts/wp-parity/check_oembed_discovery_ssrf.py

P2 "پروکسی عمومی برای هر نشانی" — the second half, after the cache. A page
that advertises its own oEmbed endpoint gets a real embed instead of a link
card, which is what makes any self-hosted CMS work rather than only the
thirteen known providers.

The gate exists mostly for ONE property: the discovered URL is a **second
SSRF surface** — it comes out of HTML the far end controls. A page can put
``http://169.254.169.254/…`` in its discovery tag, and without a guard on that
hop the server fetches its own metadata service. A gate that only checked the
happy path would miss exactly the version that ships that hole.

Scope note: the *fetch* of the discovered endpoint is what must be guarded;
extraction (a pure regex over fetched HTML) is checked for shape here.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root() -> str:
    d = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".p1-tests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.normpath(os.path.join(HERE, "..", ".."))


ROOT = _repo_root()
FIXTURE = os.path.join(ROOT, ".p1-tests", "oembed_discovery_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "content", "application", "embed_service.py"
)
CHECK_LINE = re.compile(r"^\d+\.")


def _run_fixture(path: str) -> int:
    try:
        proc = subprocess.run(
            [sys.executable, "-B", path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"  {os.path.basename(path)}: timed out")
        return 1
    for ln in (proc.stdout or "").splitlines():
        if CHECK_LINE.match(ln.strip()):
            print(f"     {ln.strip()}")
    return proc.returncode


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else detail)

    src = open(SERVICE, encoding="utf-8").read() if os.path.isfile(SERVICE) else ""

    # ── Extraction ───────────────────────────────────────────────────────────
    check("a discovery extractor exists",
          "def extract_oembed_discovery" in src,
          "no extractor")
    # The regex itself, not the whole file: the docstring legitimately
    # *mentions* text/xml+oembed to explain why it is excluded, and a
    # file-wide (or too-wide) slice would read that prose as a match. The
    # slice ends at the flags line, which is the regex's own closing.
    #
    # The JSON type is matched in its *escaped* source form (``json\+oembed``):
    # inside a regex literal the ``+`` carries a backslash, so searching for
    # the unescaped spelling finds nothing and reports a false negative.
    regex_at = src.find("_DISCOVERY_JSON_RE = re.compile(")
    regex_end = src.find("re.IGNORECASE", regex_at) if regex_at != -1 else -1
    regex_block = src[regex_at:regex_end] if regex_at != -1 and regex_end != -1 else ""
    check("the extractor regex matches the JSON type only",
          bool(regex_block)
          and "json\\+oembed" in regex_block
          and "xml" not in regex_block.lower(),
          "the regex matches XML oEmbed, which needs a parser this does not have")
    # The regex must capture the href in BOTH attribute orders — pages in the
    # wild write it both ways, and matching one order silently misses half.
    check("both attribute orders are matched",
          src.count("href=[\"']") >= 2,
          "only one attribute order is handled")

    # ── THE load-bearing check: the second hop is guarded ────────────────────
    #
    # The discovered URL comes from remote HTML; it must go through the same
    # DNS-resolving guard the page fetch uses. The check looks for the guard
    # call *inside the discovery function*, not merely somewhere in the file —
    # the file has used the guard for the main fetch all along, and matching
    # the file would pass a version that forgot the second hop.
    fn_at = src.find("async def _try_oembed_discovery")
    fn_block = src[fn_at : src.find("\nasync def ", fn_at + 10)] if fn_at != -1 else ""
    check("the discovery function exists",
          fn_at != -1 and bool(fn_block), "no _try_oembed_discovery")
    check("the discovered endpoint goes through the SSRF guard",
          "validate_public_url(" in fn_block,
          "the second hop is fetched unguarded — a discovery tag could reach "
          "the metadata service")
    # The guard must run BEFORE the fetch, not after: a check that runs after
    # the request has already made the request.
    guard_at = fn_block.find("validate_public_url(")
    fetch_at = fn_block.find("client.get(")
    check("the guard runs before the fetch",
          guard_at != -1 and fetch_at != -1 and guard_at < fetch_at,
          "the endpoint is fetched before it is vetted")
    check("an inward tag is refused quietly, not raised",
          "oembed_discovery_internal_refused" in fn_block,
          "a refused discovery tag would fail the whole resolve instead of "
          "falling back to the OG card")

    # ── Fallback discipline: every failure returns None, never raises ────────
    check("discovery failures fall back instead of raising",
          fn_block.count("return None") >= 3,
          "a discovery failure path does not fall back to OG")

    # ── Wiring: the fallback block actually calls it, before OG ─────────────
    resolve_at = src.find("async def resolve_embed")
    resolve_block = src[resolve_at:] if resolve_at != -1 else ""
    disc_call = resolve_block.find("_try_oembed_discovery(")
    og_call = resolve_block.find("parse_og_tags(")
    check("the OG fallback consults discovery",
          disc_call != -1, "resolve_embed never calls the discovery path")
    check("discovery is consulted before OG",
          disc_call != -1 and og_call != -1 and disc_call < og_call,
          "OG is built first — a discoverable page would never get a real embed")
    check("a discovery result is cached like any other",
          "discovered is not None" in resolve_block
          and "_cache_put(url, discovered" in resolve_block,
          "discovered results bypass the cache")

    # ── Live behaviour (monkeypatched httpx; no real network) ───────────────
    if not os.path.isfile(FIXTURE):
        check("the discovery fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the discovery behaviour holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: a page's own oEmbed endpoint is followed for a real embed, "
          "the second hop is SSRF-guarded, and every failure falls back to OG.")
    return 0


if __name__ == "__main__":
    sys.exit(main())