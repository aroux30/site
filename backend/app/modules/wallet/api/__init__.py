"""Wallet API package – exports the routers for inclusion in the app."""

from app.modules.wallet.api.routes import admin_router, router

__all__ = ["admin_router", "router"]
