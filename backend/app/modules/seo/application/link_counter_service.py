"""Link counter — internal/external link counts and broken-link report.

Rank Math's Link Counter (the free plugin's module; PRO's "Link Genius"
extends it): count the links in every post's body, flag posts with no
internal links (orphans from the content side), and list every external link
so an operator can spot dead domains.

Counts are computed from the stored body on demand — no index table. The
scale here is a shop blog (thousands of posts, not millions), and a
materialized count would be one more thing to keep in sync on every edit;
a scan over the fetched page's bodies costs one query and stays correct by
construction.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

#: Anchor hrefs in stored HTML. The body is operator content (bleach-sanitized
#: on write), so a straightforward href extraction is the right shape — a full
#: HTML parser would add a dependency for one attribute.
_HREF = re.compile(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _classify(href: str, site_hosts: set[str]) -> str:
    """internal | external | anchor | other."""
    href = href.strip()
    if not href or href.startswith("#"):
        return "anchor"
    if href.startswith(("mailto:", "tel:", "javascript:")):
        return "other"
    if href.startswith(("/", "./", "../")) and not href.startswith("//"):
        return "internal"
    try:
        parsed = urlparse(href)
    except ValueError:
        return "other"
    host = (parsed.hostname or "").lower()
    if not host:
        return "other"
    if host in site_hosts:
        return "internal"
    return "external"


def count_links(content: str, *, site_hosts: set[str]) -> dict[str, Any]:
    """Count links by kind and list the distinct external URLs.

    ``site_hosts`` is the set of hosts that count as internal (the site's own
    origin plus its www/apex variants). An empty set makes every absolute URL
    external — callers should pass the real hosts.
    """
    counts = {"internal": 0, "external": 0, "anchor": 0, "other": 0}
    external_urls: list[str] = []
    seen_external: set[str] = set()
    for match in _HREF.finditer(content or ""):
        href = match.group(1)
        kind = _classify(href, site_hosts)
        counts[kind] += 1
        if kind == "external":
            normalized = href.strip()
            if normalized not in seen_external:
                seen_external.add(normalized)
                external_urls.append(normalized)
    return {
        "internal": counts["internal"],
        "external": counts["external"],
        "anchor": counts["anchor"],
        "other": counts["other"],
        "total": counts["internal"] + counts["external"] + counts["anchor"] + counts["other"],
        "external_urls": external_urls,
    }


def site_hosts_from(base_url: str | None) -> set[str]:
    """The hosts that count as internal for a given site origin."""
    hosts: set[str] = set()
    if not base_url:
        return hosts
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except ValueError:
        return hosts
    if host:
        hosts.add(host)
        hosts.add(f"www.{host}" if not host.startswith("www.") else host[4:])
    return hosts
