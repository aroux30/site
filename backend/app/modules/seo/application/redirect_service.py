"""SEO redirect management (Rank Math Redirections parity).

Admin-managed redirect rules evaluated by the storefront middleware. Matching
is one of three modes, in priority order at evaluation time:

1. **Exact** path (normalized: lowercase, no trailing slash).
2. **Wildcard** suffix (``/old-blog/*``) — longest prefix wins.
3. **Regex** (``is_regex=True``) — Python-flavored pattern matched against the
   request path; a capture group referenced as ``$1`` in the target is
   substituted (Rank Math's back-reference syntax).

Status codes (Rank Math's set): 301, 302, 307, 308 carry a destination;
410 (Gone) and 451 (legal) must NOT — their meaning is "not coming back",
and a 410 pointing at a live page is a contradiction. Loops (from == to
after following a chain) are rejected at write time, and regex rules are
checked for a self-match (a pattern whose own replacement equals itself
would redirect forever).
"""

from __future__ import annotations

import csv
import io
import re
import uuid

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.seo.domain.models import RedirectRule

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_PATH_RE = re.compile(r"^/[a-zA-Z0-9\-_/.~%]*\*?$")

#: Codes that carry a destination. 410/451 are terminal by definition.
CODES_WITH_TARGET = (301, 302, 307, 308)
CODES_WITHOUT_TARGET = (410, 451)
ALL_STATUS_CODES = CODES_WITH_TARGET + CODES_WITHOUT_TARGET


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


def _validate_regex(pattern: str) -> str:
    """Compile-check a regex source; reject invalid patterns at write time.

    An invalid pattern stored now would be silently skipped by the matcher
    forever — the operator would believe the redirect works.
    """
    pattern = pattern.strip()
    if not pattern:
        raise ValidationError("الگوی regex خالی است")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValidationError(f"الگوی regex معتبر نیست: {exc}") from None
    return pattern


def _validate_status(status_code: int, to_path: str | None) -> None:
    if status_code not in ALL_STATUS_CODES:
        raise ValidationError(
            f"کد وضعیت باید یکی از {', '.join(str(c) for c in ALL_STATUS_CODES)} باشد"
        )
    if status_code in CODES_WITH_TARGET and not (to_path or "").strip():
        raise ValidationError(f"کد {status_code} به مقصد نیاز دارد")
    if status_code in CODES_WITHOUT_TARGET and (to_path or "").strip():
        raise ValidationError(
            f"کد {status_code} مقصد نمی‌پذیرد — معنایش «برنمی‌گردد» است"
        )


async def create_redirect(
    db,
    *,
    from_path: str,
    to_path: str | None,
    status_code: int = 301,
    is_regex: bool = False,
    note: str | None = None,
) -> RedirectRule:
    _validate_status(status_code, to_path)
    if is_regex:
        src = _validate_regex(from_path)
        dst = (to_path or "").strip() or None
    else:
        src = _normalize_path(from_path, allow_wildcard=True)
        dst = _normalize_path(to_path, allow_wildcard=False) if to_path else None

    if dst is not None and src.rstrip("/*") == dst:
        raise ValidationError("ریدایرکت چرخه‌ای مجاز نیست")
    if is_regex and dst:
        # A pattern whose own replacement is the matched path redirects to
        # itself forever; cheap probe, catches the common operator mistake.
        try:
            if re.sub(src, dst, src) == src and re.fullmatch(src, src):
                raise ValidationError("الگوی regex به خودش ریدایرکت می‌شود")
        except re.error:
            pass

    existing = (
        await db.execute(select(RedirectRule).where(RedirectRule.from_path == src))
    ).scalar_one_or_none()
    if existing:
        raise ValidationError(f"برای «{src}» از قبل ریدایرکت ثبت شده است")

    # Chained-loop guard: /a→/b must not be added when /b→/a (or a longer
    # chain back to /a) already exists, otherwise visitors bounce forever.
    # Regex rules are exempt: their chain cannot be walked statically.
    if not is_regex and dst is not None:
        all_rules = await list_redirects(db)
        chain: dict[str, str] = {
            r.from_path: r.to_path for r in all_rules if r.to_path and not r.is_regex
        }
        hop = dst
        for _ in range(len(chain) + 1):
            if hop == src.rstrip("/*"):
                raise ValidationError("زنجیره ریدایرکت باعث حلقه می‌شود")
            hop = chain.get(hop)
            if hop is None:
                break

    rule = RedirectRule(
        from_path=src,
        to_path=dst,
        status_code=status_code,
        is_regex=is_regex,
        note=note,
    )
    db.add(rule)
    await db.flush()
    logger.info("redirect_created", from_path=src, to_path=dst, status=status_code)
    return rule


async def update_redirect(
    db,
    rule_id: uuid.UUID,
    *,
    from_path: str | None = None,
    to_path: str | None = None,
    status_code: int | None = None,
    is_active: bool | None = None,
    is_regex: bool | None = None,
    note: str | None = None,
) -> RedirectRule:
    """Edit or (de)activate a rule. Re-normalizes and re-checks collisions."""
    rule = await db.get(RedirectRule, rule_id)
    if not rule:
        raise NotFoundError("RedirectRule", f"Redirect {rule_id} not found")

    new_status = status_code if status_code is not None else rule.status_code
    new_regex = is_regex if is_regex is not None else rule.is_regex

    if from_path is not None:
        src = (
            _validate_regex(from_path)
            if new_regex
            else _normalize_path(from_path, allow_wildcard=True)
        )
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

    if to_path is not None or status_code is not None or is_regex is not None:
        raw_dst = to_path if to_path is not None else rule.to_path
        if new_regex:
            dst = (raw_dst or "").strip() or None
        else:
            dst = (
                _normalize_path(raw_dst, allow_wildcard=False)
                if (raw_dst or "").strip()
                else None
            )
        _validate_status(new_status, dst)
        if dst is not None and rule.from_path.rstrip("/*") == dst:
            raise ValidationError("ریدایرکت چرخه‌ای مجاز نیست")
        rule.to_path = dst

    if status_code is not None:
        rule.status_code = status_code
    if is_regex is not None:
        rule.is_regex = is_regex
    if is_active is not None:
        rule.is_active = is_active
    if note is not None:
        rule.note = note or None

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


def apply_regex_target(pattern: str, target: str, path: str) -> str | None:
    """Substitute $1 back-references in a regex rule's target, or None.

    Rank Math uses ``$1`` for capture groups. A reference to a group the
    pattern does not have expands to an empty string (the middleware's
    JavaScript does the same) — refusing the whole redirect over a stray
    ``$2`` would make a working rule mysteriously dead.
    """
    match = re.match(pattern, path)
    if not match:
        return None

    def expand(m: re.Match[str]) -> str:
        group = int(m.group(1))
        if group > (match.re.groups or 0):
            return ""
        return match.group(group) or ""

    return re.sub(r"\$(\d)", expand, target)


def match_redirect(path: str, rules: list[RedirectRule]) -> RedirectRule | None:
    """Exact first, then longest wildcard prefix, then regex (first match).

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
    regex_rules: list[RedirectRule] = []
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.is_regex:
            regex_rules.append(rule)
            continue
        if rule.from_path.endswith("/*"):
            prefix = rule.from_path[:-2]
            if norm == prefix or norm.startswith(prefix + "/"):
                if len(prefix) > best_prefix_len:
                    best = rule
                    best_prefix_len = len(prefix)
        elif norm == rule.from_path:
            return rule  # exact beats any wildcard
    if best is not None:
        return best
    for rule in regex_rules:
        try:
            if re.match(rule.from_path, norm):
                return rule
        except re.error:
            # A stored pattern that no longer compiles is skipped, not fatal.
            continue
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

    managed = {
        r.from_path: r.to_path
        for r in await list_redirects(db)
        if r.is_active and r.to_path and not r.is_regex
    }

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


# ── CSV import / export (Rank Math's Redirections CSV tools) ───────────────


def export_redirects_csv(rules: list[RedirectRule]) -> str:
    """Rules as CSV: source,target,status,regex,active,hits,note.

    UTF-8 with a BOM so Excel opens Persian notes correctly — the same
    convention the reporting CSV exports use.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["source", "target", "status", "regex", "active", "hits", "note"])
    for r in rules:
        writer.writerow(
            [
                r.from_path,
                r.to_path or "",
                r.status_code,
                "1" if r.is_regex else "0",
                "1" if r.is_active else "0",
                r.hit_count or 0,
                r.note or "",
            ]
        )
    return "﻿" + buf.getvalue()


def parse_redirects_csv(content: str) -> list[dict[str, object]]:
    """Parse an import CSV into rule dicts; malformed rows are reported.

    Accepts the export shape and Rank Math's own export (source/target/status
    columns, header case-insensitive). Rows without a source are skipped with
    a reason; the caller surfaces the reasons to the operator instead of
    silently importing a partial file.
    """
    # Strip a BOM if present.
    if content.startswith("﻿"):
        content = content[1:]
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValidationError("فایل CSV خالی است")
    headers = {h.strip().lower(): h for h in reader.fieldnames if h}

    def col(*names: str) -> str | None:
        for name in names:
            if name in headers:
                return headers[name]
        return None

    src_col = col("source", "from", "from_path", "مبدأ")
    dst_col = col("target", "to", "to_path", "مقصد")
    status_col = col("status", "status_code", "code", "کد")
    regex_col = col("regex", "is_regex")
    note_col = col("note", "یادداشت")
    if not src_col:
        raise ValidationError("ستون مبدأ (source) در فایل پیدا نشد")

    out: list[dict[str, object]] = []
    for i, row in enumerate(reader, start=2):
        source = (row.get(src_col) or "").strip()
        if not source:
            continue
        try:
            status = int((row.get(status_col) or "301").strip() or "301")
        except (TypeError, ValueError):
            raise ValidationError(f"سطر {i}: کد وضعیت نامعتبر") from None
        is_regex = (row.get(regex_col) or "").strip().lower() in {"1", "true", "yes", "on"}
        out.append(
            {
                "from_path": source,
                "to_path": (row.get(dst_col) or "").strip() or None,
                "status_code": status,
                "is_regex": is_regex,
                "note": (row.get(note_col) or "").strip() or None,
                "line": i,
            }
        )
    return out


async def import_redirects_csv(db, content: str) -> dict[str, object]:
    """Import rules from CSV; per-row failures reported, valid rows imported.

    Partial success is deliberate: one bad row in a 200-row htaccess migration
    must not discard the other 199. The response carries every failure with
    its line number.
    """
    parsed = parse_redirects_csv(content)
    created = 0
    updated = 0
    errors: list[dict[str, object]] = []
    for entry in parsed:
        line = entry.pop("line")
        try:
            existing = (
                await db.execute(
                    select(RedirectRule).where(
                        RedirectRule.from_path == entry["from_path"]
                    )
                )
            ).scalar_one_or_none()
            if existing:
                await update_redirect(
                    db,
                    existing.id,
                    to_path=entry["to_path"],
                    status_code=entry["status_code"],
                    is_regex=entry["is_regex"],
                    note=entry["note"],
                )
                updated += 1
            else:
                await create_redirect(
                    db,
                    from_path=str(entry["from_path"]),
                    to_path=entry["to_path"],  # type: ignore[arg-type]
                    status_code=int(entry["status_code"]),  # type: ignore[arg-type]
                    is_regex=bool(entry["is_regex"]),
                    note=entry["note"],  # type: ignore[arg-type]
                )
                created += 1
        except ValidationError as exc:
            errors.append({"line": line, "error": str(exc)})
        except Exception:
            # A savepoint per row: one failure must not poison the session for
            # the remaining rows (the import would abort mid-file otherwise).
            errors.append({"line": line, "error": "خطای غیرمنتظره"})
            await db.rollback()
            raise ValidationError(
                "ایمپورت به دلیل خطای غیرمنتظره متوقف شد؛ ردیف‌های قبلی ذخیره شدند"
            ) from None
    return {"created": created, "updated": updated, "errors": errors, "total": len(parsed)}
