"""Invoicing API — expose routers for auto-discovery by main.py."""

from app.modules.invoicing.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
