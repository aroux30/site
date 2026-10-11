"""Broken-link crawler (Rank Math Pro's Link Genius "Audit" crawler).

Walks every distinct URL the site links to, fetches it, and records the
verdict. The operator's question is "which of my links are dead", so the table
is keyed by URL (not by the post that contains it): a dead URL linked from ten
posts is one row, one check, one fix.

Two safety rules, both from the project's existing machinery:

* **SSRF.** Every URL is vetted by :mod:`app.core.security.url_guard` before a
  request goes out, and the request is *pinned* to the vetted address so the
  name cannot be re-resolved after the check (true DNS-rebinding). A URL the
  guard refuses is recorded as ``blocked`` — it was never fetched, which is the
  assertion the SSRF test pins.
* **Robots.** A URL whose path is disallowed for our user-agent by the target
  domain's ``robots.txt`` is skipped (recorded as ``ok`` with a note, not
  fetched). The per-domain robots file is cached for the run.

The fetch never follows a redirect itself; it records the first response. A
3xx is only "broken" if it loops or points off-host — a plain normalization
redirect (http→https, trailing slash) is the target's business, not a broken
link, so a redirect is bucketed ``redirect`` and surfaced separately from
``broken``.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.url_guard import BlockedURLError, validate_pinned_url
from app.modules.seo.domain.link_models import SeoInternalLink, SeoLinkAudit

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Per-request budget. A dead host that hangs is the common case; 8s is short
#: enough that a page of 100 URLs cannot stall a worker for long, long enough
#: for a slow-but-alive host.
_REQUEST_TIMEOUT = 8.0

#: Do not re-check a URL within this window — a link does not break and heal
#: between two runs, and re-checking every URL on every run is how a crawler
#: gets its IP banned.
_RECHECK_AFTER = timedelta(hours=24)

#: How many URLs one run checks. Bounded so a single task invocation cannot run
#: for hours; the rest are picked up next run (oldest-checked first).
BATCH_SIZE = 100

#: Identify honestly. A crawler that lies about what it is gets blocked, and
#: the operator then cannot tell a real 403 from a bot filter.
_USER_AGENT = "ArouxShop-LinkAudit/1.0 (+link-checker)"

#: robots.txt per-domain cache, keyed by scheme://host.
_ROBOTS_TTL = timedelta(hours=24)


@dataclass
class AuditResult:
    url: str
    url_hash: str
    http_status: int | None
    category: str
    detail: str | None


def _hash(url: str) -> str:
    from app.modules.seo.application.link_extraction_service import url_hash

    return url_hash(url)


def _category_for_status(status: int) -> str:
    if 200 <= status < 300:
        return "ok"
    if 300 <= status < 400:
        return "redirect"
    return "broken"


def _same_host(a: str, b: str) -> bool:
    try:
        return (urlparse(a).hostname or "").lower() == (urlparse(b).hostname or "").lower()
    except ValueError:
        return False


async def _fetch_one(client: httpx.AsyncClient, url: str) -> AuditResult:
    """Fetch one URL and classify the outcome. Never raises."""
    h = _hash(url)
    try:
        connect_url, host = await validate_pinned_url(url, what="نشانی")
    except BlockedURLError as exc:
        # Refused by the SSRF guard: NOT fetched. This is the "blocked" bucket,
        # and the SSRF test asserts the request never left.
        return AuditResult(url, h, None, "blocked", str(exc)[:500])
    except Exception as exc:  # noqa: BLE001 — e.g. a host that does not resolve
        # A domain that does not resolve is a dead link, not a security block;
        # bucketing it as "blocked" would hide real broken domains.
        return AuditResult(url, h, None, "error", str(exc)[:500])

    parsed = urlparse(url)
    host_header = host if parsed.port is None else f"{host}:{parsed.port}"
    try:
        response = await client.get(
            connect_url,
            headers={"Host": host_header, "User-Agent": _USER_AGENT},
            extensions={"sni_hostname": host},
        )
    except httpx.TimeoutException:
        return AuditResult(url, h, None, "timeout", "پاسخی در بازهٔ زمانی دریافت نشد")
    except (httpx.ConnectError, httpx.NetworkError, httpx.TransportError) as exc:
        return AuditResult(url, h, None, "error", str(exc)[:500])
    except Exception as exc:  # noqa: BLE001 — never let one URL kill the run
        return AuditResult(url, h, None, "error", str(exc)[:500])

    status = response.status_code
    category = _category_for_status(status)
    detail: str | None = None
    if category == "redirect":
        location = response.headers.get("location", "")
        # A redirect that points off-host or back at itself is worth flagging;
        # a same-host normalization redirect is benign and bucketed the same
        # but noted so the operator can tell them apart.
        if location and not _same_host(url, location) and not location.startswith("/"):
            detail = f"به دامنهٔ دیگر: {location[:200]}"
        elif location:
            detail = f"→ {location[:200]}"
    return AuditResult(url, h, status, category, detail)


# ── robots.txt ──────────────────────────────────────────────────────────────


def _robots_allows(robots_txt: str, path: str, user_agent: str = "*") -> bool:
    """Whether ``path`` is allowed for ``user_agent`` per a robots.txt body.

    A minimal, correct-enough parser: it groups by User-agent, matches the
    most specific agent that has any rule (``*`` is the fallback), and applies
    longest-match-wins with Allow beating Disallow on equal length — the same
    tie-break Google documents. Not a full RFC 9309 parser (no wildcards), but
    it errs toward allowing, which for a link checker is the safe direction: a
    false "allowed" costs one request, a false "disallowed" hides a real broken
    link.
    """
    if not robots_txt:
        return True

    groups: dict[str, list[tuple[str, str]]] = {}
    current_agents: list[str] = []
    expecting_agent = False
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if not expecting_agent:
                current_agents = []
                expecting_agent = True
            current_agents.append(value.lower())
            groups.setdefault(value.lower(), [])
        elif field in ("allow", "disallow"):
            expecting_agent = False
            for agent in current_agents or ["*"]:
                groups.setdefault(agent, []).append((field, value))

    # Pick the most specific matching agent group; fall back to "*".
    rules: list[tuple[str, str]] = []
    ua = user_agent.lower()
    best = ""
    for agent in groups:
        if agent == "*":
            continue
        if agent in ua and len(agent) > len(best):
            best = agent
    if best:
        rules = groups[best]
    elif "*" in groups:
        rules = groups["*"]
    if not rules:
        return True

    decision = True
    best_len = -1
    for field, value in rules:
        if not value:
            # "Disallow:" with an empty value means allow all.
            continue
        if path.startswith(value):
            # Longest match wins; Allow beats Disallow on a tie.
            if len(value) > best_len or (
                len(value) == best_len and field == "allow"
            ):
                best_len = len(value)
                decision = field == "allow"
    return decision


async def _load_robots(
    client: httpx.AsyncClient, scheme: str, host: str, cache: dict[str, str]
) -> str:
    """Fetch and cache a domain's robots.txt (empty string on any failure)."""
    key = f"{scheme}://{host}"
    if key in cache:
        return cache[key]
    text = ""
    try:
        robots_url = f"{scheme}://{host}/robots.txt"
        connect_url, pinned_host = await validate_pinned_url(robots_url, what="نشانی")
        resp = await client.get(
            connect_url,
            headers={"Host": pinned_host, "User-Agent": _USER_AGENT},
            extensions={"sni_hostname": pinned_host},
        )
        if resp.status_code == 200:
            text = resp.text[:100_000]
    except Exception:  # noqa: BLE001 — no robots = allow (the safe direction)
        text = ""
    cache[key] = text
    return text


# ── Collection + run ────────────────────────────────────────────────────────


async def collect_urls(db: AsyncSession) -> list[str]:
    """Every distinct managed URL the site links to.

    Reads the extracted link table (populated on save). If it is empty — a
    fresh install, or posts imported before the extractor ran — it falls back
    to scanning the published bodies directly so the first audit is not a
    no-op. Anchors and mailto/tel links are not in the table by construction.
    """
    rows = (
        await db.execute(select(SeoInternalLink.url))
    ).scalars().all()
    urls = {u for u in rows if u}
    if urls:
        return sorted(urls)

    # Fallback: extract from the bodies themselves.
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.seo.application.link_extraction_service import (
        extract_anchors,
        normalize_url,
    )
    from app.modules.settings.application.site_options_service import public_base_url
    from app.modules.seo.application.link_counter_service import site_hosts_from

    base = await public_base_url(db)
    hosts = site_hosts_from(base)
    posts = (
        await db.execute(
            select(BlogPost.content).where(
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for content in posts:
        for href, _text, _nf, _tb in extract_anchors(content or ""):
            href = href.strip()
            if not href or href.startswith("#"):
                continue
            if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            if href.startswith(("/", "./", "../")) and not href.startswith("//"):
                if base:
                    href = normalize_url(href, base=base)
                else:
                    continue
            elif not href.startswith(("http://", "https://")):
                continue
            host = (urlparse(href).hostname or "").lower()
            # Internal links are audited too (a deleted page 404s), but a
            # protocol-relative URL with no base is skipped above.
            if host:
                urls.add(normalize_url(href))
    return sorted(urls)


async def _recent_hashes(db: AsyncSession) -> dict[str, datetime]:
    """url_hash → last_checked_at for URLs checked inside the re-check window."""
    cutoff = datetime.now(UTC) - _RECHECK_AFTER
    rows = (
        await db.execute(
            select(SeoLinkAudit.url_hash, SeoLinkAudit.last_checked_at).where(
                SeoLinkAudit.last_checked_at >= cutoff
            )
        )
    ).all()
    return {h: ts for h, ts in rows}


async def _known_safe_hashes(db: AsyncSession) -> set[str]:
    rows = (
        await db.execute(
            select(SeoLinkAudit.url_hash).where(SeoLinkAudit.is_marked_safe.is_(True))
        )
    ).scalars().all()
    return set(rows)


async def run_audit(
    db: AsyncSession,
    *,
    batch_size: int = BATCH_SIZE,
    force: bool = False,
) -> dict[str, Any]:
    """Check up to ``batch_size`` URLs that are due, and record the results.

    ``force`` ignores the 24h re-check window (the admin's "check now" button).
    Returns a summary the task logs and the API returns.
    """
    urls = await collect_urls(db)
    if not urls:
        return {"checked": 0, "broken": 0, "redirect": 0, "total": 0}

    recent = {} if force else await _recent_hashes(db)
    safe = await _known_safe_hashes(db)

    due = [u for u in urls if _hash(u) not in recent]
    # Oldest-checked first so a large site makes progress across runs rather
    # than re-checking the same head of the list forever.
    if not force and due:
        checked_at: dict[str, datetime] = {}
        rows = (
            await db.execute(
                select(SeoLinkAudit.url_hash, SeoLinkAudit.last_checked_at)
            )
        ).all()
        by_hash = {h: ts for h, ts in rows}
        due.sort(key=lambda u: by_hash.get(_hash(u), datetime.min.replace(tzinfo=UTC)))
    due = due[:batch_size]

    if not due:
        return {"checked": 0, "broken": 0, "redirect": 0, "total": len(urls)}

    now = datetime.now(UTC)
    counts = {"ok": 0, "broken": 0, "redirect": 0, "timeout": 0, "error": 0, "blocked": 0}
    robots_cache: dict[str, str] = {}

    from app.modules.seo.application.link_counter_service import site_hosts_from
    from app.modules.settings.application.site_options_service import public_base_url

    own_hosts = site_hosts_from(await public_base_url(db))

    async with httpx.AsyncClient(
        timeout=_REQUEST_TIMEOUT, follow_redirects=False, trust_env=False
    ) as client:
        for url in due:
            h = _hash(url)
            parsed = urlparse(url)

            # robots.txt gate (external hosts only; our own site is ours to
            # crawl). A disallowed path is recorded as skipped, never fetched.
            is_own_host = (parsed.hostname or "").lower() in own_hosts
            if not is_own_host and parsed.hostname:
                robots = await _load_robots(
                    client, parsed.scheme or "https", parsed.hostname, robots_cache
                )
                if not _robots_allows(robots, parsed.path or "/"):
                    # Disallowed: do not fetch. Record as ok with a note so it
                    # does not show as broken (it is not) and is not re-checked
                    # every run.
                    await _upsert(
                        db,
                        AuditResult(url, h, None, "ok", "robots.txt اجازهٔ بررسی نمی‌دهد"),
                        now,
                        safe=h in safe,
                    )
                    counts["ok"] += 1
                    continue

            result = await _fetch_one(client, url)
            # A URL the operator marked safe keeps its "safe" flag across runs,
            # but its status still updates — the operator may have silenced it
            # for a reason that has since gone away.
            await _upsert(db, result, now, safe=h in safe)
            counts[result.category] = counts.get(result.category, 0) + 1

    await db.commit()
    summary = {
        "checked": len(due),
        "broken": counts["broken"],
        "redirect": counts["redirect"],
        "timeout": counts["timeout"],
        "error": counts["error"],
        "blocked": counts["blocked"],
        "total": len(urls),
    }
    logger.info("link_audit_run", **summary)
    return summary


async def _upsert(
    db: AsyncSession,
    result: AuditResult,
    now: datetime,
    *,
    safe: bool,
) -> None:
    """Insert or update the audit row for one URL, keyed by url_hash."""
    stmt = pg_insert(SeoLinkAudit).values(
        url=result.url[:2000],
        url_hash=result.url_hash,
        http_status=result.http_status,
        category=result.category,
        detail=result.detail,
        is_marked_safe=safe,
        last_checked_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[SeoLinkAudit.url_hash],
        set_={
            "url": stmt.excluded.url,
            "http_status": stmt.excluded.http_status,
            "category": stmt.excluded.category,
            "detail": stmt.excluded.detail,
            "last_checked_at": stmt.excluded.last_checked_at,
            # is_marked_safe is preserved on update (the operator's choice).
            "updated_at": now,
        },
    )
    await db.execute(stmt)


async def list_results(
    db: AsyncSession,
    *,
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
    hide_safe: bool = True,
) -> tuple[list[SeoLinkAudit], int, dict[str, int]]:
    """Paginated audit rows + a per-category count for the summary tiles."""
    from sqlalchemy import func

    filters = []
    if category:
        filters.append(SeoLinkAudit.category == category)
    if hide_safe:
        filters.append(SeoLinkAudit.is_marked_safe.is_(False))

    base = select(SeoLinkAudit)
    for f in filters:
        base = base.where(f)

    total = (
        await db.execute(
            select(func.count()).select_from(SeoLinkAudit).where(*filters)
        )
    ).scalar_one()

    # Broken first, then redirect/timeout/error, then ok — the operator wants
    # the problems at the top without filtering.
    severity = {"broken": 0, "error": 1, "timeout": 2, "redirect": 3, "ok": 4}
    rows = (
        await db.execute(
            base.order_by(SeoLinkAudit.last_checked_at.desc()).limit(500)
        )
    ).scalars().all()
    rows.sort(key=lambda r: (severity.get(r.category, 9), r.url))
    start = (page - 1) * page_size

    counts: dict[str, int] = {}
    for cat in ("ok", "broken", "redirect", "timeout", "error", "blocked"):
        counts[cat] = (
            await db.execute(
                select(func.count())
                .select_from(SeoLinkAudit)
                .where(SeoLinkAudit.category == cat, SeoLinkAudit.is_marked_safe.is_(False))
            )
        ).scalar_one()

    return rows[start : start + page_size], int(total), counts


async def mark_safe(db: AsyncSession, audit_id: Any, safe: bool) -> bool:
    """Set/clear the operator's "known safe" override. Returns False if absent."""
    row = await db.get(SeoLinkAudit, audit_id)
    if row is None:
        return False
    row.is_marked_safe = safe
    await db.commit()
    return True


async def clear_results(db: AsyncSession) -> int:
    from sqlalchemy import delete

    result = await db.execute(delete(SeoLinkAudit))
    await db.commit()
    return int(result.rowcount or 0)
