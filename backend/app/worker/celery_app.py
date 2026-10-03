"""Celery application configuration.

Usage::

    # Start worker
    celery -A app.worker.celery_app worker --loglevel=info

    # Start beat scheduler
    celery -A app.worker.celery_app beat --loglevel=info
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from celery import Celery
from celery.schedules import crontab

from app.core.config.settings import get_settings

settings = get_settings()

#: Every module that defines tasks, imported at worker boot.
#:
#: ``autodiscover_tasks(packages=[...], related_name="application.tasks")`` was
#: doing this job and did not: the packages list is a list of *modules*, and
#: autodiscover only imports ``<package>.tasks`` — a top-level module has no
#: ``tasks`` attribute to find, so nothing was imported and the worker
#: registered zero business tasks. Every beat job then fired into
#: "Received unregistered task" and died, silently: no cart expired, no media
#: purged, no daily report ran, and the site-health run never happened either.
#:
#: ``include`` is a list of module *paths*, and Celery imports each one during
#: ``finalize``, which runs on worker start and on every ``.delay()``. That is
#: what makes ``expire_stale_carts`` reachable — both from the beat and from a
#: request that enqueues it.
#:
#: Kept in step with the ``beat_schedule`` task paths below; a job whose task is
#: not on this list fails at fire time with nothing but a log line to show it.
#:
#: Validated against the filesystem below, and a bad entry raises here rather
#: than inside Celery's loader. The failure it replaces was silent and total: a
#: single path that does not resolve raises ModuleNotFoundError during
#: ``import_default_modules``, which aborts the loop *before* the modules after
#: it are imported — so one stale entry left the worker with a handful of tasks
#: and twenty-odd beat jobs firing into "unregistered task". Every entry is
#: therefore checked at import time, where the stack trace names the file.
TASK_MODULES: tuple[str, ...] = (
    "app.worker.celery_app",              # record_heartbeat, defined here
    "app.modules.auth.application.tasks",
    "app.modules.orders.application.tasks",
    "app.modules.cart.application.tasks",
    "app.modules.inventory.application.tasks",
    "app.modules.cashback.application.tasks",
    "app.modules.blog.application.tasks",
    "app.modules.content.application.tasks",
    "app.modules.search.application.tasks",
    "app.modules.media.application.tasks",
    "app.modules.analytics.application.tasks",
    "app.modules.integrations.application.tasks",
    "app.modules.dataexchange.application.tasks",
    "app.modules.reporting.application.tasks",
    "app.modules.subscriptions.application.tasks",
    "app.modules.settings.application.tasks",
    "app.modules.automation.application.tasks",
    "app.modules.audit.application.tasks",
    "app.modules.discounts.application.tasks",
    "app.modules.newsletter.application.tasks",
    "app.modules.recommendations.application.tasks",
    "app.modules.wallet.application.tasks",
    "app.modules.accounting.application.tasks",
    "app.modules.invoicing.application.tasks",
    "app.modules.messaging.application.tasks",
    "app.modules.notifications.application.tasks",
)

def _assert_task_modules_exist(modules: tuple[str, ...]) -> None:
    """Fail at import on a task module that is not on disk.

    Celery imports ``include`` lazily inside ``finalize()`` and lets the first
    ImportError propagate, so a bad entry looks like a dead worker rather than a
    typo in a list. Checking here costs one stat per module and turns that into
    an error that names the missing path.
    """
    import os

    # Resolved against this file, not the working directory: a worker started
    # from / would otherwise fail the check on every module and report the
    # whole list as missing.
    here = os.path.dirname(os.path.abspath(__file__))
    missing = [
        m
        for m in modules
        if not os.path.isfile(
            os.path.normpath(os.path.join(here, "..", "..", m.replace(".", os.sep) + ".py"))
        )
    ]
    if missing:
        raise ModuleNotFoundError(
            "celery include lists modules that do not exist: "
            + ", ".join(missing)
            + " — a task module was renamed or removed; the whole include list "
            "stops importing at the first bad entry, leaving the worker with "
            "almost no tasks registered."
        )


_assert_task_modules_exist(TASK_MODULES)

celery_app = Celery(
    "iranian_ecommerce",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=TASK_MODULES,
)

celery_app.conf.update(
    # ── Serialisation ─────────────────────────────────────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # ── Timezone ──────────────────────────────────────────────────────
    timezone="Asia/Tehran",
    enable_utc=True,
    # ── Task behaviour ────────────────────────────────────────────────
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=600,  # hard limit: 10 minutes
    task_soft_time_limit=540,  # soft limit: 9 minutes
    # ── Result backend ────────────────────────────────────────────────
    result_expires=3600,  # 1 hour
    # ── Worker ────────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_concurrency=4,
    # ── Routing ───────────────────────────────────────────────────────
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "high_priority": {"exchange": "high_priority", "routing_key": "high_priority"},
        "notifications": {"exchange": "notifications", "routing_key": "notifications"},
        "payments": {"exchange": "payments", "routing_key": "payments"},
        "analytics": {"exchange": "analytics", "routing_key": "analytics"},
    },
    task_routes={
        "app.modules.payments.*": {"queue": "payments"},
        "app.modules.notifications.*": {"queue": "notifications"},
        "app.modules.messaging.*": {"queue": "notifications"},
        "app.modules.analytics.*": {"queue": "analytics"},
    },
)

# ── Auto-discover tasks from every module ────────────────────────────────
celery_app.autodiscover_tasks(
    packages=[
        "app.modules.auth",
        "app.modules.users",
        "app.modules.catalog",
        "app.modules.orders",
        "app.modules.payments",
        # Sweeps and backfills. ``sweep_wallet_withdrawals`` moves money, and
        # without these two entries the worker registered neither module: the
        # tasks were defined, nothing beat-scheduled them, and nothing enqueued
        # them either — so pending withdrawals sat untouched with no error
        # anywhere. Found by tests/test_celery_task_registration.py, which
        # compares this list against the modules that actually ship a
        # ``tasks.py``.
        "app.modules.accounting",
        "app.modules.invoicing",
        "app.modules.notifications",
        "app.modules.messaging",
        "app.modules.shipping",
        "app.modules.analytics",
        "app.modules.recommendations",
        "app.modules.search",
        "app.modules.media",
        "app.modules.wallet",
        "app.modules.discounts",
        "app.modules.reviews",
        "app.modules.loyalty",
        "app.modules.gamification",
        "app.modules.cashback",
        "app.modules.referrals",
        "app.modules.support",
        "app.modules.automation",
        "app.modules.newsletter",
        "app.modules.audit",
        # beat_schedule references tasks from these modules; without them in
        # autodiscover the worker never registers those tasks and the beat
        # entries fail with "Received unregistered task" at fire time.
        "app.modules.cart",
        "app.modules.inventory",
        "app.modules.blog",
        "app.modules.content",
        "app.modules.integrations",
        "app.modules.dataexchange",
        "app.modules.reporting",
        "app.modules.subscriptions",
        "app.modules.settings",
    ],
    # Task modules live at <pkg>.application.tasks, not <pkg>.tasks. Without
    # related_name autodiscover imports app.modules.<x>.tasks, finds nothing,
    # and the worker registers ZERO custom tasks — every beat_schedule entry
    # (expire carts, cashback, outbox, reindex, …) silently never ran.
    # Reproduced 2026-09-18: finalize() registered 0 tasks; with this fix 20+
    # register. Keep in sync with the beat_schedule task paths below.
    related_name="application.tasks",
)

# ── Periodic tasks (Celery Beat) ─────────────────────────────────────────
# ── Beat heartbeat ─────────────────────────────────────────────────────────
# The scheduler-is-alive canary. Every content check that depends on "did
# cron run" (scheduled posts, abandoned-cart reminders, discount expiry)
# shares this one signal, so it is written by the beat itself rather than by
# any single business task: a heartbeat stays fresh even while every job the
# beat dispatches is failing, which is what makes it a scheduler check rather
# than a job check. The health check reads it via
# settings/application/content_health_service.py::_check_cron_last_run.
HEARTBEAT_KEY = "health:last_beat"
# Generous TTL: the reader treats a beat older than 30 minutes as dead, so the
# key only needs to outlive that by a wide margin. It is a rolling window, not
# a history — no expiry means a stopped beat is legible as "stale" instead of
# silently vanishing into "never ran", which would be indistinguishable from
# a fresh install.
HEARTBEAT_TTL_SECONDS = 3600


async def _record_heartbeat_async() -> str:
    """Stamp the beat in Redis as an ISO-8601 UTC timestamp.

    Uses the same ``get_redis()`` helper the health check reads through, so
    the two sides cannot drift onto different clients or encodings (that
    client is built with ``decode_responses=True``, hence a str write and a
    str read, not bytes).
    """
    from app.core.cache.redis import get_redis

    stamp = datetime.now(UTC).isoformat()
    client = await get_redis()
    await client.set(HEARTBEAT_KEY, stamp, ex=HEARTBEAT_TTL_SECONDS)
    return stamp


# No autoretry: a heartbeat is a pure "the scheduler is alive" stamp, so a
# transient Redis blip that loses one tick is self-correcting on the next
# minute. Retrying would just pile duplicate writes onto an already-failing
# dependency.
@celery_app.task(name="app.worker.celery_app.record_heartbeat")
def record_heartbeat() -> dict[str, Any]:
    """Record that the beat scheduler fired. Fire-and-forget."""
    return {"status": "success", "beat": asyncio.run(_record_heartbeat_async())}


celery_app.conf.beat_schedule = {
    # Scheduler liveness canary, read by the content health check. Runs every
    # minute and is offset off :00 so it does not land in the same instant as
    # the top-of-hour jobs.
    "record-beat-heartbeat": {
        "task": "app.worker.celery_app.record_heartbeat",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
    # Site health, once a day at 06:12. WordPress runs it twice a day; the
    # checks that matter for a store (disk, database reachability, the
    # scheduler) do not change inside a day, and a slower cadence is what lets
    # the history page stay readable. The minute is off :00 so this does not
    # join the top-of-hour burst.
    "site-health-daily": {
        "task": "app.modules.settings.application.tasks.run_site_health",
        "schedule": crontab(minute=12, hour=6),
        "options": {"queue": "default"},
    },
    # Expire stale shopping carts every hour
    "expire-stale-carts": {
        "task": "app.modules.cart.application.tasks.expire_stale_carts",
        "schedule": crontab(minute=0),
        "options": {"queue": "default"},
    },
    # Abandoned-cart recovery reminders (Phase 1, Odoo website_sale concept).
    # Offset from top-of-hour and from the 5-minute reservation jobs so the
    # SMS burst is never scheduled against them.
    "abandoned-cart-recovery": {
        "task": "app.modules.cart.application.tasks.send_abandoned_cart_reminders",
        "schedule": crontab(minute=13, hour="*/2"),
        "options": {"queue": "default"},
    },
    # Process pending cashback allocations every 30 minutes
    "process-pending-cashback": {
        "task": "app.modules.cashback.application.tasks.process_pending_cashback",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "default"},
    },
    # Full search reindex every 6 hours (Phase 4 §11 — Option B-lite).
    # Normal sync is near-real-time via the transactional outbox →
    # sync_single_product (with autoretry); this periodic full reindex is
    # the compensation pass when Elasticsearch was unreachable, bounding the
    # maximum search-staleness window to ~6h instead of ~24h. Offsets minute
    # to avoid colliding with other top-of-hour jobs.
    "reindex-search": {
        "task": "app.modules.search.application.tasks.full_reindex",
        "schedule": crontab(hour="*/6", minute=15),
        "options": {"queue": "analytics"},
    },
    # GDPR retention. An export the subject never collected kept its whole
    # payload forever: the admin route existed and worked, but nothing called
    # it, so the one case the window exists to cover never fired. Daily, off the
    # hour — the windows are measured in days, so an hourly job would repeat the
    # same scan 24 times for the same result.
    "purge-expired-privacy-results": {
        "task": "app.modules.settings.application.tasks.purge_expired_privacy_results",
        "schedule": crontab(hour=4, minute=40),
        "options": {"queue": "default"},
    },
    # Comment IP retention. Once a day, twenty minutes after the export purge so
    # the two privacy sweeps do not compete for the same connections at the same
    # minute. It rewrites rows, so it gets its own slot rather than riding along
    # with the export purge: a slow mask job must not delay the export purge, and
    # a failing one must not roll back the other.
    "mask-expired-comment-ips": {
        "task": "app.modules.settings.application.tasks.mask_expired_comment_ips",
        "schedule": crontab(hour=5, minute=0),
        "options": {"queue": "default"},
    },
    # Media trash retention. Once a day, off the hour, deleting only what has
    # been in the trash longer than the retention window — so an operator who
    # trashes an image by mistake has 30 days to notice and restore it. The
    # window is the task's default rather than a beat argument on purpose: a
    # value editable from the scheduler config is a value that will eventually
    # be edited to 0.
    "purge-media-trash": {
        "task": "app.modules.media.application.tasks.purge_expired_media_trash",
        "schedule": crontab(hour=3, minute=20),
        "options": {"queue": "default"},
    },
    # Generate daily analytics report
    "daily-analytics-report": {
        "task": "app.modules.analytics.application.tasks.generate_daily_report",
        "schedule": crontab(hour=1, minute=0),
        "options": {"queue": "analytics"},
    },
    # Clean up expired OTPs every 15 minutes
    "cleanup-expired-otps": {
        "task": "app.modules.auth.application.tasks.cleanup_expired_otps",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "default"},
    },
    # Check and expire discount codes daily
    "expire-discount-codes": {
        "task": "app.modules.discounts.application.tasks.expire_discount_codes",
        "schedule": crontab(hour=0, minute=5),
        "options": {"queue": "default"},
    },
    # Update product recommendations weekly
    "update-recommendations": {
        "task": "app.modules.recommendations.application.tasks.update_recommendations",
        "schedule": crontab(day_of_week=0, hour=4, minute=0),
        "options": {"queue": "analytics"},
    },
    # Release expired stock reservations every 5 minutes
    "release-expired-reservations": {
        "task": "app.modules.inventory.application.tasks.release_expired_reservations",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "default"},
    },
    # Auto-cancel unpaid PENDING orders every 5 minutes (frees committed stock)
    "cancel-stale-pending-orders": {
        "task": "app.modules.orders.application.tasks.cancel_stale_pending_orders",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "default"},
    },
    # Drain the transactional outbox every minute
    "process-outbox-queue": {
        "task": "app.modules.automation.application.outbox_worker.process_outbox_queue",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
    # Publish scheduled blog posts whose time has come (WordPress-style
    # "scheduled" posts). Runs every minute so go-live is within ~60s of the
    # editor's chosen time.
    "publish-due-scheduled-blog-posts": {
        "task": "app.modules.blog.application.tasks.publish_due_scheduled_posts",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
    # CMS page scheduled publish/unpublish (Strapi-style releases). Every
    # minute, same go-live guarantee as blog posts.
    "process-scheduled-cms-pages": {
        "task": "app.modules.content.application.tasks.process_scheduled_cms_pages",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
    # Custom post type entries, same minute-by-minute guarantee. Without it an
    # entry dated forward through the content-types tab stayed a draft forever,
    # with a filled schedule column and nothing acting on it.
    "publish-scheduled-cpt-entries": {
        "task": "app.modules.blog.application.tasks.publish_scheduled_cpt_entries",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
    # Drain the outbound webhook delivery queue every minute (HMAC-signed
    # POSTs with exponential backoff, max 8 attempts).
    "process-pending-webhooks": {
        "task": "app.modules.integrations.application.tasks.process_pending_webhooks",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
    # Check low stock daily
    "check-low-stock": {
        "task": "app.modules.inventory.application.tasks.check_low_stock_task",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "default"},
    },
    # Evaluate reorder points and suggest replenishment (Odoo orderpoint
    # concept). Hourly, offset from the other top-of-hour inventory jobs.
    "evaluate-reorder-rules": {
        "task": "app.modules.inventory.application.tasks.evaluate_reorder_rules",
        "schedule": crontab(minute=41),
        "options": {"queue": "default"},
    },
    # Reconcile wallet cached balances with the ledger nightly (TASK P2-02)
    "reconcile-wallet-balances": {
        "task": "app.modules.wallet.application.tasks.reconcile_wallet_balances",
        "schedule": crontab(hour=2, minute=30),
        "options": {"queue": "default"},
    },
    # Read-only payment reconciliation sweep. Runs every 30 minutes, offset
    # from the top of the hour so it does not contend with the cart/cashback
    # jobs. Findings are deduplicated by key, so repeated runs only refresh
    # occurrence counts; the task never mutates financial records.
    "reconcile-payments": {
        "task": "app.modules.audit.application.tasks.reconcile_payments",
        "schedule": crontab(minute="7,37"),
        "options": {"queue": "default"},
    },
    # Read-only cross-axis order lifecycle audit. Offset from the payment
    # sweep so the two read-heavy passes do not contend, and deliberately
    # less frequent: a lifecycle contradiction is a data-integrity signal,
    # not a live-money condition that needs half-hourly detection.
    "audit-order-lifecycle": {
        "task": "app.modules.audit.application.tasks.audit_order_lifecycle",
        "schedule": crontab(minute="22", hour="*/2"),
        "options": {"queue": "default"},
    },
    # Dispatch scheduled saved reports every minute (Tehran time); the
    # dispatcher itself only fires reports whose next_run_at has passed.
    "dispatch-scheduled-reports": {
        "task": "app.modules.reporting.application.tasks.dispatch_due_reports",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "analytics"},
    },
    # Recurring subscription billing. Every 15 minutes, offset from other
    # jobs; the runner only bills subscriptions whose next_billing_at has
    # passed, and billing is idempotent per (subscription, period) — a late
    # or duplicated tick cannot charge a customer twice.
    "bill-due-subscriptions": {
        "task": "app.modules.subscriptions.application.tasks.run_due_subscription_billings",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "default"},
    },
    # Send scheduled newsletter campaigns: the dispatcher picks up campaigns
    # whose scheduled_at has passed and enqueues the chunked send task.
    "dispatch-due-newsletter-campaigns": {
        "task": "app.modules.newsletter.application.tasks.dispatch_due_scheduled_campaigns",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
}

# ── Celery Observability & Trace Context Propagation ─────────────────────
import app.worker.observability  # noqa: F401, E402

