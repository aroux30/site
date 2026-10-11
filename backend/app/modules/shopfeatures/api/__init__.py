"""Shop feature switches — public read + admin read/write."""

from app.modules.shopfeatures.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
