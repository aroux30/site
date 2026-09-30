"""Inventory API — re-export the router for auto-discovery by ``main.py``."""

from app.modules.inventory.api.routes import admin_router, router

__all__ = ["router", "admin_router"]
