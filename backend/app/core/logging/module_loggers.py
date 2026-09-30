"""Unified structured logger catalog and factory for all 35 backend modules.

Provides pre-bound structlog loggers for zero-overhead contextual logging
across all domain, application, and infrastructure services.
"""

from __future__ import annotations

from typing import Any, cast

import structlog

# All 34 business domain modules + core infrastructure module (35 total)
MODULE_NAMES: tuple[str, ...] = (
    "analytics",
    "approvals",
    "audit",
    "auth",
    "automation",
    "blog",
    "cart",
    "cashback",
    "catalog",
    "checkout",
    "content",
    "core",
    "discounts",
    "gamification",
    "integrations",
    "inventory",
    "loyalty",
    "media",
    "messaging",
    "notifications",
    "orders",
    "payments",
    "rbac",
    "recommendations",
    "referrals",
    "reviews",
    "search",
    "seo",
    "settings",
    "shipping",
    "support",
    "users",
    "vendors",
    "wallet",
    "wishlist",
)


def get_module_logger(module_name: str, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Create a structured logger pre-bound to a specific backend module.

    Example::

        from app.core.logging import get_module_logger
        logger = get_module_logger("orders", service="order_orchestrator")
        logger.info("order_created", order_id="ORD-101", total=500000)
    """
    clean_name = module_name.lower().strip()
    if clean_name not in ("core", "shared", "worker"):
        logger_name = f"app.modules.{clean_name}"
    else:
        logger_name = f"app.{clean_name}"
    return cast(
        "structlog.stdlib.BoundLogger",
        structlog.get_logger(logger_name, module=clean_name, **initial_values),
    )


# Pre-bound static logger singletons for rapid zero-cost import across the codebase
analytics_logger: structlog.stdlib.BoundLogger = get_module_logger("analytics")
approvals_logger: structlog.stdlib.BoundLogger = get_module_logger("approvals")
audit_logger: structlog.stdlib.BoundLogger = get_module_logger("audit")
auth_logger: structlog.stdlib.BoundLogger = get_module_logger("auth")
automation_logger: structlog.stdlib.BoundLogger = get_module_logger("automation")
blog_logger: structlog.stdlib.BoundLogger = get_module_logger("blog")
cart_logger: structlog.stdlib.BoundLogger = get_module_logger("cart")
cashback_logger: structlog.stdlib.BoundLogger = get_module_logger("cashback")
catalog_logger: structlog.stdlib.BoundLogger = get_module_logger("catalog")
checkout_logger: structlog.stdlib.BoundLogger = get_module_logger("checkout")
content_logger: structlog.stdlib.BoundLogger = get_module_logger("content")
core_logger: structlog.stdlib.BoundLogger = get_module_logger("core")
discounts_logger: structlog.stdlib.BoundLogger = get_module_logger("discounts")
gamification_logger: structlog.stdlib.BoundLogger = get_module_logger("gamification")
integrations_logger: structlog.stdlib.BoundLogger = get_module_logger("integrations")
inventory_logger: structlog.stdlib.BoundLogger = get_module_logger("inventory")
loyalty_logger: structlog.stdlib.BoundLogger = get_module_logger("loyalty")
media_logger: structlog.stdlib.BoundLogger = get_module_logger("media")
messaging_logger: structlog.stdlib.BoundLogger = get_module_logger("messaging")
notifications_logger: structlog.stdlib.BoundLogger = get_module_logger("notifications")
orders_logger: structlog.stdlib.BoundLogger = get_module_logger("orders")
payments_logger: structlog.stdlib.BoundLogger = get_module_logger("payments")
rbac_logger: structlog.stdlib.BoundLogger = get_module_logger("rbac")
recommendations_logger: structlog.stdlib.BoundLogger = get_module_logger("recommendations")
referrals_logger: structlog.stdlib.BoundLogger = get_module_logger("referrals")
reviews_logger: structlog.stdlib.BoundLogger = get_module_logger("reviews")
search_logger: structlog.stdlib.BoundLogger = get_module_logger("search")
seo_logger: structlog.stdlib.BoundLogger = get_module_logger("seo")
settings_logger: structlog.stdlib.BoundLogger = get_module_logger("settings")
shipping_logger: structlog.stdlib.BoundLogger = get_module_logger("shipping")
support_logger: structlog.stdlib.BoundLogger = get_module_logger("support")
users_logger: structlog.stdlib.BoundLogger = get_module_logger("users")
vendors_logger: structlog.stdlib.BoundLogger = get_module_logger("vendors")
wallet_logger: structlog.stdlib.BoundLogger = get_module_logger("wallet")
wishlist_logger: structlog.stdlib.BoundLogger = get_module_logger("wishlist")
shared_logger: structlog.stdlib.BoundLogger = get_module_logger("shared")
worker_logger: structlog.stdlib.BoundLogger = get_module_logger("worker")
