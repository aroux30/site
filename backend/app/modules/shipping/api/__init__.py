"""Shipping API package — exposes the router for inclusion in the main app."""

from app.modules.shipping.api.routes import router

__all__ = ["router"]
