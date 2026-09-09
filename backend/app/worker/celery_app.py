"""Celery application configuration.

Usage::

    # Start worker
    celery -A app.worker.celery_app worker --loglevel=info

    # Start beat scheduler
    celery -A app.worker.celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "iranian_ecommerce",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
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
    task_time_limit=600,          # hard limit: 10 minutes
    task_soft_time_limit=540,     # soft limit: 9 minutes
    # ── Result backend ────────────────────────────────────────────────
    result_expires=3600,          # 1 hour
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
        "app.modules.audit",
    ],
)

# ── Periodic tasks (Celery Beat) ─────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Expire stale shopping carts every hour
    "expire-stale-carts": {
        "task": "app.modules.cart.application.tasks.expire_stale_carts",
        "schedule": crontab(minute=0),
        "options": {"queue": "default"},
    },
    # Process pending cashback allocations every 30 minutes
    "process-pending-cashback": {
        "task": "app.modules.cashback.application.tasks.process_pending_cashback",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "default"},
    },
    # Update search index nightly
    "reindex-search": {
        "task": "app.modules.search.application.tasks.full_reindex",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "analytics"},
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
}
