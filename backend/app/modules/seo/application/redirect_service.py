"""SEO redirect management (WordPress Redirection / Payload redirects parity).

Admin-managed 301/302 rules evaluated by the storefront middleware. Redirects
match on exact path (normalized: lowercase, no trailing slash) or a single
``*`` wildcard suffix (``/old-blog/*``). Loops (from == to after following)
are rejected at write time.
"""

from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.seo.domain.models import RedirectRule

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_PATH_RE = re.compile(r"^/[a-zA-Z0-9\-_/.~%]*\*?$")


def _normalize_path(path: str, *, allow_wildcard: bool) -> str:
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    if not _PATH_RE.match(path):
        raise ValidationError(f"مسیر «{path}» معتبر نیست")
    if path.endswith("*"):
        if not allow_wildcard:
            raise ValidationError("مقصد نمی‌تواند wildcard داشته باشد")
        path = path[:-1].rstrip("/") + "/*"
    elif len(path) > 1:
        path = path.rstrip("/")
    return path.lower()


async def create_redirect(
    db, *, from_path: str, to_path: str, status_code: int = 301
) -> RedirectRule:
    if status_code not in (301, 302):
        raise ValidationError("کد وضعیت باید 301 یا 302 باشد")
    src = _normalize_path(from_path, allow_wildcard=True)
    dst = _normalize_path(to_path, allow_wildcard=False)
    if src.rstrip("/*") == dst:
        raise ValidationError("ریدایرکت چرخه‌ای مجاز نیست")

    existing = (
        await db.execute(select(RedirectRule).where(RedirectRule.from_path == src))
    ).scalar_one_or_none()
    if existing:
        raise ValidationError(f"برای «{src}» از قبل ریدایرکت ثبت شده است")

    # Chained-loop guard: /a→/b must not be added when /b→/a (or a longer
    # chain back to /a) already exists, otherwise visitors bounce forever.
    all_rules = await list_redirects(db)
    chain: dict[str, str] = {r.from_path: r.to_path for r in all_rules}
    hop = dst
    for _ in range(len(chain) + 1):
        if hop == src.rstrip("/*"):
            raise ValidationError("زنجیره ریدایرکت باعث حلقه می‌شود")
        hop = chain.get(hop)
        if hop is None:
            break

    rule = RedirectRule(from_path=src, to_path=dst, status_code=status_code)
    db.add(rule)
    await db.flush()
    logger.info("redirect_created", from_path=src, to_path=dst)
    return rule


async def update_redirect(
    db,
    rule_id: uuid.UUID,
    *,
    from_path: str | None = None,
    to_path: str | None = None,
    status_code: int | None = None,
    is_active: bool | None = None,
) -> RedirectRule:
    """Edit or (de)activate a rule. Re-normalizes and re-checks collisions."""
    rule = await db.get(RedirectRule, rule_id)
    if not rule:
        raise NotFoundError("RedirectRule", f"Redirect {rule_id} not found")

    if status_code is not None:
        if status_code not in (301, 302):
            raise ValidationError("کد وضعیت باید 301 یا 302 باشد")
        rule.status_code = status_code
    if is_active is not None:
        rule.is_active = is_active
    if from_path is not None:
        src = _normalize_path(from_path, allow_wildcard=True)
        clash = (
            await db.execute(
                select(RedirectRule).where(
                    RedirectRule.from_path == src, RedirectRule.id != rule_id
                )
            )
        ).scalar_one_or_none()
        if clash:
            raise ValidationError(f"برای «{src}» از قبل ریدایرکت ثبت شده است")
        rule.from_path = src
    if to_path is not None:
        dst = _normalize_path(to_path, allow_wildcard=False)
        if rule.from_path.rstrip("/*") == dst:
            raise ValidationError("ریدایرکت چرخه‌ای مجاز نیست")
        rule.to_path = dst

    await db.flush()
    logger.info("redirect_updated", rule_id=str(rule_id))
    return rule


async def list_redirects(db) -> list[RedirectRule]:
    stmt = select(RedirectRule).order_by(RedirectRule.from_path)
    return list((await db.execute(stmt)).scalars().all())


async def record_hits(db, from_paths: list[str]) -> int:
    """Increment hit_count for matched rules (called by the hit beacon).

    Accepts the rule's from_path (the middleware already knows it), deduped,
    so the storefront never needs to send raw request paths.
    """
    if not from_paths:
        return 0
    unique = list(dict.fromkeys(from_paths))[:50]
    rules = (
        (await db.execute(select(RedirectRule).where(RedirectRule.from_path.in_(unique))))
        .scalars()
        .all()
    )
    for rule in rules:
        rule.hit_count = (rule.hit_count or 0) + 1
    await db.flush()
    return len(rules)


async def delete_redirect(db, rule_id: uuid.UUID) -> None:
    rule = await db.get(RedirectRule, rule_id)
    if not rule:
        raise NotFoundError("RedirectRule", f"Redirect {rule_id} not found")
    await db.delete(rule)
    await db.flush()


def match_redirect(path: str, rules: list[RedirectRule]) -> RedirectRule | None:
    """Exact match first, then longest wildcard prefix — deterministic order.

    The comparison is between the two *prefixes*, not between a prefix and a
    whole ``from_path``. Comparing ``len(prefix)`` against
    ``len(best.from_path)`` mixed two different strings — one carries the
    trailing ``/*`` and the other does not — so a longer prefix could be
    rejected in favour of a shorter one depending on list order, which made
    the winner depend on which rule happened to be edited last.
    """
    norm = path.strip().lower().rstrip("/") or "/"
    best: RedirectRule | None = None
    best_prefix_len = -1
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.from_path.endswith("/*"):
            prefix = rule.from_path[:-2]
            if norm == prefix or norm.startswith(prefix + "/"):
                if len(prefix) > best_prefix_len:
                    best = rule
                    best_prefix_len = len(prefix)
        elif norm == rule.from_path:
            return rule  # exact beats any wildcard
    return best


# Storefront URL prefixes per polymorphic resource. These are the *public* paths
# the Next middleware matches, not the API paths: an API 301 would never be seen
# by a browser or a crawler that followed a link to the storefront URL.
SLUG_STOREFRONT_PREFIX: dict[str, str] = {
    "blog_post": "/blog/",
    "cms_page": "/",
}


def _would_loop(from_path: str, to_path: str, managed: dict[str, str]) -> bool:
    """Whether following *managed* hops from *to_path* returns to *from_path*.

    The derived rules are not written through :func:`create_redirect`, so they
    never pass that function's loop guard. A managed ``/b → /a`` alongside a
    derived ``/a → /b`` would ping-pong a visitor forever; such a pair is
    contradictory operator input, and dropping the derived side leaves the
    managed rule — the human's explicit decision — in force.
    """
    hop = to_path
    # Bounded by the number of managed rules: a chain longer than that cannot
    # revisit, and an unbounded walk on a cycle in the managed data would hang.
    for _ in range(len(managed) + 1):
        if hop == from_path:
            return True
        hop = managed.get(hop)
        if hop is None:
            return False
    return False


async def slug_history_redirects(db) -> list[dict[str, object]]:
    """Derive 301s for old slugs from the slug-change history.

    A renamed page 404s every link to its old URL, and the history table is the
    only record that the slug moved rather than the resource going away. These
    rules are returned alongside the managed ones by the public redirects feed
    and are evaluated by the same Next middleware matcher — no second redirect
    mechanism, no new endpoint, and the admin's redirects screen keeps showing
    the complete set.

    Three filters, each for a case where a redirect would be *worse* than the
    404 it replaces:

    * **The target must be live.** History outlives its resource: a page
      renamed and then deleted still has a row, and redirecting to its dead
      slug turns a 404 into a 404 behind a hop.
    * **A managed rule wins.** If an operator wrote a rule for the same old
      path, that is a deliberate choice and it stays.
    * **No loops.** See :func:`_would_loop`.
    """
    from sqlalchemy import select

    from app.modules.blog.domain.models import BlogPost
    from app.modules.blog.domain.wp_parity_models import SlugHistory
    from app.modules.content.domain.models import CmsPage

    rows = (await db.execute(
        select(
            SlugHistory.resource_type,
            SlugHistory.old_slug,
            SlugHistory.new_slug,
        )
        .where(SlugHistory.resource_type.in_(SLUG_STOREFRONT_PREFIX))
        .order_by(SlugHistory.created_at.desc())
    )).all()
    if not rows:
        return []

    old_slugs = [r.old_slug for r in rows]
    new_slugs = list({r.new_slug for r in rows})
    # Two existence probes rather than a join per resource type: both are
    # primary-key-ish lookups on an indexed column, and the set maths that
    # follows stays in Python where it is readable.
    live_pages = set((await db.execute(
        select(CmsPage.slug).where(
            CmsPage.slug.in_(new_slugs), CmsPage.deleted_at.is_(None))
    )).scalars().all())
    live_posts = set((await db.execute(
        select(BlogPost.slug).where(
            BlogPost.slug.in_(new_slugs), BlogPost.deleted_at.is_(None))
    )).scalars().all())

    managed = {r.from_path: r.to_path for r in await list_redirects(db) if r.is_active}

    live_by_type = {"cms_page": live_pages, "blog_post": live_posts}
    rules: list[dict[str, object]] = []
    seen: set[str] = set()
    for resource_type, old_slug, new_slug in rows:
        prefix = SLUG_STOREFRONT_PREFIX[resource_type]
        if new_slug not in live_by_type[resource_type]:
            continue
        from_path = (prefix + old_slug).lower()
        to_path = (prefix + new_slug).lower()
        if from_path == to_path or from_path in seen or from_path in managed:
            continue
        if _would_loop(from_path, to_path, managed):
            continue
        seen.add(from_path)
        # 301, not 302: the old URL is permanently gone, which is what tells a
        # search engine to move the ranking instead of re-checking forever.
        rules.append({"from_path": from_path, "to_path": to_path, "status_code": 301})

    logger.info("slug_history_redirects_derived", count=len(rules))
    return rules
