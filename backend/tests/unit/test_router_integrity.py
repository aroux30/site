"""Unit tests for fail-fast router discovery and registration integrity."""

import importlib

import pytest
from fastapi import APIRouter, FastAPI

from app.main import _include_routers


def test_all_defined_routers_exist_and_are_valid():
    """Verify that every single module in the router specification exists and exports a valid APIRouter."""  # noqa: E501
    # List of all 31 core production modules that MUST have a working router
    expected_modules = [
        "app.modules.auth.api",
        "app.modules.users.api",
        "app.modules.rbac.api",
        "app.modules.catalog.api",
        "app.modules.inventory.api",
        "app.modules.cart.api",
        "app.modules.checkout.api",
        "app.modules.orders.api",
        "app.modules.payments.api",
        "app.modules.wallet.api",
        "app.modules.discounts.api",
        "app.modules.shipping.api",
        "app.modules.reviews.api",
        "app.modules.wishlist.api",
        "app.modules.referrals.api",
        "app.modules.cashback.api",
        "app.modules.loyalty.api",
        "app.modules.gamification.api",
        "app.modules.notifications.api",
        "app.modules.messaging.api",
        "app.modules.support.api",
        "app.modules.blog.api",
        "app.modules.seo.api",
        "app.modules.search.api",
        "app.modules.analytics.api",
        "app.modules.recommendations.api",
        "app.modules.approvals.api",
        "app.modules.media.api",
        "app.modules.settings.api",
        "app.modules.audit.api",
        "app.modules.vendors.api",
    ]

    for mod_path in expected_modules:
        mod = importlib.import_module(mod_path)
        router = getattr(mod, "router", None)
        assert router is not None, f"Module '{mod_path}' does not export 'router'"
        assert isinstance(router, APIRouter), (
            f"Export 'router' in '{mod_path}' is not an APIRouter instance"
        )


def test_fail_fast_on_broken_router(monkeypatch):
    """Verify that if any router fails to load, application startup raises RuntimeError immediately (Fail-Fast)."""  # noqa: E501
    test_app = FastAPI()  # Artificially inject an invalid module path that will fail
    with pytest.raises(RuntimeError) as exc_info:
        # Patch importlib to simulate a broken module import
        import importlib

        orig_import = importlib.import_module

        def broken_import(name, *args, **kwargs):
            if name == "app.modules.auth.api":
                raise ImportError("Simulated syntax or import error in auth module")
            return orig_import(name, *args, **kwargs)

        monkeypatch.setattr(importlib, "import_module", broken_import)
        _include_routers(test_app, prefix="/api/v1")

    assert "Critical router failed to load" in str(exc_info.value)


def test_no_duplicate_schema_routes():
    """Every (path, method) pair exposed in the OpenAPI schema must be unique.

    Legacy root-level aliases (seo / vendors) are registered with
    include_in_schema=False and therefore do not appear in the schema —
    only true duplicates fail here.
    """
    from app.main import create_app

    app = create_app()
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in sorted(methods):
            if method in ("HEAD", "OPTIONS"):
                continue
            key = (path, method)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
    assert not duplicates, f"duplicate schema routes registered: {duplicates}"
