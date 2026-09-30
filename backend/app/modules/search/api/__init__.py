"""Search module API – exposes ``router`` for inclusion in the app."""

from app.modules.search.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
