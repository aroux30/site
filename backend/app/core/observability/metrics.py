"""Prometheus metrics for the application.

Exposes counters, histograms, and gauges that are scraped by the
``/metrics`` endpoint (added in ``main.py``).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# ── Application info ──────────────────────────────────────────────────────
APP_INFO = Info("app", "Application metadata")

# ── HTTP request metrics ──────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    labelnames=["method", "endpoint"],
)

# ── Database metrics ──────────────────────────────────────────────────────
DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

DB_POOL_SIZE = Gauge("db_pool_size", "Current database connection pool size")
DB_POOL_CHECKED_IN = Gauge("db_pool_checked_in", "Database connections currently checked in")
DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "Database connections currently checked out")

# ── Cache & Redis metrics ──────────────────────────────────────────────────
CACHE_HIT = Counter("cache_hits_total", "Total cache hits", labelnames=["cache_name"])
CACHE_MISS = Counter("cache_misses_total", "Total cache misses", labelnames=["cache_name"])
REDIS_OPERATION_DURATION = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation latency in seconds",
    labelnames=["operation"],
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)
REDIS_ERRORS = Counter(
    "redis_errors_total",
    "Total Redis operation errors",
    labelnames=["operation", "error_type"],
)

# ── External HTTP API metrics ─────────────────────────────────────────────
EXTERNAL_HTTP_DURATION = Histogram(
    "external_http_duration_seconds",
    "External HTTP API call duration in seconds",
    labelnames=["provider", "status_code"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
EXTERNAL_HTTP_TOTAL = Counter(
    "external_http_requests_total",
    "Total external HTTP API requests",
    labelnames=["provider", "status_code"],
)

# ── Domain events metrics ─────────────────────────────────────────────────
DOMAIN_EVENTS_TOTAL = Counter(
    "domain_events_total",
    "Total domain events emitted",
    labelnames=["aggregate_type", "event_type"],
)

# ── Celery Background Worker metrics ──────────────────────────────────────
CELERY_QUEUE_LATENCY = Histogram(
    "celery_queue_latency_seconds",
    "Celery queue waiting latency before execution in seconds",
    labelnames=["queue", "task"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
CELERY_TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    labelnames=["task", "state"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
CELERY_TASK_FAILURES = Counter(
    "celery_task_failures_total",
    "Total Celery task failures",
    labelnames=["task", "exception"],
)
CELERY_TASK_SUCCESS = Counter(
    "celery_task_success_total",
    "Total successful Celery task executions",
    labelnames=["task"],
)

# ── Business metrics ─────────────────────────────────────────────────────
ORDERS_CREATED = Counter("orders_created_total", "Total orders created")
PAYMENTS_PROCESSED = Counter(
    "payments_processed_total",
    "Total payments processed",
    labelnames=["provider", "status"],
)
USERS_REGISTERED = Counter("users_registered_total", "Total new user registrations")
OTP_SENT = Counter("otp_sent_total", "Total OTP messages sent", labelnames=["channel"])
