"""Data-exchange API — expose the admin router for auto-discovery by main.py."""

from app.modules.dataexchange.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
