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

# ── Cache metrics ─────────────────────────────────────────────────────────
CACHE_HIT = Counter("cache_hits_total", "Total cache hits", labelnames=["cache_name"])
CACHE_MISS = Counter("cache_misses_total", "Total cache misses", labelnames=["cache_name"])

# ── Business metrics ─────────────────────────────────────────────────────
ORDERS_CREATED = Counter("orders_created_total", "Total orders created")
PAYMENTS_PROCESSED = Counter(
    "payments_processed_total",
    "Total payments processed",
    labelnames=["provider", "status"],
)
USERS_REGISTERED = Counter("users_registered_total", "Total new user registrations")
OTP_SENT = Counter("otp_sent_total", "Total OTP messages sent", labelnames=["channel"])
