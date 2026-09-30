"""Payment API package – exports routers for inclusion in the app."""

from app.modules.payments.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
