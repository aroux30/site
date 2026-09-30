"""Content-level site health checks.

The existing ``site_health_service`` checks the *platform*: is PostgreSQL up,
is Redis reachable, are migrations current. Those all stay green while a site
is quietly broken in ways only the owner would notice — a post whose publish
time passed but which never appeared, a menu entry pointing at a deleted page,
a media row whose file was removed by a failed deploy.

These checks ask about the site's own content, and each one names the
operator action that resolves it. A check that cannot fail is not a check, so
every one here has a reachable bad state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select, text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _check(
    name: str, status: str, value: str, description: str, *, critical: bool = False
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "value": value,
        "description": description,
        "scope": "content",
        "critical": critical,
    }


async def _check_scheduled_publish(db: AsyncSession) -> dict[str, Any]:
    """Posts whose scheduled publish time has passed but which never went live.

    This is the canary for a dead scheduler: Celery beat stops, nobody notices,
    and every future-dated post silently stays a draft forever.
    """
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

    now = datetime.now(UTC)
    # The scheduler does not use a "scheduled" status: a future post stays a
    # DRAFT with ``scheduled_for`` set, and publish_scheduled_posts promotes it
    # to PUBLISHED once the time passes. The old filter matched a status value
    # the enum cannot even hold, so this canary reported "good" permanently and
    # never detected a dead scheduler — which is the one thing it exists for.
    overdue = (await db.execute(
        select(func.count())
        .select_from(BlogPost)
        .where(
            BlogPost.status == BlogPostStatus.DRAFT,
            BlogPost.scheduled_for.is_not(None),
            BlogPost.scheduled_for < now,
            BlogPost.deleted_at.is_(None),
        )
    )).scalar_one()
    return _check(
        "Scheduled publishing",
        "critical" if overdue else "good",
        str(overdue),
        (
            f"{overdue} نوشته از زمان انتشار گذشته منتشر نشده است "
            "(زمان‌بند خراب است یا تسک اجرا نشده)"
            if overdue
            else "همهٔ نوشته‌های زمان‌بندی‌شده به‌موقع منتشر شده‌اند"
        ),
        critical=bool(overdue),
    )


async def _check_stale_trash(db: AsyncSession) -> dict[str, Any]:
    """Content sitting in the trash past the retention window."""
    from app.modules.blog.domain.models import BlogPost
    from app.modules.content.domain.models import CmsPage

    cutoff = datetime.now(UTC) - timedelta(days=30)
    posts = (await db.execute(
        select(func.count()).select_from(BlogPost).where(
            BlogPost.deleted_at.is_not(None), BlogPost.deleted_at < cutoff)
    )).scalar_one()
    pages = (await db.execute(
        select(func.count()).select_from(CmsPage).where(
            CmsPage.deleted_at.is_not(None), CmsPage.deleted_at < cutoff)
    )).scalar_one()
    total = posts + pages
    return _check(
        "Stale trash", "warning" if total else "good", str(total),
        (
            f"{total} مورد بیش از ۳۰ روز در زباله‌دان است ({posts} نوشته، {pages} صفحه)"
            if total
            else "زباله‌دانی قدیمی وجود ندارد"
        ),
    )


async def _check_media_orphans(db: AsyncSession) -> dict[str, Any]:
    """Media rows whose file is no longer on disk.

    Broken image URLs are invisible in the admin list: the row looks fine and
    the storefront 404s. A failed deploy or a manual cleanup causes it.
    """
    from app.core.config.settings import get_settings
    from app.modules.media.application.storage_paths import MEDIA_SUBDIR
    from app.modules.media.domain.models import MediaAsset

    rows = (await db.execute(select(MediaAsset.file_path, MediaAsset.id))).all()
    # Same correction as the site-health storage check: the old constant named
    # a directory nothing creates, so every row looked present and the count
    # was permanently zero. Read the path the uploader actually writes to.
    root = Path(get_settings().UPLOAD_DIR) / MEDIA_SUBDIR
    orphans = [
        str(asset_id) for path, asset_id in rows
        if not (root / path).exists()
        and not (root / Path(path).name).exists()
        and not Path(path).exists()
    ]
    return _check(
        "Orphaned media", "critical" if orphans else "good", str(len(orphans)),
        (
            f"{len(orphans)} رکورد رسانه به فایل ناموجود اشاره دارد"
            if orphans
            else "همهٔ فایل‌های رسانه روی دیسک موجودند"
        ),
        critical=bool(orphans),
    )


async def _check_broken_menu_links(db: AsyncSession) -> dict[str, Any]:
    """Menu entries pointing at a page that no longer exists — or that was renamed.

    Menus store a free-text URL, so renaming a page silently breaks every
    entry that referenced it. Nothing reports this today.

    The two failures need different words. A slug with no live page and no
    history was deleted, and the operator has to pick a replacement or drop the
    entry. A slug with a history row was *renamed*, and the fix is mechanical:
    point the menu at the current slug. Reporting both as "deleted page" is what
    made this check useless for a store that renames anything — the operator
    reads a rename as data loss and goes looking for a page that still exists.

    The menu is not rewritten. A URL rewrite is a content decision, and a
    health check silently editing the menu would make the report describe a
    state nobody chose. The current slug is named in the message so the repair
    is a copy-paste.
    """
    from app.modules.blog.application.slug_history_service import (
        SLUG_RESOURCE_CMS_PAGE,
    )
    from app.modules.blog.domain.wp_parity_models import SlugHistory
    from app.modules.content.domain.models import CmsPage, SiteMenu

    rows = (await db.execute(
        select(SiteMenu.title, SiteMenu.url).where(SiteMenu.is_active.is_(True))
    )).all()
    if not rows:
        return _check("Menu links", "good", "0", "منوی فعالی وجود ندارد")

    slugs = [url.rstrip("/").split("/")[-1] for url in (r.url or "" for r in rows)
             if url.startswith("/") and url.count("/") >= 1]
    if not slugs:
        return _check("Menu links", "good", "0", "همهٔ آیتم‌های منو لینک بیرونی یا ریشه‌ای هستند")
    live = set((await db.execute(
        select(CmsPage.slug).where(CmsPage.slug.in_(slugs))
    )).scalars().all())
    broken = [s for s in slugs if s not in live and s]
    if not broken:
        return _check("Menu links", "good", "0", "همهٔ لینک‌های داخلی منو معتبرند")

    # One query for every broken slug rather than one per slug: this runs on the
    # system-health page, and a menu with a dozen stale entries would otherwise
    # cost a dozen round trips.
    unique_broken = list(dict.fromkeys(broken))
    history_rows = (await db.execute(
        select(SlugHistory.old_slug, SlugHistory.new_slug)
        .where(
            SlugHistory.old_slug.in_(unique_broken),
            SlugHistory.resource_type == SLUG_RESOURCE_CMS_PAGE,
        )
        .order_by(SlugHistory.created_at.desc())
    )).all()
    # Newest row per old slug: a page renamed a→b→c leaves both rows, and only
    # the newer one names the current slug. Dict insertion order keeps the first
    # (newest) row and ignores the older one.
    renamed: dict[str, str] = {old_slug: new_slug for old_slug, new_slug in history_rows}
    gone = [s for s in unique_broken if s not in renamed]

    if renamed and not gone:
        detail = (
            f"{len(renamed)} آیتم منو به صفحه‌ای اشاره دارد که تغییر اسلاگ داده است: "
            + "، ".join(
                f"{old} → {new}" for old, new in list(renamed.items())[:5]
            )
        )
    elif renamed and gone:
        detail = (
            f"{len(renamed)} آیتم منو پس از تغییر اسلاگ و {len(gone)} آیتم به صفحهٔ حذف‌شده "
            "اشاره دارد. تغییر اسلاگ: "
            + "، ".join(f"{old} → {new}" for old, new in list(renamed.items())[:5])
            + ". حذف‌شده: "
            + "، ".join(gone[:5])
        )
    else:
        detail = (
            f"{len(gone)} آیتم منو به صفحهٔ حذف‌شده اشاره دارد: "
            + "، ".join(gone[:5])
        )
    return _check("Menu links", "critical", str(len(broken)), detail, critical=True)


async def _check_https(db: AsyncSession) -> dict[str, Any]:
    """Whether the deployment is configured to serve over TLS.

    The app cannot observe its own public-facing scheme. This check runs
    inside the process, so ``request.url.scheme`` here is always the hop on
    the internal compose network — plain HTTP even when TLS is correctly
    terminated at nginx in front. There is no request in scope here, and no
    header that a health check could read to learn what the browser saw.
    Guessing "https because the deployment should have it" is how the
    previous FORCE_HTTPS check ended up reporting "good" forever: the field
    did not exist, ``getattr(..., None)`` was always ``None``, and the
    ``critical`` branch was unreachable.

    So the signal is the operator's declaration, ``TLS_TERMINATION``:

    * ``proxy`` — TLS terminates at a reverse proxy. The app deliberately
      serves plain HTTP on the internal network, which is correct and safe;
      reporting "good" is honest.
    * ``app`` — uvicorn terminates TLS itself. Also good.
    * ``auto`` (the default) — nobody declared anything. That is NOT evidence
      of TLS; it is absence of evidence, and it is reported as such rather
      than laundered into a pass.
    """
    from app.core.config.settings import get_settings

    declared = getattr(get_settings(), "TLS_TERMINATION", "auto")
    if declared == "proxy":
        return _check(
            "HTTPS", "good", "terminated at proxy",
            "TLS در پراکسی معکوس (nginx) خاتمه می‌یابد؛ اتصال داخلی برنامه HTTP است",
        )
    if declared == "app":
        return _check(
            "HTTPS", "good", "terminated at app",
            "TLS مستقیماً توسط خود برنامه خاتمه می‌یابد",
        )
    return _check(
        "HTTPS", "warning", "undeterminable",
        "وضعیت TLS از داخل برنامه قابل تشخیص نیست: هیچ proxy یا بارگذاری در"
        " مسیر این استقرار نیست و TLS_TERMINATION تنظیم نشده است. اگر TLS در"
        " پراکسی خاتمه می‌یابد، مقدار proxy را در تنظیمات ثبت کنید تا این"
        " بررسی بتواند گزارش معتبر بدهد",
    )


async def _check_cron_last_run(db: AsyncSession) -> dict[str, Any]:
    """Whether the beat scheduler has run recently.

    The signal is the ``health:last_beat`` key in Redis, written by the
    ``record_heartbeat`` task that Celery beat fires every minute. It
    timestamps the beat, not any one business task, so a single heartbeat
    proves the scheduler is alive even if every periodic job it triggers is
    failing. No record at all means the beat has never fired.
    """
    try:
        from app.core.cache.redis import get_redis

        client = await get_redis()
        raw = await client.get("health:last_beat")
    except Exception as exc:  # Redis down is already reported by its own check.
        return _check("Scheduler", "warning", "unknown",
                      f"وضعیت زمان‌بند قابل خواندن نیست: {str(exc)[:120]}")
    if not raw:
        return _check(
            "Scheduler", "warning", "never",
            "هیچ اجرای زمان‌بندی ثبت نشده؛ Celery worker در حال اجرا نیست",
        )
    try:
        last = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
    except ValueError:
        return _check("Scheduler", "warning", "unknown", "مقدار ثبت‌شده نامعتبر است")
    if last.tzinfo is None:
        # The writer stamps UTC, but a hand-written or pre-upgrade value may
        # not carry an offset, and subtracting naive-from-aware raises. Treat
        # it as UTC rather than letting the TypeError escape this check.
        last = last.replace(tzinfo=UTC)
    age = datetime.now(UTC) - last
    stale = age > timedelta(minutes=30)
    return _check(
        "Scheduler", "critical" if stale else "good",
        f"{int(age.total_seconds() // 60)} دقیقه پیش",
        "زمان‌بند منظم کار می‌کند" if not stale
        else f"{int(age.total_seconds() // 60)} دقیقه از آخرین اجرا گذشته است",
        critical=stale,
    )


async def _check_content_search_index(db: AsyncSession) -> dict[str, Any]:
    """Whether published content is discoverable by search.

    A search outage that returns zero hits is indistinguishable from an empty
    catalogue, so a missing index reads as "this site has no articles".
    """
    try:
        from app.modules.search.infrastructure.elasticsearch_client import (
            get_elasticsearch_service,
        )

        client = await get_elasticsearch_service().connect()
        healthy = bool(await client.ping())
    except Exception as exc:
        logger.warning("content_search_ping_failed", exc_info=exc)
        return _check(
            "Content search", "warning", "unavailable",
            f"جستجوی محتوا در دسترس نیست: {str(exc)[:120]}",
        )
    return _check(
        "Content search", "good" if healthy else "critical",
        "ready" if healthy else "down",
        "نمایهٔ جستجوی محتوا آماده است" if healthy
        else "نمایهٔ جستجوی محتوا از دسترس خارج است",
        critical=not healthy,
    )


CONTENT_CHECKS = (
    _check_scheduled_publish,
    _check_stale_trash,
    _check_media_orphans,
    _check_broken_menu_links,
    _check_https,
    _check_cron_last_run,
    _check_content_search_index,
)


async def run_content_checks(db: AsyncSession) -> list[dict[str, Any]]:
    """Run every content check, isolating failures so one bad query cannot
    hide the other six results.

    An exception is reported as ``critical``, not ``warning``. A check that
    raises is a check that did not run, so we do not know whether the
    condition it exists to catch is present — and for a canary, "I could not
    look" must never read as "probably fine". Downgrading a crash to a
    warning is what previously let a genuine "scheduler is dead" verdict
    arrive as a generic warning: the AttributeError in the stale branch was
    raised while building the critical result, caught here, and flattened
    into a pass-shaped report.
    """
    results: list[dict[str, Any]] = []
    for check in CONTENT_CHECKS:
        try:
            results.append(await check(db))
        except Exception as exc:
            logger.warning("content_health_check_failed", check=check.__name__, exc_info=exc)
            results.append(_check(
                check.__name__.lstrip("_").replace("_", " ").title(), "critical", "error",
                f"این بررسی اجرا نشد و نتیجهٔ آن نامعلوم است: {str(exc)[:160]}",
                critical=True,
            ))
    return results
